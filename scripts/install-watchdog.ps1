# Organon Watchdog Installer — Windows Task Scheduler
# Runs watchdog.ps1 every hour in the background, even when Claude Code is closed.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$WatchdogScript = Join-Path $ScriptDir "watchdog.ps1"
$TaskName = "Organon-Watchdog"
$IntervalMinutes = if ($args[0]) { [int]$args[0] } else { 60 }

Write-Host "Organon Watchdog Installer"
Write-Host "=============================="
Write-Host ""

# Check claude CLI
$claudePath = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claudePath) {
    Write-Host "ERROR: 'claude' CLI not found."
    Write-Host "Install it first: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
}

# Check python3
$pythonPath = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    $pythonPath = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $pythonPath) {
    Write-Host "ERROR: python3/python not found. It's needed to parse job files."
    exit 1
}

# Check watchdog script exists
if (-not (Test-Path $WatchdogScript)) {
    Write-Host "ERROR: watchdog.ps1 not found at $WatchdogScript"
    exit 1
}

# Ensure logs directory
$LogsDir = Join-Path $RepoDir "cron\logs"
New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing watchdog task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create scheduled task
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$WatchdogScript`"" `
    -WorkingDirectory $RepoDir

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 365)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Organon — runs scheduled Claude Code jobs" | Out-Null

Write-Host ""
Write-Host "Watchdog installed and running."
Write-Host ""
Write-Host "  Check interval: every $IntervalMinutes minutes"
Write-Host "  Task name: $TaskName"
Write-Host "  Logs: $LogsDir\watchdog-*.log"
Write-Host ""
Write-Host "To trigger immediately:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To uninstall:            powershell $RepoDir\scripts\uninstall-watchdog.ps1"
