#!/usr/bin/env bash
# Install the Organon Watchdog — registers with macOS launchd
# Runs watchdog.sh every hour in the background, even when Claude Code is closed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_NAME="com.organon.watchdog"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
WATCHDOG_SCRIPT="$REPO_DIR/scripts/watchdog.sh"
LOGS_DIR="$REPO_DIR/cron/logs"
INTERVAL="${1:-3600}"  # Default: 1 hour. Pass seconds as first arg to override.

echo "Organon Watchdog Installer"
echo "==========================="
echo ""

# --- Pre-flight checks ---

# Check claude CLI
if ! command -v claude &>/dev/null; then
  echo "ERROR: 'claude' CLI not found."
  echo "Install it first: https://docs.anthropic.com/en/docs/claude-code"
  exit 1
fi

CLAUDE_BIN_DIR=$(dirname "$(command -v claude)")

# Check watchdog script exists
if [[ ! -f "$WATCHDOG_SCRIPT" ]]; then
  echo "ERROR: watchdog.sh not found at $WATCHDOG_SCRIPT"
  exit 1
fi

chmod +x "$WATCHDOG_SCRIPT"

# Check python3 (needed for YAML parsing)
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. It's needed to parse job files."
  exit 1
fi

# Ensure logs directory exists
mkdir -p "$LOGS_DIR"

# --- Cost estimate ---
echo "Calculating cost estimate..."
ENABLED_JOBS=0
DAILY_COST_LOW=0
DAILY_COST_HIGH=0

for job_file in "$REPO_DIR/cron/jobs/"*.md; do
  [[ -f "$job_file" ]] || continue
  PARSED=$(python3 -c "
import re
content = open('$job_file').read()
match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if not match: exit()
fm = {}
for line in match.group(1).strip().split('\n'):
    if ':' in line:
        k, v = line.split(':', 1)
        fm[k.strip()] = v.strip().strip('\"').strip(\"'\")
if fm.get('enabled','true') == 'false': exit()
if fm.get('schedule','') == 'session_start': exit()
budget = fm.get('max_budget_usd', '0.50')
schedule = fm.get('schedule', 'every_2h')
name = fm.get('name', 'unknown')
intervals = {'every_10m':144,'every_30m':48,'every_1h':24,'every_2h':12,'every_4h':6}
runs_per_day = intervals.get(schedule, 12)
print(f'{name}\t{budget}\t{runs_per_day}')
" 2>/dev/null) || continue

  [[ -z "$PARSED" ]] && continue
  ENABLED_JOBS=$((ENABLED_JOBS + 1))

  IFS=$'\t' read -r JOB_NAME JOB_BUDGET RUNS_PER_DAY <<< "$PARSED"
  # Worst case = budget * runs. Typical = 30% of budget * runs.
  WORST=$(python3 -c "print(round($JOB_BUDGET * $RUNS_PER_DAY, 2))")
  TYPICAL=$(python3 -c "print(round($JOB_BUDGET * $RUNS_PER_DAY * 0.3, 2))")
  echo "  $JOB_NAME: ~\$$TYPICAL - \$$WORST/day ($RUNS_PER_DAY runs/day, \$$JOB_BUDGET cap each)"
  DAILY_COST_LOW=$(python3 -c "print(round($DAILY_COST_LOW + $TYPICAL, 2))")
  DAILY_COST_HIGH=$(python3 -c "print(round($DAILY_COST_HIGH + $WORST, 2))")
done

echo ""
if [[ "$ENABLED_JOBS" -eq 0 ]]; then
  echo "No enabled jobs found in cron/jobs/. The watchdog will install"
  echo "but won't run anything until you create a job."
else
  echo "Estimated daily cost: \$$DAILY_COST_LOW - \$$DAILY_COST_HIGH"
  echo "(Based on $ENABLED_JOBS enabled jobs. Each job has its own spending cap.)"
fi
echo ""

# --- Unload existing plist if present ---
if launchctl list | grep -q "$PLIST_NAME" 2>/dev/null; then
  echo "Removing existing watchdog..."
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

# --- Generate plist ---
cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${WATCHDOG_SCRIPT}</string>
    </array>

    <key>StartInterval</key>
    <integer>${INTERVAL}</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${CLAUDE_BIN_DIR}:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>${REPO_DIR}</string>

    <key>StandardOutPath</key>
    <string>${LOGS_DIR}/watchdog-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${LOGS_DIR}/watchdog-stderr.log</string>

    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
PLIST

# --- Load ---
launchctl load "$PLIST_PATH"

echo "Watchdog installed and running."
echo ""
echo "  Check interval: every $((INTERVAL / 60)) minutes"
echo "  Plist: $PLIST_PATH"
echo "  Logs: $LOGS_DIR/watchdog-*.log"
echo ""
echo "To trigger immediately:  launchctl start $PLIST_NAME"
echo "To uninstall:            bash $REPO_DIR/scripts/uninstall-watchdog.sh"
echo ""
echo "Jobs run using your Claude plan credits. Each job has a spending"
echo "cap (max_budget_usd in the job file) to prevent runaway costs."
