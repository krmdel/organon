# Organon Watchdog — Windows version
# Runs scheduled jobs outside Claude Code sessions via Task Scheduler.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$JobsDir = Join-Path $RepoDir "cron\jobs"
$LogsDir = Join-Path $RepoDir "cron\logs"
$StateFile = Join-Path $RepoDir "cron\watchdog.state.json"
$LockFile = Join-Path $RepoDir "cron\.watchdog.lock"

$Intervals = @{
    "every_10m" = 600
    "every_30m" = 1800
    "every_1h"  = 3600
    "every_2h"  = 7200
    "every_4h"  = 14400
}

function Log($msg) {
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
}

# Lock check
if (Test-Path $LockFile) {
    $oldPid = Get-Content $LockFile -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Log "Another watchdog is running (PID $oldPid). Exiting."
        exit 0
    }
    Log "Stale lock found. Removing."
    Remove-Item $LockFile -Force
}

$PID | Out-File $LockFile -Force
try {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null

    # Check claude CLI
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        Log "ERROR: 'claude' CLI not found on PATH."
        exit 1
    }

    # Init state
    if (-not (Test-Path $StateFile)) {
        "{}" | Out-File $StateFile
    }

    if (-not (Test-Path $JobsDir)) {
        Log "No jobs directory found. Nothing to do."
        exit 0
    }

    $state = Get-Content $StateFile -Raw | ConvertFrom-Json
    $jobCount = 0
    $runCount = 0

    foreach ($jobFile in Get-ChildItem "$JobsDir\*.md") {
        $content = Get-Content $jobFile.FullName -Raw

        # Parse YAML frontmatter
        if ($content -notmatch '(?s)^---\s*\n(.*?)\n---') { continue }
        $fm = @{}
        foreach ($line in ($Matches[1] -split "`n")) {
            if ($line -match '^(\w+):\s*(.*)$') {
                $fm[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
            }
        }

        $name = $fm["name"]
        $schedule = $fm["schedule"]
        $model = if ($fm["model"]) { $fm["model"] } else { "sonnet" }
        $budget = if ($fm["max_budget_usd"]) { $fm["max_budget_usd"] } else { "0.50" }
        $enabled = if ($fm["enabled"]) { $fm["enabled"] } else { "true" }

        if ($enabled -ne "true") { continue }
        if ($schedule -eq "session_start") { continue }

        $jobCount++

        $interval = $Intervals[$schedule]
        if (-not $interval) {
            Log "WARN: Unknown schedule '$schedule' for $name"
            continue
        }

        $lastRun = 0
        if ($state.PSObject.Properties[$name]) {
            $lastRun = [int]$state.$name.last_run
        }
        $now = [int](Get-Date -UFormat %s)
        $elapsed = $now - $lastRun

        if ($elapsed -lt $interval) {
            $remaining = [math]::Round(($interval - $elapsed) / 60)
            Log "$name`: not due yet (${remaining}m remaining)"
            continue
        }

        # Execute
        Log "$name`: RUNNING (model=$model, budget=`$$budget)"
        $runCount++

        # Extract prompt (everything after second ---)
        $promptBody = ($content -replace '(?s)^---.*?---\s*\n', '').Trim()
        $today = Get-Date -Format "yyyy-MM-dd"
        $logFile = Join-Path $LogsDir "${name}_${today}.log"

        $runHeader = "=== Run at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
        Add-Content $logFile $runHeader

        try {
            $output = claude -p $promptBody --model $model --max-turns 25 --allowedTools "Read,Write,Edit,Bash,Glob,Grep,WebSearch,WebFetch" 2>&1
            Add-Content $logFile ($output | Out-String)
        } catch {
            Add-Content $logFile "[watchdog] claude error: $_"
        }

        Add-Content $logFile "=== End run ===`n"

        # Update state
        if (-not $state.PSObject.Properties[$name]) {
            $state | Add-Member -NotePropertyName $name -NotePropertyValue @{ last_run = "$now" }
        } else {
            $state.$name.last_run = "$now"
        }
        $state | ConvertTo-Json | Out-File $StateFile
        Log "$name`: completed. Log at $logFile"
    }

    Log "Done. $jobCount enabled jobs found, $runCount executed."
} finally {
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
}
