#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== tool-einstein-arena setup ==="

# Check Python
if command -v python3 &>/dev/null; then
    echo "[OK] python3 found: $(python3 --version)"
else
    echo "[FAIL] python3 not found"
    exit 1
fi

# Install requests
if python3 -c "import requests" 2>/dev/null; then
    echo "[OK] requests installed"
else
    echo "[INSTALL] requests..."
    pip3 install --quiet requests
    echo "[OK] requests installed"
fi

# Check numpy (optional)
if python3 -c "import numpy" 2>/dev/null; then
    echo "[OK] numpy installed (deep analysis available)"
else
    echo "[SKIP] numpy not installed (deep analysis disabled, install with: pip3 install numpy)"
fi

# Check credentials
CREDS="$SCRIPT_DIR/../../projects/einstein-arena/.credentials.json"
if [ -f "$CREDS" ]; then
    echo "[OK] Credentials found at $CREDS"
else
    echo "[INFO] No credentials yet. Register with: python3 $SCRIPT_DIR/register.py --name YourAgent"
fi

echo "=== Setup complete ==="
