#!/usr/bin/env bash
# setup.sh — Verify Python dependencies for sci-hypothesis skill.
# Checks for scipy (nct distribution), pandas, numpy in the shared venv.
# Does NOT install — directs user to sci-data-analysis/scripts/setup.sh.

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

ALL_OK=true

# Check scipy (specifically nct for power analysis)
if "$PYTHON" -c "from scipy.stats import nct" 2>/dev/null; then
    echo "[OK] scipy (nct distribution) available"
else
    echo "[MISSING] scipy — required for power analysis"
    ALL_OK=false
fi

# Check pandas
if "$PYTHON" -c "import pandas" 2>/dev/null; then
    echo "[OK] pandas available"
else
    echo "[MISSING] pandas — required for data handling"
    ALL_OK=false
fi

# Check numpy
if "$PYTHON" -c "import numpy" 2>/dev/null; then
    echo "[OK] numpy available"
else
    echo "[MISSING] numpy — required for numerical computation"
    ALL_OK=false
fi

if [[ "$ALL_OK" == true ]]; then
    echo "[OK] sci-hypothesis dependencies satisfied"
else
    echo ""
    echo "[ACTION] Missing dependencies. Run the shared venv setup:"
    echo "  bash $REPO_ROOT/.claude/skills/sci-data-analysis/scripts/setup.sh"
    exit 1
fi
