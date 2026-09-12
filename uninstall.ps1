# Complete uninstall of the GeekMagic PC monitor. Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
# Removes: the monitor process, the 3 scheduled tasks, LibreHardwareMonitor (C:\Tools),
#          the dashboard picture on the device (device is switched to its weather clock).
# Leaves:  this project folder (delete it by hand afterwards) and Python.
param(
    [switch]$KeepLibreHardwareMonitor   # keep the LHM program + its autostart task
)
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$lhmDir = 'C:\Tools\LibreHardwareMonitor'

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# 1. Put the device back on its own clock and remove our picture
Step 'Device'
try {
    $cfg = Get-Content (Join-Path $here 'config.json') -Raw | ConvertFrom-Json
    $ip = $cfg.device_ip
    if ($ip) {
        $theme = if ($cfg.off_theme) { $cfg.off_theme } else { 1 }
        Invoke-WebRequest -Uri "http://$ip/set?theme=$theme" -TimeoutSec 5 -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "http://$ip/delete?file=/image/monitor.jpg" -TimeoutSec 5 -UseBasicParsing | Out-Null
        Write-Host "   device $ip switched to theme $theme, monitor.jpg deleted"
    }
} catch { Write-Warning "device not reachable, skipped ($($_.Exception.Message))" }

# 2. Stop the monitor and remove its tasks
Step 'Monitor process and tasks'
Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object {
    try { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -like '*monitor.py*' } catch { $false }
} | Stop-Process -Force -ErrorAction SilentlyContinue
foreach ($t in 'GeekMagic Monitor', 'GeekMagic Clock On Shutdown') {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "   removed task '$t'"
    }
}

# 3. LibreHardwareMonitor (its autostart task was created elevated, so removing it needs one UAC prompt)
if (-not $KeepLibreHardwareMonitor) {
    Step 'LibreHardwareMonitor'
    Get-Process LibreHardwareMonitor -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 2
    if (Get-ScheduledTask -TaskName 'LibreHardwareMonitor Autostart' -ErrorAction SilentlyContinue) {
        $cmd = "Unregister-ScheduledTask -TaskName 'LibreHardwareMonitor Autostart' -Confirm:`$false"
        $p = Start-Process powershell -Verb RunAs -PassThru -Wait -ArgumentList "-NoProfile -WindowStyle Hidden -Command `"$cmd`""
        if ($p.ExitCode -eq 0) { Write-Host "   removed task 'LibreHardwareMonitor Autostart'" }
        else { Write-Warning 'could not remove the LibreHardwareMonitor Autostart task (UAC cancelled?) - remove it in Task Scheduler' }
    }
    if (Test-Path $lhmDir) {
        Remove-Item -Recurse -Force $lhmDir
        Write-Host "   deleted $lhmDir"
    }
}

Write-Host ''
Write-Host "Done. Finally delete this folder by hand: $here" -ForegroundColor Green
Write-Host 'The device keeps working on its own (clock/weather); its WiFi, city and 12-hour settings are untouched.'
