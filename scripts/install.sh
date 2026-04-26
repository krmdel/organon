#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Organon — Installer
# =============================================================================
# Single installer for everything. Run after `git clone`:
#   bash scripts/install.sh
#
# Phases:
#   1. Prerequisites (git, bash, python3, node)
#   2. Environment (.env, directory structure)
#   3. System tools (uv, yt-dlp, ffmpeg)
#   4. Python scientific environment (.venv + packages)
#   5. Skill dependencies (mermaid, marp, etc.)
#   6. MCP server build (paper-search)
#   7. Skills catalog + installed.json
#   8. GSD project framework
#   9. Cron dispatcher
#
# Idempotent — safe to run multiple times. Skips what's already done.
# =============================================================================

# ---------- Resolve repo root from script location ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Convert MSYS/Git Bash paths to Windows-native for Python compatibility
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) REPO_ROOT="$(cygpath -m "$REPO_ROOT")" ;;
esac

# ---------- Colors ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ---------- Helpers ----------
info()    { printf "${CYAN}%s${NC}\n" "$1"; }
success() { printf "${GREEN}  ✓ %s${NC}\n" "$1"; }
warn()    { printf "${YELLOW}  ! %s${NC}\n" "$1"; }
fail()    { printf "${RED}  ✗ %s${NC}\n" "$1"; }
installed() { command -v "$1" &>/dev/null; }

# ---------- Detect OS ----------
OS="unknown"
case "$(uname -s)" in
    Darwin*)              OS="mac" ;;
    MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
    Linux*)               OS="linux" ;;
esac

# ---------- Paths ----------
CATALOG="$REPO_ROOT/.claude/skills/_catalog/catalog.json"
INSTALLED_JSON="$REPO_ROOT/.claude/skills/_catalog/installed.json"
SKILLS_DIR="$REPO_ROOT/.claude/skills"
VENV_PATH="$REPO_ROOT/.venv"

# Track non-critical failures
WARNINGS=0

# =============================================================================
# Phase 1: Welcome + Prerequisites
# =============================================================================
clear 2>/dev/null || true
echo ""
printf "${CYAN}${BOLD}"
cat << 'BANNER'
    ╔══════════════════════════════════════════════╗
    ║                                              ║
    ║                O R G A N O N                 ║
    ║                                              ║
    ║        An Agentic OS for Scientists          ║
    ║                                              ║
    ╚══════════════════════════════════════════════╝
BANNER
printf "${NC}"
echo ""
printf "${DIM}  Installer v2.0${NC}\n"
echo ""

info "Phase 1: Checking prerequisites..."
echo ""

PREREQ_FAIL=0
PYTHON_CMD="python3"

# Git
printf "  git .......... "
if installed git; then
    printf "${GREEN}$(git --version | awk '{print $3}')${NC}\n"
else
    printf "${RED}not found${NC}\n"
    fail "Install git: https://git-scm.com/downloads"
    PREREQ_FAIL=1
fi

# Bash
printf "  bash ......... "
if installed bash; then
    printf "${GREEN}${BASH_VERSION}${NC}\n"
else
    printf "${RED}not found${NC}\n"
    fail "bash is required"
    PREREQ_FAIL=1
fi

# Node.js
printf "  node ......... "
if installed node; then
    printf "${GREEN}$(node --version 2>&1)${NC}\n"
else
    printf "${YELLOW}not found${NC}\n"
    warn "Node.js recommended for GSD + MCP. Install from: https://nodejs.org/"
    WARNINGS=$((WARNINGS + 1))
fi

# Python 3
printf "  python3 ...... "
if installed python3; then
    printf "${GREEN}$(python3 --version 2>&1 | awk '{print $2}')${NC}\n"
    PYTHON_CMD="python3"
elif installed python; then
    PY_VER=$(python --version 2>&1 | awk '{print $2}')
    case "$PY_VER" in
        3.*) printf "${GREEN}${PY_VER} (as 'python')${NC}\n"
             PYTHON_CMD="python" ;;
        *)   printf "${RED}found python ${PY_VER} — need Python 3${NC}\n"
             PREREQ_FAIL=1 ;;
    esac
else
    printf "${RED}not found${NC}\n"
    fail "Install Python 3: https://www.python.org/downloads/"
    PREREQ_FAIL=1
fi

echo ""

if [[ $PREREQ_FAIL -ne 0 ]]; then
    fail "Missing prerequisites — install them and re-run this script."
    exit 1
fi

success "All prerequisites met"
echo ""

# =============================================================================
# Phase 2: Environment
# =============================================================================
info "Phase 2: Setting up environment..."
echo ""

if [[ -f "$REPO_ROOT/.env" ]]; then
    success ".env already exists"
else
    if [[ -f "$REPO_ROOT/.env.example" ]]; then
        cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
        success "Created .env from .env.example"
        warn "Add your API keys to .env later — skills work without them"
    else
        warn "No .env.example found — skipping .env creation"
    fi
fi

# Create .mcp.json from example if not present
if [[ -f "$REPO_ROOT/.mcp.json" ]]; then
    success ".mcp.json already exists"
else
    if [[ -f "$REPO_ROOT/.mcp.example.json" ]]; then
        cp "$REPO_ROOT/.mcp.example.json" "$REPO_ROOT/.mcp.json"
        success "Created .mcp.json from .mcp.example.json (MCP servers: paper-search, paperclip, tooluniverse)"
    else
        warn "No .mcp.example.json found — skipping .mcp.json creation"
    fi
fi

# Ensure MCP env shim is executable
if [[ -f "$REPO_ROOT/scripts/with-env.sh" ]]; then
    chmod +x "$REPO_ROOT/scripts/with-env.sh"
    success "scripts/with-env.sh is executable (MCP servers will auto-load .env)"
fi

# Create user data directories
mkdir -p "$REPO_ROOT/research_context"
mkdir -p "$REPO_ROOT/repro/summaries"
success "Directory structure ready"

# context/USER.md and context/learnings.md are tracked — no template logic needed
if [[ -f "$REPO_ROOT/context/USER.md" ]]; then
    success "context/USER.md exists"
else
    fail "context/USER.md missing — your clone is incomplete. Run: git checkout -- context/"
    exit 1
fi

echo ""

# =============================================================================
# Phase 3: System tools
# =============================================================================
info "Phase 3: Installing system tools..."
echo ""

# Package manager check
if [[ "$OS" == "mac" ]]; then
    printf "  brew ......... "
    if installed brew; then
        printf "${GREEN}found${NC}\n"
    else
        printf "${YELLOW}not found${NC}\n"
        warn "Install from https://brew.sh — some auto-installs may fail"
        WARNINGS=$((WARNINGS + 1))
    fi
elif [[ "$OS" == "windows" ]]; then
    WIN_PKG=""
    if installed winget; then WIN_PKG="winget"
    elif installed choco; then WIN_PKG="choco"
    else warn "No package manager found (winget or choco)"; fi
fi

# uv (Python package manager — needed for venv and skill deps)
printf "  uv ........... "
if installed uv; then
    printf "${GREEN}$(uv --version 2>&1 | awk '{print $2}')${NC}\n"
else
    printf "${YELLOW}installing...${NC}\n"
    if [[ "$OS" == "mac" ]] && installed brew; then
        brew install uv >/dev/null 2>&1 && success "uv installed" || { fail "uv install failed"; WARNINGS=$((WARNINGS + 1)); }
    elif [[ "$OS" == "windows" ]] && [[ "${WIN_PKG:-}" == "winget" ]]; then
        winget install --id astral-sh.uv -e --silent >/dev/null 2>&1 && success "uv installed" || { fail "uv install failed"; WARNINGS=$((WARNINGS + 1)); }
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 && success "uv installed" || { fail "uv install failed"; WARNINGS=$((WARNINGS + 1)); }
    fi
fi

# yt-dlp (YouTube transcripts)
printf "  yt-dlp ....... "
if installed yt-dlp; then
    printf "${GREEN}found${NC}\n"
else
    printf "${YELLOW}installing...${NC}\n"
    if [[ "$OS" == "mac" ]] && installed brew; then
        brew install yt-dlp >/dev/null 2>&1 && success "yt-dlp installed" || { warn "yt-dlp install failed — tool-youtube will prompt"; WARNINGS=$((WARNINGS + 1)); }
    elif installed pip3; then
        pip3 install yt-dlp >/dev/null 2>&1 && success "yt-dlp installed" || { warn "yt-dlp install failed"; WARNINGS=$((WARNINGS + 1)); }
    else
        warn "yt-dlp not installed — tool-youtube transcript mode requires it"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# ffmpeg (video/audio processing)
printf "  ffmpeg ....... "
if installed ffmpeg; then
    printf "${GREEN}found${NC}\n"
else
    printf "${YELLOW}installing...${NC}\n"
    if [[ "$OS" == "mac" ]] && installed brew; then
        brew install ffmpeg >/dev/null 2>&1 && success "ffmpeg installed" || { warn "ffmpeg install failed"; WARNINGS=$((WARNINGS + 1)); }
    elif [[ "$OS" == "windows" ]] && [[ "${WIN_PKG:-}" == "winget" ]]; then
        winget install --id Gyan.FFmpeg -e --silent >/dev/null 2>&1 && success "ffmpeg installed" || { warn "ffmpeg install failed"; WARNINGS=$((WARNINGS + 1)); }
    else
        warn "ffmpeg not installed — install manually from https://ffmpeg.org/"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

echo ""

# =============================================================================
# Phase 4: Python scientific environment
# =============================================================================
info "Phase 4: Setting up Python scientific environment..."
echo ""

if ! installed uv; then
    warn "uv not available — skipping Python environment setup"
    warn "Install uv (https://astral.sh/uv), then re-run this script"
    WARNINGS=$((WARNINGS + 1))
else
    # Create venv if needed
    if [[ ! -d "$VENV_PATH" ]]; then
        if uv venv "$VENV_PATH" --python 3.10 2>/dev/null; then
            success "Created .venv (Python 3.10)"
        else
            uv venv "$VENV_PATH" 2>/dev/null && success "Created .venv (system Python)" || {
                fail "Could not create .venv"
                WARNINGS=$((WARNINGS + 1))
            }
        fi
    else
        success ".venv already exists"
    fi

    # Install scientific packages
    if [[ -d "$VENV_PATH" ]]; then
        VENV_PY="$VENV_PATH/bin/python"
        [[ "$OS" == "windows" ]] && VENV_PY="$VENV_PATH/Scripts/python.exe"

        info "  Installing scientific packages..."
        if uv pip install --python "$VENV_PY" \
            pandas numpy scipy matplotlib seaborn SciencePlots plotly \
            openpyxl pytest pymupdf 2>/dev/null; then
            success "Scientific stack: pandas, numpy, scipy, matplotlib, seaborn, plotly, SciencePlots"
            success "Extras: openpyxl (Excel), pytest (testing), pymupdf (PDF → viz-presentation paper mode)"
        else
            warn "Some packages failed to install — skills will report what's missing"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
fi

echo ""

# =============================================================================
# Phase 5: Skill dependencies
# =============================================================================
info "Phase 5: Installing skill dependencies..."
echo ""

# Mermaid CLI (viz-diagram-code, tool-substack mermaid pre-render)
printf "  mermaid-cli .. "
if installed mmdc; then
    printf "${GREEN}found${NC}\n"
elif installed npx; then
    printf "${YELLOW}installing...${NC}\n"
    npm install -g @mermaid-js/mermaid-cli 2>/dev/null && success "mermaid-cli installed" || {
        warn "mermaid-cli install failed — viz-diagram-code will prompt"
        WARNINGS=$((WARNINGS + 1))
    }
else
    printf "${YELLOW}skipped (no npm)${NC}\n"
    WARNINGS=$((WARNINGS + 1))
fi

# Marp CLI (viz-presentation)
printf "  marp-cli ..... "
if installed marp; then
    printf "${GREEN}found${NC}\n"
elif installed npx; then
    printf "${YELLOW}installing...${NC}\n"
    npm install -g @marp-team/marp-cli 2>/dev/null && success "marp-cli installed" || {
        warn "marp-cli install failed — viz-presentation will prompt"
        WARNINGS=$((WARNINGS + 1))
    }
else
    printf "${YELLOW}skipped (no npm)${NC}\n"
    WARNINGS=$((WARNINGS + 1))
fi

# IDE preview extensions (Cursor / VS Code) — enables inline preview of
# .pdf / .docx / .xlsx / .csv and live HTML preview for viz-presentation decks.
# Idempotent: CLI skips already-installed extensions. Skipped silently if no
# Cursor/VS Code CLI is on PATH (CI / server environments).
printf "  ide-previews . "
if bash "$REPO_ROOT/scripts/setup-ide-previews.sh" >/dev/null 2>&1; then
    success "IDE preview extensions installed (PDF, docx/xlsx, Live Preview for HTML)"
else
    warn "IDE preview extensions skipped (no Cursor/VS Code CLI detected)"
fi

echo ""

# =============================================================================
# Phase 6: MCP server build
# =============================================================================
info "Phase 6: Building MCP servers..."
echo ""

PAPER_SEARCH_DIR="$REPO_ROOT/mcp-servers/paper-search"
if [[ -d "$PAPER_SEARCH_DIR" ]] && installed node; then
    if [[ -d "$PAPER_SEARCH_DIR/dist" ]] && [[ -f "$PAPER_SEARCH_DIR/dist/index.js" ]]; then
        success "paper-search MCP server already built"
    else
        (cd "$PAPER_SEARCH_DIR" && npm install --ignore-scripts 2>/dev/null && npm run build 2>/dev/null) \
            && success "paper-search MCP server built" \
            || { warn "paper-search build failed — run 'cd mcp-servers/paper-search && npm install && npm run build'"; WARNINGS=$((WARNINGS + 1)); }
    fi
else
    if ! installed node; then
        warn "Skipping MCP server build — Node.js not found"
    fi
fi

echo ""

# =============================================================================
# Phase 7: Skills catalog
# =============================================================================
info "Phase 7: Registering skills..."
echo ""

if [[ ! -f "$CATALOG" ]]; then
    fail "Catalog not found at $CATALOG"
    fail "Your clone may be incomplete. Try: git checkout -- .claude/skills/_catalog/"
    exit 1
fi

$PYTHON_CMD << PYEOF
import json, datetime, os

catalog_path = "$CATALOG"
installed_json = "$INSTALLED_JSON"

with open(catalog_path) as f:
    catalog = json.load(f)

core = catalog['core_skills']
optional = catalog['skills']
all_skills = sorted(set(core) | set(optional.keys()))

os.makedirs(os.path.dirname(installed_json), exist_ok=True)
data = {
    'installed_at': datetime.date.today().isoformat(),
    'version': catalog['version'],
    'installed_skills': all_skills,
    'removed_skills': [],
    'selection_pending': True
}
with open(installed_json, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')

print(f"  \033[0;32m✓ {len(all_skills)} skills registered\033[0m")
PYEOF

echo ""

# =============================================================================
# Phase 8: GSD project framework
# =============================================================================
info "Phase 8: Installing GSD project framework..."
echo ""

if installed node; then
    GSD_GLOBAL="$HOME/.claude/commands/gsd"
    if [[ -d "$GSD_GLOBAL" ]] && [[ $(ls -1 "$GSD_GLOBAL"/*.md 2>/dev/null | wc -l) -gt 10 ]]; then
        success "GSD already installed ($(ls -1 "$GSD_GLOBAL"/*.md | wc -l | tr -d ' ') commands)"
    else
        if npx get-shit-done-cc --global --claude 2>/dev/null; then
            success "GSD installed"
        else
            warn "GSD install failed — install later with: npx get-shit-done-cc --global --claude"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
    # Clean up any local GSD install (migrated to global)
    GSD_LOCAL="$REPO_ROOT/.claude/commands/gsd"
    if [[ -d "$GSD_LOCAL" ]]; then
        rm -rf "$GSD_LOCAL"
        find "$REPO_ROOT/.claude/agents" -name "gsd-*.md" -delete 2>/dev/null || true
        success "Cleaned up old local GSD files"
    fi
else
    warn "Skipping GSD — Node.js not found"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""

# =============================================================================
# Phase 9: Cron dispatcher
# =============================================================================
info "Phase 9: Installing cron dispatcher..."
echo ""

if bash "$SCRIPT_DIR/install-crons.sh" 2>/dev/null; then
    : # install-crons.sh prints its own success
else
    warn "Cron dispatcher install failed — install later: bash scripts/install-crons.sh"
    WARNINGS=$((WARNINGS + 1))
fi

# =============================================================================
# Done
# =============================================================================
echo ""
printf "${CYAN}${BOLD}═══════════════════════════════════════════════${NC}\n"
printf "${CYAN}${BOLD}  Installation Complete${NC}\n"
printf "${CYAN}${BOLD}═══════════════════════════════════════════════${NC}\n"
echo ""

if [[ $WARNINGS -gt 0 ]]; then
    printf "  ${YELLOW}$WARNINGS optional item(s) need attention — see above.${NC}\n"
    echo "  Everything else works. Skills tell you when something's missing."
    echo ""
fi

echo "  Next steps:"
echo "    1. Run ${BOLD}claude${NC} — it walks you through research profile setup"
echo "    2. Add API keys to .env if any skills need them"
echo "    3. Check for updates anytime: ${BOLD}bash scripts/update.sh --check${NC}"
echo ""
