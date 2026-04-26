#!/usr/bin/env bash
# render_diagram.sh — Render a .mmd file to SVG and PNG
#
# Usage: render_diagram.sh input.mmd [output_base] [theme]
#
# Arguments:
#   input.mmd    Path to the Mermaid source file
#   output_base  (optional) Base path for outputs (without extension).
#                Defaults to input path without .mmd extension.
#   theme        (optional) Mermaid theme: default, dark, forest, neutral
#                Defaults to "neutral" (best for scientific/educational content).
#
# Outputs:
#   {output_base}.svg  — Vector format, scales perfectly
#   {output_base}.png  — Raster format for embedding (2x scale for clarity)
#
# If a .css file exists at the same base path as the .mmd file, it is
# applied automatically via --cssFile for custom styling.

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

# ── Argument parsing ─────────────────────────────────────────────────
case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
render_diagram.sh — Render a .mmd file to SVG and PNG

Usage: render_diagram.sh input.mmd [output_base] [theme]

Arguments:
  input.mmd    Path to the Mermaid source file
  output_base  (optional) Base path for outputs (without extension).
               Defaults to input path without .mmd extension.
  theme        (optional) Mermaid theme: default, dark, forest, neutral.
               Defaults to "neutral".

Outputs:
  {output_base}.svg  — Vector format, scales perfectly
  {output_base}.png  — Raster format, 2x scale for clarity

If a .css file exists at the same base path as the .mmd file, it is
applied automatically via --cssFile.
USAGE
    exit 0
    ;;
esac

if [ $# -lt 1 ]; then
  echo "Usage: render_diagram.sh input.mmd [output_base] [theme]"
  echo "Run with --help for details."
  exit 1
fi

INPUT="$1"
if [ ! -f "$INPUT" ]; then
  fail "Input file not found: $INPUT"
fi

# Output base: strip .mmd extension if not provided
OUTPUT_BASE="${2:-${INPUT%.mmd}}"
THEME="${3:-neutral}"

# Validate theme
case "$THEME" in
  default|dark|forest|neutral) ;;
  *) echo "Warning: Unknown theme '$THEME', falling back to 'neutral'"; THEME="neutral" ;;
esac

# ── Check for custom CSS ─────────────────────────────────────────────
CSS_FILE="${INPUT%.mmd}.css"
CSS_ARGS=""
if [ -f "$CSS_FILE" ]; then
  CSS_ARGS="--cssFile $CSS_FILE"
  echo "Using custom CSS: $CSS_FILE"
fi

# ── Check mmdc is available ──────────────────────────────────────────
if ! npx mmdc --version &>/dev/null 2>&1; then
  fail "mmdc not found. Run: bash .claude/skills/viz-diagram-code/scripts/setup.sh"
fi

# ── Render SVG ───────────────────────────────────────────────────────
echo "Rendering SVG..."
if npx mmdc -i "$INPUT" -o "${OUTPUT_BASE}.svg" -t "$THEME" -b transparent $CSS_ARGS 2>/dev/null; then
  ok "SVG: ${OUTPUT_BASE}.svg"
else
  fail "SVG rendering failed"
fi

# ── Render PNG (2x scale for clarity) ────────────────────────────────
echo "Rendering PNG..."
if npx mmdc -i "$INPUT" -o "${OUTPUT_BASE}.png" -t "$THEME" -b white -s 2 $CSS_ARGS 2>/dev/null; then
  ok "PNG: ${OUTPUT_BASE}.png"
else
  fail "PNG rendering failed"
fi

echo ""
echo "Done. Files:"
echo "  SVG: ${OUTPUT_BASE}.svg"
echo "  PNG: ${OUTPUT_BASE}.png"
