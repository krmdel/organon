#!/usr/bin/env bash
# Setup script for sci-writing skill
# Checks Python venv and required modules (stdlib only -- no new deps)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
VENV="$REPO_ROOT/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "[ERROR] Python venv not found at $VENV"
    echo "Run: cd $REPO_ROOT && bash scripts/install.sh"
    exit 1
fi

echo "[OK] Python venv found"
echo "[OK] sci-writing uses stdlib only -- no additional packages needed"
echo "[OK] Setup complete"
