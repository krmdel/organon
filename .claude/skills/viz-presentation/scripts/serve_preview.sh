#!/usr/bin/env bash
# Serve a directory over HTTP for Marp preview.
# Idempotent: reuses an existing viz-presentation server on the requested dir, else starts a new one.
# Auto-falls back to a higher port if the requested port is held by an external process.
#
# Usage:
#   serve_preview.sh <dir>           # tries port 8765
#   serve_preview.sh <dir> <port>    # tries given port, falls back upward if taken
#
# Prints the URL root on stdout.

set -euo pipefail

DIR="${1:?need a directory to serve}"
START_PORT="${2:-8765}"
MAX_PORT=$((START_PORT + 20))
LOCK_DIR="${TMPDIR:-/tmp}/viz-presentation-serve"

mkdir -p "$LOCK_DIR"
ABS_DIR="$(cd "$DIR" && pwd)"

port_is_ours() {
  local port="$1"
  local lock="${LOCK_DIR}/port-${port}.lock"
  [[ -f "$lock" ]] || return 1
  read -r pid dir < "$lock" || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  [[ "$dir" == "$ABS_DIR" ]]
}

port_held_externally() {
  local port="$1"
  local listener
  listener=$(lsof -ti:"$port" 2>/dev/null | head -1 || true)
  [[ -n "$listener" ]]
}

start_server_on() {
  local port="$1"
  local lock="${LOCK_DIR}/port-${port}.lock"
  python3 -m http.server "$port" --directory "$ABS_DIR" > "$LOCK_DIR/port-${port}.log" 2>&1 &
  local pid=$!
  echo "$pid $ABS_DIR" > "$lock"
  sleep 0.4
  if kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  rm -f "$lock"
  return 1
}

# 1. Reuse an existing viz-presentation server for this exact dir (any port in range)
for ((p = START_PORT; p <= MAX_PORT; p++)); do
  if port_is_ours "$p"; then
    echo "http://localhost:${p}"
    exit 0
  fi
done

# 2. Try to start on START_PORT. If held externally, walk upward.
for ((p = START_PORT; p <= MAX_PORT; p++)); do
  if port_held_externally "$p"; then
    # If it's one of our stale locks, clean it up and try again
    if [[ -f "$LOCK_DIR/port-${p}.lock" ]]; then
      read -r stale_pid _ < "$LOCK_DIR/port-${p}.lock" 2>/dev/null || true
      if [[ -n "${stale_pid:-}" ]] && kill -0 "$stale_pid" 2>/dev/null; then
        # Different dir, but it's ours. Kill it.
        kill "$stale_pid" 2>/dev/null || true
        sleep 0.3
      fi
      rm -f "$LOCK_DIR/port-${p}.lock"
    fi
    # Re-check
    port_held_externally "$p" && continue
  fi
  if start_server_on "$p"; then
    echo "http://localhost:${p}"
    exit 0
  fi
done

echo "ERROR: no free port in range ${START_PORT}-${MAX_PORT}" >&2
exit 1
