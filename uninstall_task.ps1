# Removes the scheduled tasks and stops the monitor (LibreHardwareMonitor itself is left installed).
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
foreach ($t in 'GeekMagic Monitor', 'GeekMagic Clock On Shutdown') {
    Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction SilentlyContinue
}
Write-Host 'Removed GeekMagic tasks. To also remove the LibreHardwareMonitor Autostart task, run as admin:'
Write-Host '  Unregister-ScheduledTask -TaskName ''LibreHardwareMonitor Autostart'' -Confirm:$false'
