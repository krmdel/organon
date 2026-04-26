#!/usr/bin/env bash
# setup.sh — Install missing Python dependencies for sci-data-analysis skill.
# Checks for SciencePlots and openpyxl; installs via uv if absent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Determine Python path
if [[ -f "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "[ERROR] No Python found. Install Python 3.10+ or create a venv."
    exit 1
fi

NEED_INSTALL=()

# Check SciencePlots
if "$PYTHON" -c "import scienceplots" 2>/dev/null; then
    echo "[OK] SciencePlots already installed"
else
    echo "[MISSING] SciencePlots — will install"
    NEED_INSTALL+=("SciencePlots")
fi

# Check openpyxl
if "$PYTHON" -c "import openpyxl" 2>/dev/null; then
    echo "[OK] openpyxl already installed"
else
    echo "[MISSING] openpyxl — will install"
    NEED_INSTALL+=("openpyxl")
fi

if [[ ${#NEED_INSTALL[@]} -gt 0 ]]; then
    echo "[INSTALL] Installing: ${NEED_INSTALL[*]}"
    source "$REPO_ROOT/.venv/bin/activate"
    uv pip install "${NEED_INSTALL[@]}"
    echo "[DONE] Dependencies installed successfully"
else
    echo "[DONE] All dependencies already present"
fi
