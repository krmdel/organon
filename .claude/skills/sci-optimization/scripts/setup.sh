#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== sci-optimization setup ==="

# Check Python
if command -v python3 &>/dev/null; then
    echo "[OK] python3 found: $(python3 --version)"
else
    echo "[FAIL] python3 not found"
    exit 1
fi

# Required: numpy
if python3 -c "import numpy" 2>/dev/null; then
    echo "[OK] numpy installed"
else
    echo "[INSTALL] numpy..."
    pip3 install --quiet numpy
    echo "[OK] numpy installed"
fi

# Required: scipy
if python3 -c "import scipy" 2>/dev/null; then
    echo "[OK] scipy installed"
else
    echo "[INSTALL] scipy..."
    pip3 install --quiet scipy
    echo "[OK] scipy installed"
fi

# Optional: sympy
if python3 -c "import sympy" 2>/dev/null; then
    echo "[OK] sympy installed (symbolic math available)"
else
    echo "[SKIP] sympy not installed (optional, install with: pip3 install sympy)"
fi

echo "=== Setup complete ==="
