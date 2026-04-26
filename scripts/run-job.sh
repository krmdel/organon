#!/usr/bin/env bash
# Manual job trigger — run any job by name, ignoring schedule.
# Usage: bash scripts/run-job.sh <job-name>
# Future Telegram bot calls this script to trigger jobs on demand.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/run-job.sh <job-name>"
  echo "  Runs the job immediately, ignoring time/days/active."
  echo ""
  echo "Available jobs:"
  for f in "$(cd "$(dirname "$0")/.." && pwd)/cron/jobs"/*.md; do
    [[ -f "$f" ]] && echo "  $(basename "$f" .md)"
  done
  exit 1
fi

JOB_ARG="$1"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
JOB_FILE="${PROJECT_DIR}/cron/jobs/${JOB_ARG}.md"
LOGS_DIR="${PROJECT_DIR}/cron/logs"
STATUS_DIR="${PROJECT_DIR}/cron/status"

if [[ ! -f "$JOB_FILE" ]]; then
  echo "Error: No job file at ${JOB_FILE}"
  exit 1
fi

mkdir -p "$LOGS_DIR" "$STATUS_DIR"

# --- Parse YAML frontmatter ---
JOB_NAME=$(awk '/^---/{n++; next} n==1 && /^name:/{gsub(/^name: *"?/, ""); gsub(/"$/, ""); print}' "$JOB_FILE")
JOB_NAME="${JOB_NAME:-$JOB_ARG}"
MODEL=$(awk '/^---/{n++; next} n==1 && /^model:/{gsub(/[" ]/, "", $2); print $2}' "$JOB_FILE")
MODEL="${MODEL:-sonnet}"
NOTIFY=$(awk '/^---/{n++; next} n==1 && /^notify:/{gsub(/[" ]/, "", $2); print $2}' "$JOB_FILE")
NOTIFY="${NOTIFY:-on_finish}"
TIMEOUT_RAW=$(awk '/^---/{n++; next} n==1 && /^timeout:/{gsub(/[" ]/, "", $2); print $2}' "$JOB_FILE")
TIMEOUT_RAW="${TIMEOUT_RAW:-30m}"
RETRY=$(awk '/^---/{n++; next} n==1 && /^retry:/{gsub(/[" ]/, "", $2); print $2}' "$JOB_FILE")
RETRY="${RETRY:-0}"

PROMPT=$(awk 'BEGIN{n=0} /^---/{n++; next} n>=2{print}' "$JOB_FILE")

if [[ -z "$PROMPT" ]]; then
  echo "Error: No prompt body found in ${JOB_FILE}"
  exit 1
fi

# --- Helper functions ---

send_notification() {
  local title="$1" subtitle="$2" body="$3"
  if [[ "$(uname)" == "Darwin" ]]; then
    osascript -e "display notification \"$body\" with title \"$title\" subtitle \"$subtitle\" sound name \"default\"" 2>/dev/null || true
  else
    command -v notify-send &>/dev/null && notify-send "$title" "$subtitle: $body" 2>/dev/null || true
  fi
}

parse_timeout() {
  local val="$1"
  if [[ "$val" =~ ^([0-9]+)m$ ]]; then echo $(( ${BASH_REMATCH[1]} * 60 ))
  elif [[ "$val" =~ ^([0-9]+)h$ ]]; then echo $(( ${BASH_REMATCH[1]} * 3600 ))
  elif [[ "$val" =~ ^([0-9]+)s$ ]]; then echo "${BASH_REMATCH[1]}"
  else echo "$val"
  fi
}

format_duration() {
  local secs="$1"
  if (( secs >= 60 )); then
    echo "$(( secs / 60 ))m $(( secs % 60 ))s"
  else
    echo "${secs}s"
  fi
}

TIMEOUT_SECS=$(parse_timeout "$TIMEOUT_RAW")
LOG_FILE="${LOGS_DIR}/${JOB_ARG}.log"
STATUS_FILE="${STATUS_DIR}/${JOB_ARG}.json"

echo "Running job: ${JOB_NAME} (model: ${MODEL}, timeout: ${TIMEOUT_RAW}, retry: ${RETRY})"
echo ""

# --- Read previous status for run_count / fail_count ---
PREV_RUN_COUNT=0
PREV_FAIL_COUNT=0
if [[ -f "$STATUS_FILE" ]]; then
  PREV_RUN_COUNT=$(grep -o '"run_count":[0-9]*' "$STATUS_FILE" 2>/dev/null | grep -o '[0-9]*' || echo 0)
  PREV_FAIL_COUNT=$(grep -o '"fail_count":[0-9]*' "$STATUS_FILE" 2>/dev/null | grep -o '[0-9]*' || echo 0)
fi

# --- Execute with retry loop ---
ATTEMPT=0
MAX_ATTEMPTS=$(( RETRY + 1 ))
EXIT_CODE=1

while (( ATTEMPT < MAX_ATTEMPTS )); do
  ATTEMPT=$((ATTEMPT + 1))

  if (( MAX_ATTEMPTS > 1 )); then
    echo "Attempt ${ATTEMPT}/${MAX_ATTEMPTS}..."
  fi

  {
    echo ""
    echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] MANUAL START: ${JOB_NAME} (attempt ${ATTEMPT}/${MAX_ATTEMPTS}) ==="
    START_TIME=$(date +%s)

    # Launch Claude with timeout watchdog
    env -u CLAUDECODE claude -p "$PROMPT" \
      --model "$MODEL" \
      --dangerously-skip-permissions 2>&1 | tee /dev/stderr &
    CLAUDE_PID=$!

    ( sleep "$TIMEOUT_SECS" && kill "$CLAUDE_PID" 2>/dev/null ) &
    WATCHDOG_PID=$!

    wait "$CLAUDE_PID" 2>/dev/null
    EXIT_CODE=$?
    kill "$WATCHDOG_PID" 2>/dev/null 2>&1 || true
    wait "$WATCHDOG_PID" 2>/dev/null 2>&1 || true

    END_TIME=$(date +%s)
    RUNTIME=$((END_TIME - START_TIME))
    DURATION_HUMAN=$(format_duration "$RUNTIME")

    if (( EXIT_CODE == 0 )); then
      echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] MANUAL END: ${JOB_NAME} (${DURATION_HUMAN}) ==="
    elif (( EXIT_CODE == 137 || EXIT_CODE == 143 )); then
      echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] MANUAL TIMEOUT: ${JOB_NAME} (killed after ${TIMEOUT_RAW}) ==="
    else
      echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] MANUAL FAIL: ${JOB_NAME} (exit ${EXIT_CODE}, ${DURATION_HUMAN}) ==="
    fi
  } >> "$LOG_FILE"

  # Success — break out of retry loop
  if (( EXIT_CODE == 0 )); then
    break
  fi

  # If retries remain, log and continue
  if (( ATTEMPT < MAX_ATTEMPTS )); then
    echo "Attempt ${ATTEMPT} failed (exit ${EXIT_CODE}). Retrying..."
    {
      echo "[run-job] Attempt ${ATTEMPT} failed (exit ${EXIT_CODE}). Retrying..."
    } >> "$LOG_FILE"
  fi
done

# --- Write status file ---
END_TIME=$(date +%s)
RUNTIME=$((END_TIME - START_TIME))
DURATION_HUMAN=$(format_duration "$RUNTIME")
NEW_RUN_COUNT=$((PREV_RUN_COUNT + 1))
NEW_FAIL_COUNT=$PREV_FAIL_COUNT
RESULT="success"

if (( EXIT_CODE != 0 )); then
  NEW_FAIL_COUNT=$((PREV_FAIL_COUNT + 1))
  if (( EXIT_CODE == 137 || EXIT_CODE == 143 )); then
    RESULT="timeout"
  else
    RESULT="failure"
  fi
fi

cat > "$STATUS_FILE" <<STATUSEOF
{"last_run":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","result":"${RESULT}","duration":${RUNTIME},"exit_code":${EXIT_CODE},"run_count":${NEW_RUN_COUNT},"fail_count":${NEW_FAIL_COUNT}}
STATUSEOF

# --- Send notification based on notify field ---
NOTIFY_SUCCESS=false
NOTIFY_FAILURE=false
case "$NOTIFY" in
  on_finish)  NOTIFY_SUCCESS=true; NOTIFY_FAILURE=true ;;
  on_success) NOTIFY_SUCCESS=true ;;
  on_failure) NOTIFY_FAILURE=true ;;
  silent)     ;;
esac

if (( EXIT_CODE == 0 )) && [[ "$NOTIFY_SUCCESS" == "true" ]]; then
  send_notification "Organon" "✓ ${JOB_NAME}" "Completed in ${DURATION_HUMAN}"
elif [[ "$RESULT" == "timeout" ]] && [[ "$NOTIFY_FAILURE" == "true" ]]; then
  send_notification "Organon" "✗ ${JOB_NAME} timed out" "Killed after ${TIMEOUT_RAW} limit"
elif (( EXIT_CODE != 0 )) && [[ "$NOTIFY_FAILURE" == "true" ]]; then
  send_notification "Organon" "✗ ${JOB_NAME} failed" "Exit code ${EXIT_CODE} after ${DURATION_HUMAN}"
fi

exit $EXIT_CODE
