#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Organon — Scientific Environment Setup
# =============================================================================
# Sets up the shared Python virtual environment with scientific packages.
# Run after initial install:
#   bash scripts/setup-science.sh
#
# What it does:
#   1. Checks prerequisites (uv)
#   2. Creates shared .venv at project root (Python 3.10+ per D-12)
#   3. Installs scientific packages (per D-11)
#   4. Installs pytest for test infrastructure
#   5. Creates repro/ directory structure (per D-06)
#
# Idempotent — safe to run multiple times.
# =============================================================================

# ---------- Resolve repo root from script location ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$REPO_ROOT/.venv"

# ---------- Colors ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# ---------- Helpers ----------
info()    { printf "${CYAN}%s${NC}\n" "$1"; }
success() { printf "${GREEN}  + %s${NC}\n" "$1"; }
warn()    { printf "${YELLOW}  ! %s${NC}\n" "$1"; }
error()   { printf "${RED}%s${NC}\n" "$1"; }

# ---------- Prerequisites ----------
info "Setting up scientific computing environment..."

if ! command -v uv >/dev/null 2>&1; then
    error "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# ---------- Create venv ----------
if [[ ! -d "$VENV_PATH" ]]; then
    info "Creating Python virtual environment..."
    if uv venv "$VENV_PATH" --python 3.10 2>/dev/null; then
        success "venv created at $VENV_PATH (Python 3.10)"
    else
        warn "Python 3.10 not available, falling back to system Python"
        uv venv "$VENV_PATH"
        success "venv created at $VENV_PATH"
    fi
else
    success "venv already exists"
fi

# ---------- Install scientific packages (D-11) ----------
info "Installing scientific packages..."
uv pip install --python "$VENV_PATH/bin/python" \
    pandas numpy scipy matplotlib seaborn SciencePlots plotly
success "Scientific packages installed: pandas, numpy, scipy, matplotlib, seaborn, SciencePlots, plotly"

# ---------- Install pytest ----------
info "Installing test infrastructure..."
uv pip install --python "$VENV_PATH/bin/python" pytest
success "pytest installed"

# ---------- Create repro directory (D-06) ----------
mkdir -p "$REPO_ROOT/repro/summaries"
success "Reproducibility ledger directory created"

# ---------- Create repro package ----------
if [[ ! -f "$REPO_ROOT/repro/__init__.py" ]]; then
    touch "$REPO_ROOT/repro/__init__.py"
    success "repro/ Python package initialized"
else
    success "repro/ Python package already exists"
fi

# ---------- Done ----------
printf "\n${GREEN}Scientific environment ready${NC}\n"
