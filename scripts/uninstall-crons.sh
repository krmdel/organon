#!/usr/bin/env bash
# Remove the cron dispatcher. Job files are left untouched.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DISPATCHER="${PROJECT_DIR}/scripts/run-crons.sh"

# Derive the same slug used during install
PROJECT_SLUG=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
PLIST_NAME="com.organon.${PROJECT_SLUG}"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_NAME}.plist"

# macOS — unload launchd plist
if [[ "$(uname)" == "Darwin" ]]; then

  if [[ ! -f "$PLIST_PATH" ]]; then
    echo "Cron dispatcher is not installed. Nothing to remove."
    exit 0
  fi

  launchctl unload "$PLIST_PATH" 2>/dev/null || true
  rm -f "$PLIST_PATH"

  echo "Cron dispatcher removed."
  echo "Your job files in cron/jobs/ are still there — they just won't run automatically."

# Linux — remove crontab entry
else

  EXISTING=$(crontab -l 2>/dev/null || true)

  if ! echo "$EXISTING" | grep -qF "$DISPATCHER"; then
    echo "Cron dispatcher is not installed. Nothing to remove."
    exit 0
  fi

  echo "$EXISTING" | grep -vF "$DISPATCHER" | crontab -

  echo "Cron dispatcher removed."
  echo "Your job files in cron/jobs/ are still there — they just won't run automatically."

fi
