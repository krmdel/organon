#!/usr/bin/env bash
# Setup script for viz-figure-mirror.
# Verifies the two required Python packages (matplotlib, pillow) are importable in
# the Organon venv and installs them via pip only if missing. Idempotent, no user
# interaction, safe to run once per machine.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
VENV="$REPO_ROOT/.venv"

if [[ -d "$VENV" ]]; then
    PY="$VENV/bin/python"
    echo "[OK] Python venv found at $VENV"
else
    PY="$(command -v python3 || true)"
    if [[ -z "$PY" ]]; then
        echo "[ERROR] No Python venv at $VENV and no python3 on PATH."
        echo "        Run: cd $REPO_ROOT && bash scripts/install.sh"
        exit 1
    fi
    echo "[WARN] No Organon venv; falling back to system python3 ($PY)."
fi

missing=()
for spec in "matplotlib:matplotlib" "pillow:PIL"; do
    pkg="${spec%%:*}"; mod="${spec##*:}"
    if "$PY" -c "import ${mod}" >/dev/null 2>&1; then
        echo "[OK] ${pkg} is importable"
    else
        echo "[..] ${pkg} missing -- will install"
        missing+=("$pkg")
    fi
done

if (( ${#missing[@]} > 0 )); then
    echo "[..] pip install ${missing[*]}"
    "$PY" -m pip install --quiet "${missing[@]}"
    for spec in "matplotlib:matplotlib" "pillow:PIL"; do
        pkg="${spec%%:*}"; mod="${spec##*:}"
        if "$PY" -c "import ${mod}" >/dev/null 2>&1; then
            echo "[OK] ${pkg} now importable"
        else
            echo "[ERROR] ${pkg} still not importable after install"
            exit 1
        fi
    done
fi

echo "[OK] viz-figure-mirror setup complete (matplotlib + pillow ready)"
