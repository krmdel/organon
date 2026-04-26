# Organon Watchdog Uninstaller — removes from Windows Task Scheduler
# Job files in cron/jobs/ are NOT deleted.

$TaskName = "Organon-Watchdog"

Write-Host "Organon Watchdog Uninstaller"
Write-Host "================================"
Write-Host ""

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "Watchdog is not installed (no scheduled task found)."
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

Write-Host "Watchdog removed."
Write-Host ""
Write-Host "Your job files in cron/jobs/ are untouched."
Write-Host "To reinstall later: powershell scripts\install-watchdog.ps1"
