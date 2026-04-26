# Install the cron dispatcher — registers a Task Scheduler entry that runs every minute.
# Windows only. For Mac/Linux, use install-crons.sh.

$ProjectDir = Split-Path -Parent $PSScriptRoot
$Dispatcher = Join-Path $ProjectDir "scripts\run-crons.ps1"

# Derive a unique slug from the project directory name for multi-client support
$ProjectSlug = (Split-Path -Leaf $ProjectDir).ToLower() -replace '[^a-z0-9-]', '-'
$TaskName = "Organon-$ProjectSlug"

# Pre-flight checks
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "Error: 'claude' CLI not found. Install Claude Code first."
    exit 1
}

# Check if already installed
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Cron dispatcher is already installed as scheduled task '$TaskName'."
    exit 0
}

# Count enabled jobs
$enabled = 0
Get-ChildItem -Path (Join-Path $ProjectDir "cron\jobs") -Filter "*.md" -ErrorAction SilentlyContinue | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $active = if ($content -match '(?m)^active:\s*"?(\w+)"?') { $Matches[1] } else { "true" }
    if ($active -ne "false") { $enabled++ }
}

# Install
$action = New-ScheduledTaskAction -Execute "powershell" -Argument "-ExecutionPolicy Bypass -File `"$Dispatcher`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 365)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Organon cron dispatcher — checks cron/jobs/ every minute"

Write-Host "Cron dispatcher installed as scheduled task '$TaskName'."
Write-Host "  Checks cron/jobs/ every minute for due jobs."
Write-Host "  $enabled enabled job(s) found."
Write-Host "  Logs go to cron/logs/"
Write-Host ""
Write-Host "To remove: powershell scripts/uninstall-crons.ps1"
