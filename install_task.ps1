# Registers (or refreshes) the "GeekMagic Monitor" scheduled task: runs run_monitor.vbs at logon, 30 s delay.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbs  = Join-Path $here 'run_monitor.vbs'
$a = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$vbs`"" -WorkingDirectory $here
$t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$t.Delay = 'PT30S'
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'GeekMagic Monitor' -Action $a -Trigger $t -Settings $s -Force | Select-Object TaskName, State
