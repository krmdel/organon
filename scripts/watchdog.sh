#!/usr/bin/env bash
# Organon Watchdog — runs scheduled jobs outside Claude Code sessions
# Called by launchd (Mac) or Task Scheduler (Windows) every hour.
# Each job execution is a standalone `claude -p` call — stateless, self-contained.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
JOBS_DIR="$REPO_DIR/cron/jobs"
LOGS_DIR="$REPO_DIR/cron/logs"
STATE_FILE="$REPO_DIR/cron/watchdog.state.json"
LOCK_FILE="$REPO_DIR/cron/.watchdog.lock"

# Schedule intervals in seconds (bash 3.2 compatible — no associative arrays)
get_interval() {
  case "$1" in
    every_10m) echo 600 ;;
    every_30m) echo 1800 ;;
    every_1h)  echo 3600 ;;
    every_2h)  echo 7200 ;;
    every_4h)  echo 14400 ;;
    *)         echo 0 ;;
  esac
}

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

cleanup() {
  rm -f "$LOCK_FILE"
}

# --- Lock check ---
if [[ -f "$LOCK_FILE" ]]; then
  OLD_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    log "Another watchdog is running (PID $OLD_PID). Exiting."
    exit 0
  fi
  log "Stale lock found (PID $OLD_PID). Removing."
  rm -f "$LOCK_FILE"
fi

echo $$ > "$LOCK_FILE"
trap cleanup EXIT

# --- Ensure directories exist ---
mkdir -p "$LOGS_DIR"

# --- Check claude CLI ---
if ! command -v claude &>/dev/null; then
  log "ERROR: 'claude' CLI not found on PATH. Install it or add it to your PATH."
  exit 1
fi

# --- Init state file ---
if [[ ! -f "$STATE_FILE" ]]; then
  echo '{}' > "$STATE_FILE"
fi

# --- Parse YAML frontmatter with python3 ---
parse_frontmatter() {
  local file="$1"
  python3 -c "
import sys, re

content = open('$file').read()
match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if not match:
    sys.exit(1)

fm = {}
for line in match.group(1).strip().split('\n'):
    if ':' in line:
        key, val = line.split(':', 1)
        val = val.strip().strip('\"').strip(\"'\")
        if val == 'null':
            val = ''
        if val == 'true':
            val = 'true'
        if val == 'false':
            val = 'false'
        fm[key.strip()] = val

# Print tab-separated: name, schedule, model, max_budget, enabled
print('\t'.join([
    fm.get('name', ''),
    fm.get('schedule', ''),
    fm.get('model', 'sonnet'),
    fm.get('max_budget_usd', '0.50'),
    fm.get('enabled', 'true'),
]))
"
}

# --- Extract prompt body (everything after second ---) ---
get_prompt() {
  local file="$1"
  python3 -c "
import re
content = open('$file').read()
match = re.match(r'^---.*?---\s*\n', content, re.DOTALL)
if match:
    print(content[match.end():].strip())
"
}

# --- Get last run time from state ---
get_last_run() {
  local job_name="$1"
  python3 -c "
import json
state = json.load(open('$STATE_FILE'))
print(state.get('$job_name', {}).get('last_run', '0'))
"
}

# --- Update state with new run time ---
update_state() {
  local job_name="$1"
  local timestamp="$2"
  python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['$job_name'] = {'last_run': '$timestamp'}
json.dump(state, open('$STATE_FILE', 'w'), indent=2)
"
}

# --- Main loop through jobs ---
log "Watchdog scanning $JOBS_DIR"

if [[ ! -d "$JOBS_DIR" ]]; then
  log "No jobs directory found. Nothing to do."
  exit 0
fi

JOB_COUNT=0
RUN_COUNT=0

for job_file in "$JOBS_DIR"/*.md; do
  [[ -f "$job_file" ]] || continue

  # Parse frontmatter
  PARSED=$(parse_frontmatter "$job_file" 2>/dev/null) || {
    log "WARN: Could not parse $job_file — skipping"
    continue
  }

  IFS=$'\t' read -r NAME SCHEDULE MODEL BUDGET ENABLED <<< "$PARSED"

  # Skip disabled jobs
  if [[ "$ENABLED" != "true" ]]; then
    continue
  fi

  # Skip session_start jobs (these only run inside interactive sessions)
  if [[ "$SCHEDULE" == "session_start" ]]; then
    continue
  fi

  JOB_COUNT=$((JOB_COUNT + 1))

  # Check if job is due
  INTERVAL=$(get_interval "$SCHEDULE")
  if [[ "$INTERVAL" -eq 0 ]]; then
    log "WARN: Unknown schedule '$SCHEDULE' for $NAME — skipping"
    continue
  fi

  LAST_RUN=$(get_last_run "$NAME")
  NOW=$(date +%s)
  ELAPSED=$((NOW - LAST_RUN))

  if [[ "$ELAPSED" -lt "$INTERVAL" ]]; then
    REMAINING=$(( (INTERVAL - ELAPSED) / 60 ))
    log "$NAME: not due yet (${REMAINING}m remaining)"
    continue
  fi

  # --- Execute the job ---
  log "$NAME: RUNNING (model=$MODEL, budget=\$$BUDGET)"
  RUN_COUNT=$((RUN_COUNT + 1))

  PROMPT=$(get_prompt "$job_file")
  TODAY=$(date +%Y-%m-%d)
  LOG_FILE="$LOGS_DIR/${NAME}_${TODAY}.log"

  # Run claude headlessly
  {
    echo "=== Run at $(date '+%Y-%m-%d %H:%M:%S') ==="
    claude -p "$PROMPT" \
      --model "$MODEL" \
      --max-turns 25 \
      --allowedTools "Read,Write,Edit,Bash,Glob,Grep,WebSearch,WebFetch" \
      2>&1 || echo "[watchdog] claude exited with code $?"
    echo ""
    echo "=== End run ==="
    echo ""
  } >> "$LOG_FILE"

  # Update state
  update_state "$NAME" "$NOW"
  log "$NAME: completed. Log at $LOG_FILE"
done

log "Done. $JOB_COUNT enabled jobs found, $RUN_COUNT executed."
