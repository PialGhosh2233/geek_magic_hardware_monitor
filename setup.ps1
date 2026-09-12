# One-shot setup for a new PC. Run from the project folder in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
# Idempotent: safe to re-run. Needs: Windows 10/11, Python 3.10+ on PATH, internet.
#
# Steps: pip deps -> LibreHardwareMonitor (download + web server config) -> 3 scheduled tasks
#        -> start LibreHardwareMonitor + the monitor.  One UAC prompt for the elevated LHM task.
param(
    [switch]$SkipElevated   # skip the UAC-requiring LibreHardwareMonitor autostart task
)
$ErrorActionPreference = 'Stop'
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$lhmDir = 'C:\Tools\LibreHardwareMonitor'
$lhmExe = Join-Path $lhmDir 'LibreHardwareMonitor.exe'
$lhmUrl = 'https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.6/LibreHardwareMonitor.zip'

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# 1. Python + dependencies
Step 'Python and dependencies'
$python  = (Get-Command python.exe  -ErrorAction SilentlyContinue).Source
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $python -or -not $pythonw) { throw 'Python not found on PATH. Install Python 3 from python.org (tick "Add to PATH") and re-run.' }
& $python -m pip install --quiet --disable-pip-version-check -r (Join-Path $here 'requirements.txt')
Write-Host "   python: $python"

# 2. LibreHardwareMonitor
Step 'LibreHardwareMonitor'
if (-not (Test-Path $lhmExe)) {
    New-Item -ItemType Directory -Force $lhmDir | Out-Null
    $zip = Join-Path $env:TEMP 'lhm.zip'
    Invoke-WebRequest -Uri $lhmUrl -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $lhmDir -Force
    Remove-Item $zip -Force
    Write-Host "   downloaded to $lhmDir"
} else { Write-Host "   already at $lhmDir" }
$lhmCfg = Join-Path $lhmDir 'LibreHardwareMonitor.config'
if (-not (Test-Path $lhmCfg)) {
@'
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <appSettings>
    <add key="runWebServerMenuItem" value="true" />
    <add key="listenerPort" value="8085" />
    <add key="authenticationEnabled" value="false" />
    <add key="minTrayMenuItem" value="true" />
    <add key="startMinMenuItem" value="true" />
    <add key="minCloseMenuItem" value="true" />
    <add key="cpuMenuItem" value="true" />
    <add key="gpuMenuItem" value="true" />
    <add key="ramMenuItem" value="true" />
    <add key="mainboardMenuItem" value="true" />
  </appSettings>
</configuration>
'@ | Set-Content -Path $lhmCfg -Encoding UTF8
    Write-Host '   web server config written (port 8085)'
}

# 3. Scheduled tasks (current user, no admin needed)
Step 'Scheduled tasks'
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)

$vbs = Join-Path $here 'run_monitor.vbs'
$trig = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trig.Delay = 'PT30S'
Register-ScheduledTask -TaskName 'GeekMagic Monitor' -Force -Settings $settings -Trigger $trig `
    -Action (New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$vbs`"" -WorkingDirectory $here) | Out-Null
Write-Host '   GeekMagic Monitor (at logon)'

$evt = New-CimInstance -CimClass (Get-CimClass MSFT_TaskEventTrigger root/Microsoft/Windows/TaskScheduler) -ClientOnly
$evt.Subscription = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name=''User32''] and EventID=1074]]</Select></Query></QueryList>'
$evt.Enabled = $true
$clockSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'GeekMagic Clock On Shutdown' -Force -Settings $clockSettings -Trigger $evt `
    -Action (New-ScheduledTaskAction -Execute $pythonw -Argument "`"$(Join-Path $here 'set_clock.py')`"" -WorkingDirectory $here) | Out-Null
Write-Host '   GeekMagic Clock On Shutdown (system event 1074)'

if (-not $SkipElevated) {
    $cmd = "Register-ScheduledTask -TaskName 'LibreHardwareMonitor Autostart' -Force -RunLevel Highest " +
           "-Action (New-ScheduledTaskAction -Execute '$lhmExe' -WorkingDirectory '$lhmDir') " +
           "-Trigger (New-ScheduledTaskTrigger -AtLogOn -User '$env:USERNAME') " +
           "-Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)) | Out-Null"
    Write-Host '   LibreHardwareMonitor Autostart (needs one UAC prompt)...'
    $p = Start-Process powershell -Verb RunAs -PassThru -Wait -ArgumentList "-NoProfile -WindowStyle Hidden -Command `"$cmd`""
    if ($p.ExitCode -ne 0) { Write-Warning 'elevated task registration failed or was cancelled; LHM will not autostart' }
}

# 4. Start things now
Step 'Starting'
if (-not (Get-Process LibreHardwareMonitor -ErrorAction SilentlyContinue)) {
    if (Get-ScheduledTask -TaskName 'LibreHardwareMonitor Autostart' -ErrorAction SilentlyContinue) {
        Start-ScheduledTask -TaskName 'LibreHardwareMonitor Autostart'
    } else {
        Start-Process -FilePath $lhmExe -WorkingDirectory $lhmDir -Verb RunAs
    }
    Start-Sleep 8
}
try { $null = Invoke-WebRequest -Uri 'http://localhost:8085/data.json' -TimeoutSec 5 -UseBasicParsing; Write-Host '   LibreHardwareMonitor web server: OK' }
catch { Write-Warning 'LibreHardwareMonitor web server not answering yet on port 8085 (temps will show -- until it is)' }

Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $pythonw } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName 'GeekMagic Monitor'
Start-Sleep 12
$log = Join-Path $here 'monitor.log'
if (Test-Path $log) { Write-Host '   last log lines:'; Get-Content $log -Tail 3 | ForEach-Object { "     $_" } }
Write-Host 'Done. The device is found automatically on the LAN (config.json device_ip/device_mac get filled in).' -ForegroundColor Green
