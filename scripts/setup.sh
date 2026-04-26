#!/usr/bin/env bash
set -uo pipefail
# Note: intentionally NOT using set -e here.
# We want to continue past individual install failures
# and report them all at the end, not bail on the first one.

# Organon — System Setup
# Installs CLI dependencies needed by skills in this repo.
# Called automatically by install.sh. Can also be run standalone:
#   bash scripts/setup.sh
#
# Supports macOS (brew) and Windows (winget/choco/pip).

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { printf "${GREEN}  ✓ %s${NC}\n" "$1"; }
warn() { printf "${YELLOW}  → %s${NC}\n" "$1"; }
fail() { printf "${RED}  ✗ %s${NC}\n" "$1"; }

installed() { command -v "$1" &>/dev/null; }

# ---------- Resolve paths ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) REPO_ROOT="$(cygpath -m "$REPO_ROOT")" ;; esac

# ---------- Detect OS ----------
OS="unknown"
case "$(uname -s)" in
    Darwin*)          OS="mac" ;;
    MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
    Linux*)           OS="linux" ;;
esac

echo ""
echo "========================================="
echo "  Organon — Dependency Setup"
echo "========================================="
echo ""
printf "  Platform: %s\n" "$OS"
echo ""

ERRORS=0

# ---------- Package manager check ----------
if [[ "$OS" == "mac" ]]; then
    printf "Checking brew... "
    if installed brew; then
        ok "brew found"
    else
        fail "brew not found — install from https://brew.sh"
        ERRORS=$((ERRORS + 1))
    fi
elif [[ "$OS" == "windows" ]]; then
    printf "Checking package manager... "
    if installed winget; then
        ok "winget found"
        WIN_PKG="winget"
    elif installed choco; then
        ok "choco found"
        WIN_PKG="choco"
    else
        warn "No package manager found (winget or choco). Some auto-installs may fail."
        WIN_PKG=""
    fi
fi

# ---------- Python 3 ----------
printf "Checking python3... "
if installed python3; then
    ok "python3 $(python3 --version 2>&1 | awk '{print $2}')"
elif installed python; then
    # Windows often has 'python' not 'python3'
    PY_VER=$(python --version 2>&1 | awk '{print $2}')
    case "$PY_VER" in
        3.*) ok "python $PY_VER (as 'python')" ;;
        *)   fail "python found but it's version $PY_VER — need Python 3"
             fail "Install Python 3: https://www.python.org/downloads/"
             ERRORS=$((ERRORS + 1)) ;;
    esac
else
    fail "python3 not found"
    fail "Install Python 3: https://www.python.org/downloads/"
    ERRORS=$((ERRORS + 1))
fi

# ---------- uv (Python package manager) ----------
printf "Checking uv... "
if installed uv; then
    ok "uv $(uv --version 2>&1 | awk '{print $2}')"
else
    warn "Installing uv..."
    if [[ "$OS" == "mac" ]] && installed brew; then
        brew install uv && ok "uv installed" || { fail "uv install failed"; ERRORS=$((ERRORS + 1)); }
    elif [[ "$OS" == "windows" ]] && [[ "${WIN_PKG:-}" == "winget" ]]; then
        winget install --id astral-sh.uv -e --silent && ok "uv installed" || { fail "uv install failed"; ERRORS=$((ERRORS + 1)); }
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh && ok "uv installed" || { fail "uv install failed"; ERRORS=$((ERRORS + 1)); }
    fi
fi

# ---------- yt-dlp (YouTube transcripts) ----------
printf "Checking yt-dlp... "
if installed yt-dlp; then
    ok "yt-dlp found"
else
    warn "Installing yt-dlp..."
    if [[ "$OS" == "mac" ]] && installed brew; then
        brew install yt-dlp && ok "yt-dlp installed" || { fail "yt-dlp install failed"; ERRORS=$((ERRORS + 1)); }
    elif [[ "$OS" == "windows" ]] && [[ "${WIN_PKG:-}" == "winget" ]]; then
        winget install --id yt-dlp.yt-dlp -e --silent && ok "yt-dlp installed" || { fail "yt-dlp install failed"; ERRORS=$((ERRORS + 1)); }
    elif installed pip3; then
        pip3 install yt-dlp && ok "yt-dlp installed" || { fail "yt-dlp install failed"; ERRORS=$((ERRORS + 1)); }
    elif installed pip; then
        pip install yt-dlp && ok "yt-dlp installed" || { fail "yt-dlp install failed"; ERRORS=$((ERRORS + 1)); }
    else
        fail "Cannot install yt-dlp — need pip or a package manager"; ERRORS=$((ERRORS + 1))
    fi
fi

# ---------- ffmpeg (video processing) ----------
printf "Checking ffmpeg... "
if installed ffmpeg; then
    ok "ffmpeg found"
else
    warn "Installing ffmpeg..."
    if [[ "$OS" == "mac" ]] && installed brew; then
        brew install ffmpeg && ok "ffmpeg installed" || { fail "ffmpeg install failed"; ERRORS=$((ERRORS + 1)); }
    elif [[ "$OS" == "windows" ]] && [[ "${WIN_PKG:-}" == "winget" ]]; then
        winget install --id Gyan.FFmpeg -e --silent && ok "ffmpeg installed" || { fail "ffmpeg install failed"; ERRORS=$((ERRORS + 1)); }
    elif [[ "$OS" == "windows" ]] && [[ "${WIN_PKG:-}" == "choco" ]]; then
        choco install ffmpeg -y && ok "ffmpeg installed" || { fail "ffmpeg install failed"; ERRORS=$((ERRORS + 1)); }
    else
        fail "Install ffmpeg manually — https://ffmpeg.org/download.html"; ERRORS=$((ERRORS + 1))
    fi
fi

# ---------- .env file ----------
echo ""
printf "Checking .env... "
if [[ -f "$REPO_ROOT/.env" ]]; then
    ok ".env exists"
else
    if [[ -f "$REPO_ROOT/.env.example" ]]; then
        cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
        warn "Created .env from .env.example — add your API keys to .env"
    else
        warn "No .env.example found — skipping"
    fi
fi

# ---------- Summary ----------
echo ""
echo "========================================="
if [[ $ERRORS -eq 0 ]]; then
    printf "${GREEN}  All dependencies installed!${NC}\n"
else
    printf "${YELLOW}  %d optional dependency issue(s) — see above.${NC}\n" "$ERRORS"
    printf "${YELLOW}  Skills that need these tools will tell you when they're missing.${NC}\n"
    printf "${YELLOW}  Everything else works fine without them.${NC}\n"
fi
echo "========================================="
echo ""

# Always exit 0 — dependency failures are non-blocking.
# Skills gracefully degrade when their tools are missing.
exit 0
