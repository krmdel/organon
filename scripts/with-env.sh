#!/usr/bin/env bash
# =============================================================================
# with-env.sh — source repo .env then exec the given command
# =============================================================================
# Used by .mcp.json to give MCP servers access to secrets in .env without
# requiring the user to export them in their shell rc before launching claude.
#
# Usage (from .mcp.json, cwd = repo root):
#   "command": "bash"
#   "args": ["scripts/with-env.sh", "node", "mcp-servers/foo/dist/index.js"]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

exec "$@"
