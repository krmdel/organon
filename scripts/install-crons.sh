#!/usr/bin/env bash
# Install the cron dispatcher via launchd (macOS) or crontab (Linux).
# For Windows, use install-crons.ps1.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DISPATCHER="${PROJECT_DIR}/scripts/run-crons.sh"

# Derive a unique slug from the project directory name for multi-client support
PROJECT_SLUG=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
PLIST_NAME="com.organon.${PROJECT_SLUG}"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_NAME}.plist"

# Pre-flight checks
if ! command -v claude &>/dev/null; then
  echo "Error: 'claude' CLI not found. Install Claude Code first."
  exit 1
fi

# macOS: check if project is in a protected folder
if [[ "$(uname)" == "Darwin" ]]; then
  PROTECTED_DIRS=("${HOME}/Desktop" "${HOME}/Documents" "${HOME}/Downloads")
  for dir in "${PROTECTED_DIRS[@]}"; do
    if [[ "$PROJECT_DIR" == "$dir"* ]]; then
      FOLDER_NAME=$(basename "$dir")
      echo "Error: Your project is inside ~/${FOLDER_NAME}/"
      echo ""
      echo "  macOS blocks background processes from accessing Desktop,"
      echo "  Documents, and Downloads. The cron dispatcher won't be"
      echo "  able to run your jobs from this location."
      echo ""
      echo "  Move your project to a non-protected folder, e.g.:"
      echo ""
      echo "    mv ${PROJECT_DIR} ~/Projects/$(basename "$PROJECT_DIR")"
      echo ""
      echo "  Then cd into the new location and run this script again / ask claude code to run it again."
      exit 1
    fi
  done
fi

if [[ ! -x "$DISPATCHER" ]]; then
  chmod +x "$DISPATCHER"
fi

# Count enabled jobs
ENABLED=0
for f in "${PROJECT_DIR}/cron/jobs"/*.md; do
  [[ -f "$f" ]] || continue
  ACTIVE=$(awk '/^---/{n++; next} n==1 && /^active:/{gsub(/[" ]/, "", $2); print $2}' "$f")
  [[ "$ACTIVE" != "false" ]] && ENABLED=$((ENABLED + 1))
done

# macOS — use launchd
if [[ "$(uname)" == "Darwin" ]]; then

  # Check if already installed
  if [[ -f "$PLIST_PATH" ]]; then
    echo "Cron dispatcher is already installed."
    echo "  Plist: ${PLIST_PATH}"
    echo "  ${ENABLED} enabled job(s)."
    exit 0
  fi

  mkdir -p "${HOME}/Library/LaunchAgents"

  cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_NAME}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${DISPATCHER}</string>
  </array>
  <key>StartInterval</key>
  <integer>60</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>
  <key>StandardOutPath</key>
  <string>${PROJECT_DIR}/cron/logs/dispatcher-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${PROJECT_DIR}/cron/logs/dispatcher-stderr.log</string>
</dict>
</plist>
PLIST

  launchctl load "$PLIST_PATH"

  echo "Cron dispatcher installed (launchd)."
  echo "  Runs every 60 seconds."
  echo "  ${ENABLED} enabled job(s) found."
  echo "  Logs: cron/logs/"
  echo ""
  echo "To remove: bash scripts/uninstall-crons.sh"

# Linux — use crontab
else

  CRON_LINE="* * * * * ${DISPATCHER}"
  EXISTING=$(crontab -l 2>/dev/null || true)

  if echo "$EXISTING" | grep -qF "$DISPATCHER"; then
    echo "Cron dispatcher is already installed."
    echo "  ${ENABLED} enabled job(s)."
    exit 0
  fi

  (echo "$EXISTING"; echo "$CRON_LINE") | crontab -

  echo "Cron dispatcher installed (crontab)."
  echo "  Runs every 60 seconds."
  echo "  ${ENABLED} enabled job(s) found."
  echo "  Logs: cron/logs/"
  echo ""
  echo "To remove: bash scripts/uninstall-crons.sh"

fi
