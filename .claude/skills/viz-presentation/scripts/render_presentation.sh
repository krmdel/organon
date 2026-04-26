#!/usr/bin/env bash
# Usage: render_presentation.sh input.md [format] [theme]
# format: pdf (default), pptx, html, all
# theme: default, gaia, uncover, or path to custom CSS
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ $# -lt 1 ]; then
  echo "Usage: render_presentation.sh input.md [format] [theme]"
  echo "  format: pdf (default), pptx, html, all"
  echo "  theme:  default, gaia, uncover, or path to custom .css"
  exit 1
fi

INPUT="$1"
FORMAT="${2:-pdf}"
THEME="${3:-}"

if [ ! -f "$INPUT" ]; then
  echo -e "${RED}ERROR: File not found: ${INPUT}${NC}"
  exit 1
fi

# Check marp-cli
if ! command -v marp &>/dev/null && ! npx @marp-team/marp-cli --version &>/dev/null 2>&1; then
  echo -e "${RED}ERROR: marp-cli not found. Run scripts/setup.sh first.${NC}"
  exit 1
fi

# Determine marp command
if command -v marp &>/dev/null; then
  MARP="marp"
else
  MARP="npx @marp-team/marp-cli"
fi

# Build base args
ARGS=("--html" "--allow-local-files")

# Add theme if specified
if [ -n "$THEME" ]; then
  ARGS+=("--theme" "$THEME")
fi

DIR=$(dirname "$INPUT")
BASE=$(basename "$INPUT" .md)

render() {
  local fmt="$1"
  local ext="$fmt"
  local output="${DIR}/${BASE}.${ext}"

  echo -e "${YELLOW}Rendering ${fmt}...${NC}"
  if $MARP "${ARGS[@]}" "--${fmt}" "$INPUT" -o "$output" 2>&1; then
    echo -e "${GREEN}OK${NC} ${output}"
  else
    echo -e "${RED}FAIL${NC} Could not render ${fmt}"
    return 1
  fi
}

case "$FORMAT" in
  pdf)
    render pdf
    ;;
  pptx)
    render pptx
    ;;
  html)
    render html
    ;;
  all)
    render pdf
    render pptx
    render html
    ;;
  *)
    echo -e "${RED}ERROR: Unknown format '${FORMAT}'. Use: pdf, pptx, html, all${NC}"
    exit 1
    ;;
esac

echo ""
echo "Output files:"
ls -la "${DIR}/${BASE}".{pdf,pptx,html} 2>/dev/null || true
