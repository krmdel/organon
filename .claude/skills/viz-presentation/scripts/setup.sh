#!/usr/bin/env bash
# Setup for viz-presentation skill
# - Base: installs @marp-team/marp-cli globally via npm
# - Optional (--with-paper): installs PDF extraction backends for paper mode
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

WITH_PAPER=0
for arg in "$@"; do
  [[ "$arg" == "--with-paper" ]] && WITH_PAPER=1
done

echo "=== viz-presentation: Setup ==="

# Check Node.js
if ! command -v node &>/dev/null; then
  echo -e "${RED}ERROR: Node.js is required but not installed.${NC}"
  echo "Install via: brew install node (macOS) or https://nodejs.org"
  exit 1
fi

echo -e "${GREEN}OK${NC} Node.js $(node --version)"

# Check/install marp-cli
if npx @marp-team/marp-cli --version &>/dev/null 2>&1; then
  MARP_VERSION=$(npx @marp-team/marp-cli --version 2>/dev/null | head -1)
  echo -e "${GREEN}OK${NC} marp-cli already installed: ${MARP_VERSION}"
else
  echo -e "${YELLOW}Installing @marp-team/marp-cli globally...${NC}"
  if npm install -g @marp-team/marp-cli; then
    echo -e "${GREEN}OK${NC} marp-cli installed successfully"
  else
    echo -e "${RED}FAIL${NC} Could not install marp-cli"
    echo "Try manually: npm install -g @marp-team/marp-cli"
    exit 1
  fi
  if npx @marp-team/marp-cli --version &>/dev/null 2>&1; then
    MARP_VERSION=$(npx @marp-team/marp-cli --version 2>/dev/null | head -1)
    echo -e "${GREEN}OK${NC} Verified: marp-cli ${MARP_VERSION}"
  else
    echo -e "${RED}FAIL${NC} marp-cli installed but verification failed"
    exit 1
  fi
fi

# Optional: PDF extraction backends for `paper` mode
if [[ $WITH_PAPER -eq 1 ]]; then
  echo ""
  echo "=== Optional: PDF extraction (paper mode) ==="

  # Prefer Docling (strong layout + figure extraction); fall back to PyMuPDF
  if python3 -c "import docling" &>/dev/null; then
    echo -e "${GREEN}OK${NC} Docling already available"
  elif command -v uv &>/dev/null; then
    echo -e "${YELLOW}Installing Docling via uv...${NC}"
    uv pip install --system docling 2>/dev/null \
      || uv pip install docling 2>/dev/null \
      || echo -e "${YELLOW}Docling install failed — will rely on PyMuPDF fallback${NC}"
  elif command -v pip3 &>/dev/null; then
    echo -e "${YELLOW}Installing Docling via pip...${NC}"
    pip3 install --user docling 2>/dev/null \
      || echo -e "${YELLOW}Docling install failed — will rely on PyMuPDF fallback${NC}"
  fi

  if python3 -c "import fitz" &>/dev/null; then
    echo -e "${GREEN}OK${NC} PyMuPDF (fitz) available as fallback"
  elif command -v uv &>/dev/null; then
    echo -e "${YELLOW}Installing PyMuPDF fallback via uv...${NC}"
    uv pip install --system pymupdf 2>/dev/null \
      || uv pip install pymupdf 2>/dev/null \
      || echo -e "${RED}PyMuPDF install failed — paper mode unavailable${NC}"
  elif command -v pip3 &>/dev/null; then
    pip3 install --user pymupdf 2>/dev/null \
      || echo -e "${RED}PyMuPDF install failed — paper mode unavailable${NC}"
  fi

  if python3 -c "import docling" &>/dev/null || python3 -c "import fitz" &>/dev/null; then
    echo -e "${GREEN}OK${NC} At least one PDF backend ready"
  else
    echo -e "${RED}WARN${NC} No PDF backend installed — paper mode will prompt for manual install"
  fi
fi

echo "=== Setup complete ==="
