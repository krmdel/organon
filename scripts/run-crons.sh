#!/usr/bin/env bash
# Dispatcher — runs every minute via OS crontab.
# Scans cron/jobs/*.md, fires any jobs matching the current time and day.
# Supports exact times ("09:00"), multiple times ("09:00,13:00,17:00"),
# minute intervals ("every_1m", "every_5m"), and hour intervals ("every_1h", "every_2h").
# Features: timeout watchdog, retry, per-job status tracking, desktop notifications, catch-up.

set -euo pipefail

# Ensure common user binary paths are available (launchd uses minimal PATH)
export PATH="${HOME}/.local/bin:${HOME}/.npm-global/bin:/usr/local/bin:/opt/homebrew/bin:${PATH}"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CRONS_DIR="${PROJECT_DIR}/cron/jobs"
LOGS_DIR="${PROJECT_DIR}/cron/logs"
STATUS_DIR="${PROJECT_DIR}/cron/status"
NOW_HOUR=$(date +%H)
NOW_MIN=$(date +%M)
NOW_TIME="${NOW_HOUR}:${NOW_MIN}"
NOW_DAY=$(date +%a | tr '[:upper:]' '[:lower:]')  # mon, tue, wed, etc.
NOW_EPOCH=$(date +%s)

mkdir -p "$LOGS_DIR" "$STATUS_DIR"

# Log rotation: keep the active log under LOG_MAX_BYTES. When a log grows
# past the threshold we rotate it to .1, .2, ... up to LOG_KEEP archives;
# beyond that the oldest archive is dropped. Called lazily before each
# append so we never stall the dispatcher on a large rotation burst.
LOG_MAX_BYTES=${CRON_LOG_MAX_BYTES:-10485760}   # 10 MiB
LOG_KEEP=${CRON_LOG_KEEP:-5}

rotate_log_if_needed() {
  local log="$1"
  [[ -f "$log" ]] || return 0
  local size
  # Portable stat: try BSD (-f%z), then GNU (-c%s).
  size=$(stat -f%z "$log" 2>/dev/null || stat -c%s "$log" 2>/dev/null || echo 0)
  (( size >= LOG_MAX_BYTES )) || return 0

  # Drop the oldest archive, shift the rest down, move active → .1.
  [[ -f "${log}.${LOG_KEEP}" ]] && rm -f "${log}.${LOG_KEEP}"
  local i
  for (( i = LOG_KEEP - 1; i >= 1; i-- )); do
    [[ -f "${log}.${i}" ]] && mv "${log}.${i}" "${log}.$((i + 1))"
  done
  mv "$log" "${log}.1"
  : > "$log"
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Format seconds as human-readable duration: "2m 34s" or "45s"
format_duration() {
  local secs="$1"
  if (( secs >= 60 )); then
    echo "$((secs / 60))m $((secs % 60))s"
  else
    echo "${secs}s"
  fi
}

# Parse timeout string to seconds. Supports "30m", "1h", "90s", plain number.
parse_timeout() {
  local val="$1"
  if [[ "$val" =~ ^([0-9]+)m$ ]]; then
    echo $(( ${BASH_REMATCH[1]} * 60 ))
  elif [[ "$val" =~ ^([0-9]+)h$ ]]; then
    echo $(( ${BASH_REMATCH[1]} * 3600 ))
  elif [[ "$val" =~ ^([0-9]+)s$ ]]; then
    echo "${BASH_REMATCH[1]}"
  elif [[ "$val" =~ ^[0-9]+$ ]]; then
    echo "$val"
  else
    echo "1800"  # default 30m
  fi
}

# Send a desktop notification (macOS native or Linux notify-send)
send_notification() {
  local title="$1" subtitle="$2" body="$3"
  if [[ "$(uname)" == "Darwin" ]]; then
    osascript -e "display notification \"$body\" with title \"$title\" subtitle \"$subtitle\" sound name \"default\"" 2>/dev/null || true
  else
    command -v notify-send &>/dev/null && notify-send "$title" "$subtitle: $body" 2>/dev/null || true
  fi
}

# Check if a time value matches the current time.
# Handles: exact ("09:00"), comma-separated ("09:00,13:00"),
# minute intervals ("every_5m"), hour intervals ("every_2h").
time_matches() {
  local sched="$1"

  # Interval: every_Nm — run when minute is divisible by N
  if [[ "$sched" =~ ^every_([0-9]+)m$ ]]; then
    local interval="${BASH_REMATCH[1]}"
    (( 10#$NOW_MIN % interval == 0 )) && return 0
    return 1
  fi

  # Interval: every_Nh — run on the hour when hour is divisible by N
  if [[ "$sched" =~ ^every_([0-9]+)h$ ]]; then
    local interval="${BASH_REMATCH[1]}"
    [[ "$NOW_MIN" == "00" ]] && (( 10#$NOW_HOUR % interval == 0 )) && return 0
    return 1
  fi

  # Comma-separated or single time
  IFS=',' read -ra TIMES <<< "$sched"
  for t in "${TIMES[@]}"; do
    t=$(echo "$t" | tr -d ' ')
    [[ "$t" == "$NOW_TIME" ]] && return 0
  done
  return 1
}

# Check if a schedule is a fixed-time schedule (not an interval)
is_fixed_time() {
  local sched="$1"
  [[ ! "$sched" =~ ^every_ ]]
}

# Return all fixed times from a schedule string as space-separated list
get_fixed_times() {
  local sched="$1"
  echo "$sched" | tr ',' ' '
}

# Read a JSON field from a status file using awk (no jq dependency)
read_status_field() {
  local file="$1" field="$2"
  if [[ -f "$file" ]]; then
    awk -F'"' -v key="$field" '{ for(i=1;i<=NF;i++) if($i==key) print $(i+2) }' "$file" | head -1
  fi
}

# Write per-job status file, preserving cumulative counters
write_job_status() {
  local status_file="$1" result="$2" duration="$3" exit_code="$4"
  local prev_run_count prev_fail_count new_run_count new_fail_count

  prev_run_count=$(read_status_field "$status_file" "run_count")
  prev_fail_count=$(read_status_field "$status_file" "fail_count")
  prev_run_count="${prev_run_count:-0}"
  prev_fail_count="${prev_fail_count:-0}"
  # Strip non-numeric (awk may grab trailing chars)
  prev_run_count="${prev_run_count//[^0-9]/}"
  prev_fail_count="${prev_fail_count//[^0-9]/}"
  prev_run_count="${prev_run_count:-0}"
  prev_fail_count="${prev_fail_count:-0}"

  new_run_count=$((prev_run_count + 1))
  if [[ "$result" != "success" ]]; then
    new_fail_count=$((prev_fail_count + 1))
  else
    new_fail_count="$prev_fail_count"
  fi

  cat > "$status_file" <<STATUSEOF
{"last_run":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","result":"${result}","duration":${duration},"exit_code":${exit_code},"run_count":${new_run_count},"fail_count":${new_fail_count}}
STATUSEOF
}

# Execute a single job with timeout, retry, status tracking, and notifications.
# Runs inside a background subshell.
run_job() {
  local file="$1" catchup_label="$2"  # catchup_label is empty or "(catch-up)"

  # Parse YAML frontmatter
  ACTIVE=$(awk '/^---/{n++; next} n==1 && /^active:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  [[ "$ACTIVE" == "false" ]] && return 0

  SCHED_TIME=$(awk '/^---/{n++; next} n==1 && /^time:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  SCHED_DAYS=$(awk '/^---/{n++; next} n==1 && /^days:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  MODEL=$(awk '/^---/{n++; next} n==1 && /^model:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  JOB_NAME=$(awk '/^---/{n++; next} n==1 && /^name:/{gsub(/^name: *"?/, ""); gsub(/"$/, ""); print}' "$file")
  NOTIFY=$(awk '/^---/{n++; next} n==1 && /^notify:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  DESCRIPTION=$(awk '/^---/{n++; next} n==1 && /^description:/{gsub(/^description: *"?/, ""); gsub(/"$/, ""); print}' "$file")
  TIMEOUT_RAW=$(awk '/^---/{n++; next} n==1 && /^timeout:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  RETRY=$(awk '/^---/{n++; next} n==1 && /^retry:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  # C1: per-job permission scoping. Replaces the unconditional
  # --dangerously-skip-permissions that every cron used to run with.
  # Defaults: acceptEdits mode (writes allowed, destructive Bash still
  # gated by settings.json denies). Jobs can opt in to
  # bypassPermissions via explicit YAML, and can narrow the tool
  # surface via `allowed_tools`.
  PERM_MODE=$(awk '/^---/{n++; next} n==1 && /^permission_mode:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  ALLOWED_TOOLS=$(awk '/^---/{n++; next} n==1 && /^allowed_tools:/{gsub(/^allowed_tools: *"?/, ""); gsub(/"$/, ""); print}' "$file")
  PERM_MODE="${PERM_MODE:-acceptEdits}"

  MODEL="${MODEL:-sonnet}"
  JOB_NAME="${JOB_NAME:-$(basename "$file" .md)}"
  NOTIFY="${NOTIFY:-on_finish}"
  TIMEOUT_RAW="${TIMEOUT_RAW:-30m}"
  RETRY="${RETRY:-0}"
  TIMEOUT_SECS=$(parse_timeout "$TIMEOUT_RAW")
  MAX_ATTEMPTS=$((RETRY + 1))

  # Extract prompt body (everything after the second ---)
  PROMPT=$(awk 'BEGIN{n=0} /^---/{n++; next} n>=2{print}' "$file")
  [[ -z "$PROMPT" ]] && return 0

  local LOG_FILE="${LOGS_DIR}/$(basename "$file" .md).log"
  local STATUS_FILE="${STATUS_DIR}/$(basename "$file" .md).json"
  rotate_log_if_needed "$LOG_FILE"

  local label_prefix=""
  [[ -n "$catchup_label" ]] && label_prefix="CATCH-UP "

  echo ""
  echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] ${label_prefix}START: ${JOB_NAME} ==="

  local attempt=0
  local final_exit_code=1
  local final_result="failure"
  local timed_out=false
  local job_start_epoch
  job_start_epoch=$(date +%s)

  while (( attempt < MAX_ATTEMPTS )); do
    attempt=$((attempt + 1))
    timed_out=false

    if (( MAX_ATTEMPTS > 1 )); then
      echo "--- Attempt ${attempt}/${MAX_ATTEMPTS} ---"
    fi

    local attempt_start
    attempt_start=$(date +%s)

    # Launch claude with timeout watchdog + scoped permissions (C1).
    # Build the claude command incrementally so we only add
    # --allowed-tools when the job opts in.
    local claude_cmd=(claude -p "$PROMPT" --model "$MODEL" --permission-mode "$PERM_MODE")
    if [[ -n "$ALLOWED_TOOLS" ]]; then
      claude_cmd+=(--allowed-tools "$ALLOWED_TOOLS")
    fi
    if [[ "$PERM_MODE" == "bypassPermissions" ]]; then
      echo "[${JOB_NAME}] WARNING: job opted in to bypassPermissions — all permission gates bypassed." >&2
    fi
    env -u CLAUDECODE "${claude_cmd[@]}" 2>&1 &
    local CLAUDE_PID=$!

    # Watchdog: kill claude if it exceeds timeout
    ( sleep "$TIMEOUT_SECS" && kill "$CLAUDE_PID" 2>/dev/null ) &
    local WATCHDOG_PID=$!

    wait "$CLAUDE_PID" 2>/dev/null
    local EXIT_CODE=$?
    kill "$WATCHDOG_PID" 2>/dev/null 2>&1
    wait "$WATCHDOG_PID" 2>/dev/null || true

    local attempt_end
    attempt_end=$(date +%s)
    local attempt_duration=$((attempt_end - attempt_start))

    # Detect timeout: if duration >= TIMEOUT_SECS and non-zero exit
    if (( attempt_duration >= TIMEOUT_SECS )) && (( EXIT_CODE != 0 )); then
      timed_out=true
      echo "[dispatcher] Attempt ${attempt} timed out after ${TIMEOUT_RAW} limit (exit code ${EXIT_CODE})"
    elif (( EXIT_CODE != 0 )); then
      echo "[dispatcher] Attempt ${attempt} failed with exit code ${EXIT_CODE} after $(format_duration $attempt_duration)"
    fi

    final_exit_code=$EXIT_CODE

    if (( EXIT_CODE == 0 )); then
      final_result="success"
      break
    fi

    # Don't retry on timeout if this was the last attempt
    if (( attempt < MAX_ATTEMPTS )); then
      echo "[dispatcher] Retrying..."
    fi
  done

  local job_end_epoch
  job_end_epoch=$(date +%s)
  local total_duration=$((job_end_epoch - job_start_epoch))

  if [[ "$final_result" != "success" ]] && [[ "$timed_out" == "true" ]]; then
    final_result="timeout"
  fi

  echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] ${label_prefix}END: ${JOB_NAME} ($(format_duration $total_duration)) [${final_result}] ==="

  # Write status file
  write_job_status "$STATUS_FILE" "$final_result" "$total_duration" "$final_exit_code"

  # Send notification based on notify setting
  local subtitle_prefix=""
  [[ -n "$catchup_label" ]] && subtitle_prefix=" ${catchup_label}"

  local should_notify_success=false
  local should_notify_failure=false
  case "$NOTIFY" in
    on_finish)  should_notify_success=true; should_notify_failure=true ;;
    on_success) should_notify_success=true ;;
    on_failure) should_notify_failure=true ;;
    silent)     ;;
  esac

  if [[ "$final_result" == "success" ]] && [[ "$should_notify_success" == "true" ]]; then
    send_notification "Organon" "✓ ${JOB_NAME}${subtitle_prefix}" "Completed in $(format_duration $total_duration)"
  elif [[ "$final_result" == "timeout" ]] && [[ "$should_notify_failure" == "true" ]]; then
    send_notification "Organon" "✗ ${JOB_NAME} timed out${subtitle_prefix}" "Killed after ${TIMEOUT_RAW} limit"
  elif [[ "$final_result" != "success" ]] && [[ "$should_notify_failure" == "true" ]]; then
    send_notification "Organon" "✗ ${JOB_NAME} failed${subtitle_prefix}" "Exit code ${final_exit_code} after $(format_duration $total_duration)"
  fi
}

# ---------------------------------------------------------------------------
# Catch-up: detect gaps and re-run missed fixed-time jobs
# ---------------------------------------------------------------------------

catch_up_missed_jobs() {
  local dispatcher_status="${STATUS_DIR}/dispatcher.json"
  [[ -f "$dispatcher_status" ]] || return 0

  local last_dispatch
  last_dispatch=$(read_status_field "$dispatcher_status" "last_dispatch")
  [[ -z "$last_dispatch" ]] && return 0

  # Convert ISO timestamp to epoch. macOS date -j vs GNU date.
  local last_epoch
  if date -j -f "%Y-%m-%dT%H:%M:%SZ" "$last_dispatch" +%s &>/dev/null 2>&1; then
    last_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$last_dispatch" +%s 2>/dev/null)
  elif date -d "$last_dispatch" +%s &>/dev/null 2>&1; then
    last_epoch=$(date -d "$last_dispatch" +%s 2>/dev/null)
  else
    return 0
  fi

  local gap=$((NOW_EPOCH - last_epoch))
  # Only catch up if gap > 120 seconds
  (( gap <= 120 )) && return 0

  # Cap catch-up at 24 hours
  local max_gap=86400
  local effective_start=$last_epoch
  if (( gap > max_gap )); then
    effective_start=$((NOW_EPOCH - max_gap))
  fi

  # Track which jobs we've already caught up to deduplicate
  local caught_up_jobs=""

  for file in "${CRONS_DIR}"/*.md; do
    [[ -f "$file" ]] || continue

    local ACTIVE SCHED_TIME SCHED_DAYS
    ACTIVE=$(awk '/^---/{n++; next} n==1 && /^active:/{gsub(/[" ]/, "", $2); print $2}' "$file")
    [[ "$ACTIVE" == "false" ]] && continue

    SCHED_TIME=$(awk '/^---/{n++; next} n==1 && /^time:/{gsub(/[" ]/, "", $2); print $2}' "$file")
    SCHED_DAYS=$(awk '/^---/{n++; next} n==1 && /^days:/{gsub(/[" ]/, "", $2); print $2}' "$file")

    # Only catch up fixed-time jobs, not intervals
    is_fixed_time "$SCHED_TIME" || continue

    local job_basename
    job_basename=$(basename "$file" .md)

    # Deduplicate: only catch up each job once per gap
    [[ "$caught_up_jobs" == *"|${job_basename}|"* ]] && continue

    # Check each fixed time in the schedule
    local missed=false
    IFS=',' read -ra FIXED_TIMES <<< "$SCHED_TIME"
    for ft in "${FIXED_TIMES[@]}"; do
      ft=$(echo "$ft" | tr -d ' ')
      local ft_hour="${ft%%:*}"
      local ft_min="${ft##*:}"

      # Walk each day in the gap and check if this time was missed
      local check_epoch=$effective_start
      while (( check_epoch < NOW_EPOCH )); do
        # Get the date components for this epoch
        local check_day check_hhmm check_time_epoch
        if date -j -f "%s" "$check_epoch" +%a &>/dev/null 2>&1; then
          check_day=$(date -j -f "%s" "$check_epoch" +%a | tr '[:upper:]' '[:lower:]')
          # Build epoch for the scheduled time on this day
          local check_date_str
          check_date_str=$(date -j -f "%s" "$check_epoch" +%Y-%m-%d)
          check_time_epoch=$(date -j -f "%Y-%m-%d %H:%M" "${check_date_str} ${ft}" +%s 2>/dev/null) || { check_epoch=$((check_epoch + 86400)); continue; }
        else
          check_day=$(date -d "@${check_epoch}" +%a | tr '[:upper:]' '[:lower:]')
          local check_date_str
          check_date_str=$(date -d "@${check_epoch}" +%Y-%m-%d)
          check_time_epoch=$(date -d "${check_date_str} ${ft}" +%s 2>/dev/null) || { check_epoch=$((check_epoch + 86400)); continue; }
        fi

        # Was this scheduled time in the gap?
        if (( check_time_epoch > effective_start )) && (( check_time_epoch < NOW_EPOCH )); then
          # Check day filter
          local day_ok=true
          case "$SCHED_DAYS" in
            daily) ;;
            weekdays) [[ "$check_day" =~ ^(sat|sun)$ ]] && day_ok=false ;;
            weekends) [[ ! "$check_day" =~ ^(sat|sun)$ ]] && day_ok=false ;;
            *) echo "$SCHED_DAYS" | tr ',' ' ' | grep -qw "$check_day" || day_ok=false ;;
          esac

          if [[ "$day_ok" == "true" ]]; then
            missed=true
            local missed_time="$ft"
            break 2  # break out of both loops — we only need one miss to trigger catch-up
          fi
        fi

        check_epoch=$((check_epoch + 86400))
      done
    done

    if [[ "$missed" == "true" ]]; then
      caught_up_jobs="${caught_up_jobs}|${job_basename}|"

      local JOB_NAME
      JOB_NAME=$(awk '/^---/{n++; next} n==1 && /^name:/{gsub(/^name: *"?/, ""); gsub(/"$/, ""); print}' "$file")
      JOB_NAME="${JOB_NAME:-${job_basename}}"

      local LOG_FILE="${LOGS_DIR}/${job_basename}.log"
      rotate_log_if_needed "$LOG_FILE"

      echo "=== CATCH-UP: ${JOB_NAME} (missed ${missed_time:-unknown}) ===" >> "$LOG_FILE"

      {
        run_job "$file" "(catch-up)"
      } >> "$LOG_FILE" &
    fi
  done
}

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

# Read previous dispatcher timestamp BEFORE writing the new one (for catch-up)
catch_up_missed_jobs

# Write dispatcher heartbeat
cat > "${STATUS_DIR}/dispatcher.json" <<DISPEOF
{"last_dispatch":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
DISPEOF

# Scan and fire matching jobs
for file in "${CRONS_DIR}"/*.md; do
  [[ -f "$file" ]] || continue

  # Quick active check before full parse
  ACTIVE=$(awk '/^---/{n++; next} n==1 && /^active:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  [[ "$ACTIVE" == "false" ]] && continue

  SCHED_TIME=$(awk '/^---/{n++; next} n==1 && /^time:/{gsub(/[" ]/, "", $2); print $2}' "$file")
  SCHED_DAYS=$(awk '/^---/{n++; next} n==1 && /^days:/{gsub(/[" ]/, "", $2); print $2}' "$file")

  # Check time (supports exact, comma-separated, and intervals)
  time_matches "$SCHED_TIME" || continue

  # Check day
  case "$SCHED_DAYS" in
    daily) ;;
    weekdays) [[ "$NOW_DAY" =~ ^(sat|sun)$ ]] && continue ;;
    weekends) [[ ! "$NOW_DAY" =~ ^(sat|sun)$ ]] && continue ;;
    *) echo "$SCHED_DAYS" | tr ',' ' ' | grep -qw "$NOW_DAY" || continue ;;
  esac

  LOG_FILE="${LOGS_DIR}/$(basename "$file" .md).log"
  rotate_log_if_needed "$LOG_FILE"

  # Fire job in background subshell with full lifecycle management
  {
    run_job "$file" ""
  } >> "$LOG_FILE" &

done

# Wait for all background jobs so launchd doesn't kill orphaned children
wait
