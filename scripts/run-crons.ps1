# Dispatcher — runs every minute via Windows Task Scheduler.
# Scans cron/jobs/*.md, fires any jobs matching the current time and day.
# Supports exact times ("09:00"), multiple times ("09:00,13:00"),
# minute intervals ("every_1m", "every_5m"), and hour intervals ("every_1h", "every_2h").
# Features: timeout, retry, notifications, status tracking, catch-up after sleep/reboot.

$ProjectDir = Split-Path -Parent $PSScriptRoot
$CronsDir = Join-Path $ProjectDir "cron\jobs"
$LogsDir = Join-Path $ProjectDir "cron\logs"
$StatusDir = Join-Path $ProjectDir "cron\status"
$NowHour = [int](Get-Date -Format "HH")
$NowMin = Get-Date -Format "mm"
$NowTime = Get-Date -Format "HH:mm"
$NowDay = (Get-Date).ToString("ddd").ToLower()
$NowUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $StatusDir | Out-Null

# --- Helpers ---

function Format-Duration {
    param([int]$Seconds)
    if ($Seconds -lt 60) { return "${Seconds}s" }
    $m = [math]::Floor($Seconds / 60)
    $s = $Seconds % 60
    if ($s -eq 0) { return "${m}m" }
    return "${m}m ${s}s"
}

function ConvertTo-TimeoutMs {
    param([string]$Value)
    if ($Value -match '^(\d+)s$') { return [int]$Matches[1] * 1000 }
    if ($Value -match '^(\d+)m$') { return [int]$Matches[1] * 60 * 1000 }
    if ($Value -match '^(\d+)h$') { return [int]$Matches[1] * 3600 * 1000 }
    # Default 30 minutes
    return 1800000
}

function Send-Notification {
    param([string]$Title, [string]$Subtitle, [string]$Body)
    try {
        # Windows toast notification
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("$Subtitle")) | Out-Null
        $textNodes.Item(1).AppendChild($template.CreateTextNode($Body)) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Organon").Show($toast)
    } catch {
        # Fallback: BurntToast module or silent
        if (Get-Module -ListAvailable -Name BurntToast) {
            New-BurntToastNotification -Text "$Subtitle", $Body -ErrorAction SilentlyContinue
        }
    }
}

function Test-TimeMatch {
    param([string]$Sched)

    # Interval: every_Nm (minutes)
    if ($Sched -match '^every_(\d+)m$') {
        $interval = [int]$Matches[1]
        return ([int]$NowMin % $interval -eq 0)
    }

    # Interval: every_Nh (hours)
    if ($Sched -match '^every_(\d+)h$') {
        $interval = [int]$Matches[1]
        return ($NowMin -eq "00" -and ($NowHour % $interval -eq 0))
    }

    # Comma-separated or single time
    $times = $Sched -split ',' | ForEach-Object { $_.Trim() }
    return ($NowTime -in $times)
}

function Test-TimeInRange {
    param([string]$Sched, [datetime]$MissedTime)
    # Only for fixed-time jobs — check if any scheduled time falls in the missed window
    if ($Sched -match '^every_') { return $false }

    $times = $Sched -split ',' | ForEach-Object { $_.Trim() }
    foreach ($t in $times) {
        if ($t -match '^\d{2}:\d{2}$') {
            $schedDt = Get-Date -Hour ([int]$t.Substring(0,2)) -Minute ([int]$t.Substring(3,2)) -Second 0
            if ($schedDt -ge $MissedTime -and $schedDt -lt (Get-Date)) {
                return $true
            }
        }
    }
    return $false
}

function Read-StatusFile {
    param([string]$Path)
    if (Test-Path $Path) {
        try {
            return Get-Content $Path -Raw | ConvertFrom-Json
        } catch {
            return $null
        }
    }
    return $null
}

function Write-StatusFile {
    param([string]$Path, [hashtable]$Data)
    $Data | ConvertTo-Json -Compress | Set-Content $Path -Encoding UTF8
}

function Invoke-Job {
    param(
        [string]$File,
        [string]$JobName,
        [string]$Prompt,
        [string]$Model,
        [string]$Notify,
        [string]$Description,
        [string]$Timeout,
        [int]$Retry,
        [bool]$IsCatchUp = $false
    )

    $basename = [System.IO.Path]::GetFileNameWithoutExtension($File)
    $logFile = Join-Path $LogsDir "$basename.log"
    $statusFile = Join-Path $StatusDir "$basename.json"
    $timeoutMs = ConvertTo-TimeoutMs $Timeout

    # Read previous status for counters
    $prevStatus = Read-StatusFile $statusFile
    $runCount = if ($prevStatus -and $prevStatus.run_count) { [int]$prevStatus.run_count } else { 0 }
    $failCount = if ($prevStatus -and $prevStatus.fail_count) { [int]$prevStatus.fail_count } else { 0 }

    $catchUpTag = if ($IsCatchUp) { " [CATCH-UP]" } else { "" }

    # Retry loop
    $maxAttempts = $Retry + 1
    $attempt = 0
    $success = $false
    $lastExitCodeVal = -1
    $totalDuration = 0

    while ($attempt -lt $maxAttempts) {
        $attempt++
        $attemptTag = if ($maxAttempts -gt 1) { " (attempt $attempt/$maxAttempts)" } else { "" }

        $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        Add-Content $logFile "`n=== [$timestamp] START: ${JobName}${catchUpTag}${attemptTag} ==="
        $startTime = Get-Date

        # Clear CLAUDECODE env var to avoid nested session error
        Remove-Item Env:CLAUDECODE -ErrorAction SilentlyContinue

        $timedOut = $false
        $tempOut = [System.IO.Path]::GetTempFileName()
        $tempErr = [System.IO.Path]::GetTempFileName()

        try {
            $process = Start-Process -FilePath "claude" `
                -ArgumentList "-p", "`"$prompt`"", "--model", $Model, "--dangerously-skip-permissions" `
                -NoNewWindow -PassThru `
                -RedirectStandardOutput $tempOut `
                -RedirectStandardError $tempErr

            if (-not $process.WaitForExit($timeoutMs)) {
                $process.Kill()
                $timedOut = $true
            }

            $lastExitCodeVal = $process.ExitCode

            # Append output to log
            if (Test-Path $tempOut) {
                $outContent = Get-Content $tempOut -Raw -ErrorAction SilentlyContinue
                if ($outContent) { Add-Content $logFile $outContent }
            }
            if (Test-Path $tempErr) {
                $errContent = Get-Content $tempErr -Raw -ErrorAction SilentlyContinue
                if ($errContent) { Add-Content $logFile "[stderr] $errContent" }
            }
        } catch {
            Add-Content $logFile "[dispatcher] Error: $_"
            $lastExitCodeVal = 1
        } finally {
            Remove-Item $tempOut -ErrorAction SilentlyContinue
            Remove-Item $tempErr -ErrorAction SilentlyContinue
        }

        $endTime = Get-Date
        $duration = [int]($endTime - $startTime).TotalSeconds
        $totalDuration += $duration
        $durationStr = Format-Duration $duration
        $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

        if ($timedOut) {
            Add-Content $logFile "=== [$timestamp] TIMEOUT: ${JobName} after ${durationStr}${attemptTag} ==="
            $lastExitCodeVal = 124
        } else {
            Add-Content $logFile "=== [$timestamp] END: ${JobName} (${durationStr})${attemptTag} ==="
        }

        if ($lastExitCodeVal -eq 0 -and -not $timedOut) {
            $success = $true
            break
        }

        # If more attempts remain, log the retry
        if ($attempt -lt $maxAttempts) {
            Add-Content $logFile "[dispatcher] Retrying ${JobName}..."
        }
    }

    # Update counters
    $runCount++
    if (-not $success) { $failCount++ }

    $result = if ($timedOut) { "timeout" } elseif ($success) { "success" } else { "failure" }

    # Write per-job status file
    Write-StatusFile $statusFile @{
        last_run   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        result     = $result
        duration   = $totalDuration
        exit_code  = $lastExitCodeVal
        run_count  = $runCount
        fail_count = $failCount
    }

    # Notifications
    $durationTotal = Format-Duration $totalDuration
    $catchUpSuffix = if ($IsCatchUp) { " (catch-up)" } else { "" }
    $notifySuccess = $Notify -in @("on_finish", "on_success")
    $notifyFailure = $Notify -in @("on_finish", "on_failure")

    if ($success -and $notifySuccess) {
        Send-Notification -Title "Organon" -Subtitle "$([char]0x2713) ${JobName}${catchUpSuffix}" -Body "Completed in $durationTotal"
    } elseif ($timedOut -and $notifyFailure) {
        Send-Notification -Title "Organon" -Subtitle "$([char]0x2717) ${JobName} timed out${catchUpSuffix}" -Body "Killed after $Timeout limit"
    } elseif (-not $success -and $notifyFailure) {
        Send-Notification -Title "Organon" -Subtitle "$([char]0x2717) ${JobName} failed${catchUpSuffix}" -Body "Exit code $lastExitCodeVal after $durationTotal"
    }
}

function Parse-JobFile {
    param([string]$FilePath)

    $content = Get-Content $FilePath -Raw

    $active      = if ($content -match '(?m)^active:\s*"?(\w+)"?')         { $Matches[1] } else { "true" }
    $schedTime   = if ($content -match '(?m)^time:\s*"?([^"\r\n]+)"?')     { $Matches[1].Trim() } else { "" }
    $schedDays   = if ($content -match '(?m)^days:\s*"?(\w+)"?')           { $Matches[1] } else { "" }
    $model       = if ($content -match '(?m)^model:\s*"?(\w+)"?')          { $Matches[1] } else { "sonnet" }
    $jobName     = if ($content -match '(?m)^name:\s*"?([^"\r\n]+)"?')     { $Matches[1] } else { [System.IO.Path]::GetFileNameWithoutExtension($FilePath) }
    $notify      = if ($content -match '(?m)^notify:\s*"?([^"\r\n]+)"?')   { $Matches[1].Trim() } else { "on_finish" }
    $description = if ($content -match '(?m)^description:\s*"?([^"\r\n]+)"?') { $Matches[1].Trim() } else { "" }
    $timeout     = if ($content -match '(?m)^timeout:\s*"?([^"\r\n]+)"?')  { $Matches[1].Trim() } else { "30m" }
    $retry       = if ($content -match '(?m)^retry:\s*"?(\d+)"?')          { [int]$Matches[1] } else { 0 }

    # Extract prompt body (everything after second ---)
    $parts = $content -split '---'
    $prompt = ""
    if ($parts.Count -ge 3) {
        $prompt = ($parts[2..($parts.Count - 1)] -join '---').Trim()
    }

    return @{
        Active      = $active
        Time        = $schedTime
        Days        = $schedDays
        Model       = $model
        Name        = $jobName
        Notify      = $notify
        Description = $description
        Timeout     = $timeout
        Retry       = $retry
        Prompt      = $prompt
    }
}

function Test-DayMatch {
    param([string]$ScheduledDays)
    switch ($ScheduledDays) {
        "daily"    { return $true }
        "weekdays" { return ($NowDay -notin @("sat", "sun")) }
        "weekends" { return ($NowDay -in @("sat", "sun")) }
        default    { return ($ScheduledDays -match $NowDay) }
    }
}

# --- Write dispatcher status BEFORE scanning jobs ---

$dispatcherStatusFile = Join-Path $StatusDir "dispatcher.json"
$prevDispatcher = Read-StatusFile $dispatcherStatusFile

Write-StatusFile $dispatcherStatusFile @{
    last_dispatch = $NowUtc
    pid           = $PID
}

# --- Catch-up: detect gap and run missed fixed-time jobs ---

if ($prevDispatcher -and $prevDispatcher.last_dispatch) {
    try {
        $lastDispatch = [datetime]::Parse($prevDispatcher.last_dispatch).ToUniversalTime()
        $nowDt = (Get-Date).ToUniversalTime()
        $gapSeconds = ($nowDt - $lastDispatch).TotalSeconds

        if ($gapSeconds -gt 120) {
            # Cap at 24 hours
            $catchUpFrom = if ($gapSeconds -gt 86400) {
                $nowDt.AddHours(-24)
            } else {
                $lastDispatch
            }

            $gapStr = Format-Duration ([int][math]::Min($gapSeconds, 86400))
            # Log catch-up scan
            $catchUpLogFile = Join-Path $LogsDir "dispatcher.log"
            $timestamp = $nowDt.ToString("yyyy-MM-ddTHH:mm:ssZ")
            Add-Content $catchUpLogFile "`n=== [$timestamp] CATCH-UP: gap of $gapStr detected, scanning missed jobs ==="

            Get-ChildItem -Path $CronsDir -Filter "*.md" -ErrorAction SilentlyContinue | ForEach-Object {
                $job = Parse-JobFile $_.FullName
                if ($job.Active -eq "false") { return }
                if ([string]::IsNullOrEmpty($job.Prompt)) { return }

                # Only catch up fixed-time jobs (not intervals)
                if ($job.Time -match '^every_') { return }

                # Check if any scheduled time falls in the gap
                if (-not (Test-TimeInRange $job.Time $catchUpFrom)) { return }

                # Check day match (use today's day — close enough for catch-up)
                if (-not (Test-DayMatch $job.Days)) { return }

                Add-Content $catchUpLogFile "[catch-up] Running missed job: $($job.Name)"

                Invoke-Job -File $_.FullName `
                    -JobName $job.Name `
                    -Prompt $job.Prompt `
                    -Model $job.Model `
                    -Notify $job.Notify `
                    -Description $job.Description `
                    -Timeout $job.Timeout `
                    -Retry $job.Retry `
                    -IsCatchUp $true
            }

            Add-Content $catchUpLogFile "=== [$timestamp] CATCH-UP: scan complete ==="
        }
    } catch {
        # If we can't parse the last dispatch, skip catch-up silently
    }
}

# --- Main dispatch loop ---

Get-ChildItem -Path $CronsDir -Filter "*.md" -ErrorAction SilentlyContinue | ForEach-Object {
    $job = Parse-JobFile $_.FullName

    if ($job.Active -eq "false") { return }
    if (-not (Test-TimeMatch $job.Time)) { return }
    if (-not (Test-DayMatch $job.Days)) { return }
    if ([string]::IsNullOrEmpty($job.Prompt)) { return }

    Invoke-Job -File $_.FullName `
        -JobName $job.Name `
        -Prompt $job.Prompt `
        -Model $job.Model `
        -Notify $job.Notify `
        -Description $job.Description `
        -Timeout $job.Timeout `
        -Retry $job.Retry `
        -IsCatchUp $false
}
