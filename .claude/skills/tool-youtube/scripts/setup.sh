#!/bin/bash
# tool-youtube setup: detect and install uv + yt-dlp
set -e

echo "=== tool-youtube: checking dependencies ==="
echo ""

MISSING=0

# ── uv ──────────────────────────────────────────────────────────────────
if command -v uv &>/dev/null; then
    echo "  uv ............ installed ($(uv --version 2>/dev/null || echo 'ok'))"
else
    echo "  uv ............ not found — installing..."
    if command -v brew &>/dev/null; then
        brew install uv
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi

    if command -v uv &>/dev/null; then
        echo "  uv ............ installed"
    else
        echo "  uv ............ FAILED (try: brew install uv)"
        MISSING=1
    fi
fi

# ── yt-dlp ──────────────────────────────────────────────────────────────
if command -v yt-dlp &>/dev/null; then
    echo "  yt-dlp ........ installed ($(yt-dlp --version 2>/dev/null || echo 'ok'))"
else
    echo "  yt-dlp ........ not found — installing..."
    if command -v brew &>/dev/null; then
        brew install yt-dlp
    else
        pip install yt-dlp 2>/dev/null || pip3 install yt-dlp
    fi

    if command -v yt-dlp &>/dev/null; then
        echo "  yt-dlp ........ installed"
    else
        echo "  yt-dlp ........ FAILED (try: brew install yt-dlp)"
        MISSING=1
    fi
fi

echo ""
if [ "$MISSING" -eq 0 ]; then
    echo "=== All dependencies ready ==="
else
    echo "=== Some dependencies failed — see above ==="
    exit 1
fi
