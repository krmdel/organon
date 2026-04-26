#!/usr/bin/env bash
set -euo pipefail

# capstone_verify.sh -- Automated verification for Organon v1.1 capstone
#
# Verifies all outputs produced by scripts/capstone_demo.sh:
#   - File existence for all deliverables (md, docx, pdf)
#   - Content structure (headings, keywords)
#   - Hypotheses quality (confidence levels, falsifiability)
#   - Blog post structure (headings, image references, rendered formats)
#   - Presentation overflow check (Marp source slide count)
#   - Figure generation method (AI via nano-banana vs code fallback)
#   - Citation tracing to source article (CAP-06)
#   - BibTeX file validity
#   - Consolidated article existence (Stage 6)
#
# Usage: bash scripts/capstone_verify.sh
# Exit: 0 if all checks pass, 1 if any check fails

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

OUTPUT_DIR="projects/capstone"
PASS=0
FAIL=0
SKIP=0

# Helper: run a check, print [PASS] or [FAIL], increment counter
check() {
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then
        echo "  [PASS] $desc"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $desc"
        FAIL=$((FAIL + 1))
    fi
}

# Helper: mark a check as skipped
skip() {
    echo "  [SKIP] $1"
    SKIP=$((SKIP + 1))
}

echo "============================================"
echo "  Capstone Verification"
echo "  Organon v1.1"
echo "  Output dir: $OUTPUT_DIR/"
echo "============================================"
echo ""

# ---------------------------------------------------------------
# File Existence
# ---------------------------------------------------------------
echo "-- File Existence --"
check "critical-analysis.md exists"  test -f "$OUTPUT_DIR/critical-analysis.md"
check "hypotheses.md exists"         test -f "$OUTPUT_DIR/hypotheses.md"
check "blog-post.md exists"          test -f "$OUTPUT_DIR/blog-post.md"
check "references.bib exists"        test -f "$OUTPUT_DIR/references.bib"
check "presentation/ directory exists" test -d "$OUTPUT_DIR/presentation"
check "figures/ directory exists"    test -d "$OUTPUT_DIR/figures"

# Check for rendered presentation (PDF or PPTX)
if ls "$OUTPUT_DIR/presentation/"*.pdf 1>/dev/null 2>&1; then
    check "presentation rendered as PDF" true
elif ls "$OUTPUT_DIR/presentation/"*.pptx 1>/dev/null 2>&1; then
    check "presentation rendered as PPTX" true
else
    check "presentation rendered output (PDF or PPTX)" false
fi

# Check for rendered blog post formats (DOCX and PDF)
if [[ -f "$OUTPUT_DIR/blog-post.docx" ]]; then
    check "blog-post.docx exists" true
else
    skip "blog-post.docx (rendered blog not found -- Stage 3 may not have produced DOCX)"
fi
if [[ -f "$OUTPUT_DIR/blog-post.pdf" ]]; then
    check "blog-post.pdf exists" true
else
    skip "blog-post.pdf (rendered blog not found -- Stage 3 may not have produced PDF)"
fi

# Check for consolidated article
if [[ -f "$OUTPUT_DIR/article.pdf" ]] || [[ -f "$OUTPUT_DIR/article.html" ]]; then
    check "consolidated article exists (HTML or PDF)" true
    if [[ -f "$OUTPUT_DIR/article.docx" ]]; then
        check "article.docx exists" true
    else
        skip "article.docx (not generated)"
    fi
else
    skip "consolidated article (Stage 6 may not have run)"
fi

# ---------------------------------------------------------------
# Content Structure -- Critical Analysis (CAP-01, CAP-02)
# ---------------------------------------------------------------
echo ""
echo "-- Critical Analysis Structure (CAP-01, CAP-02) --"
check "Has summary/overview section" \
    grep -qi "summary\|overview\|abstract" "$OUTPUT_DIR/critical-analysis.md"
check "Has gaps/limitations section" \
    grep -qi "gap\|limitation\|weakness" "$OUTPUT_DIR/critical-analysis.md"
check "Has improvement suggestions" \
    grep -qi "suggest\|recommend\|improv" "$OUTPUT_DIR/critical-analysis.md"

# ---------------------------------------------------------------
# Hypotheses Structure (CAP-03)
# ---------------------------------------------------------------
echo ""
echo "-- Hypotheses Structure (CAP-03) --"
check "Has multiple hypotheses" \
    grep -qi "hypothesis\|H[0-9]" "$OUTPUT_DIR/hypotheses.md"
check "Has confidence levels" \
    grep -qi "confidence\|high\|medium\|low" "$OUTPUT_DIR/hypotheses.md"
check "Has falsifiability criteria" \
    grep -qi "falsif\|disproven\|reject" "$OUTPUT_DIR/hypotheses.md"

# ---------------------------------------------------------------
# Blog Post Structure (CAP-04)
# ---------------------------------------------------------------
echo ""
echo "-- Blog Post Structure (CAP-04) --"
check "Has structured headings" \
    grep -q '^#' "$OUTPUT_DIR/blog-post.md"
check "Has image references" \
    grep -q '!\[' "$OUTPUT_DIR/blog-post.md"

# ---------------------------------------------------------------
# Presentation Slide Overflow (CAP-05)
# ---------------------------------------------------------------
echo ""
echo "-- Presentation Quality (CAP-05) --"
MARP_SRC=$(find "$OUTPUT_DIR/presentation" -name "*.md" -type f 2>/dev/null | head -1)
if [[ -n "$MARP_SRC" ]]; then
    # Count slides (--- separators) -- should be 8-14 for a 8-12 content slide deck
    SLIDE_COUNT=$(grep -c '^---$' "$MARP_SRC" || true)
    if [[ $SLIDE_COUNT -ge 8 ]] && [[ $SLIDE_COUNT -le 16 ]]; then
        check "slide count in range 8-16 (got $SLIDE_COUNT)" true
    else
        check "slide count in range 8-16 (got $SLIDE_COUNT)" false
    fi
    # Check for font-size constraint (prevents overflow)
    if grep -q 'font-size' "$MARP_SRC" 2>/dev/null; then
        check "Marp style has font-size constraint" true
    else
        check "Marp style has font-size constraint (prevents overflow)" false
    fi
else
    skip "Marp source not found for overflow check"
fi

# ---------------------------------------------------------------
# Figure Generation Method
# ---------------------------------------------------------------
echo ""
echo "-- Figure Generation --"
# Check that figures directory has at least 2 images
FIG_COUNT=$(find "$OUTPUT_DIR/figures" -type f \( -name "*.png" -o -name "*.svg" -o -name "*.jpg" \) 2>/dev/null | wc -l | tr -d ' ')
if [[ $FIG_COUNT -ge 2 ]]; then
    check "at least 2 figure files generated ($FIG_COUNT found)" true
else
    check "at least 2 figure files generated (only $FIG_COUNT found)" false
fi
# Check if any figure was generated via nano-banana (Gemini) vs code fallback
if find "$OUTPUT_DIR/figures" -name "*.png" -exec file {} \; 2>/dev/null | grep -qi "PNG image"; then
    check "figures are valid PNG images" true
else
    check "figures are valid PNG images" false
fi
# Informational: report generation method
if grep -rqi "gemini\|nano.banana\|GEMINI_API_KEY" "$OUTPUT_DIR/blog-post.md" 2>/dev/null; then
    echo "  [INFO] Blog post references Gemini/nano-banana -- AI figure generation was attempted"
else
    echo "  [INFO] No Gemini references found -- figures likely generated via Mermaid/SVG code fallback"
fi

# ---------------------------------------------------------------
# Citation Tracing (CAP-06)
# Require at least 2 of: "TriAgent", "Delikoyun", "2510.16080" or "biomarker discovery"
# ---------------------------------------------------------------
echo ""
echo "-- Citation Tracing (CAP-06) --"

for file in critical-analysis.md hypotheses.md blog-post.md; do
    filepath="$OUTPUT_DIR/$file"
    if [[ ! -f "$filepath" ]]; then
        skip "$file citation trace (file not found)"
        continue
    fi
    hits=0
    grep -qi "TriAgent" "$filepath" && hits=$((hits + 1)) || true
    grep -qi "Delikoyun" "$filepath" && hits=$((hits + 1)) || true
    grep -qi "2510\.16080\|biomarker discovery" "$filepath" && hits=$((hits + 1)) || true
    if [[ $hits -ge 2 ]]; then
        check "$file traces to source paper (${hits}/3 identifiers match)" true
    else
        check "$file traces to source paper (only ${hits}/3 identifiers -- need 2+)" false
    fi
done

check "BibTeX file has entries (@ present)" \
    grep -q '@' "$OUTPUT_DIR/references.bib"
check "BibTeX references source paper (TriAgent/Delikoyun)" \
    grep -qi "TriAgent\|Delikoyun\|triagent" "$OUTPUT_DIR/references.bib"

# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------
echo ""
echo "============================================"
echo "  Automated results: $PASS passed, $FAIL failed, $SKIP skipped"
echo ""
echo "  Manual review required:"
echo "    Open $OUTPUT_DIR/ and assess output quality."
echo "    Key questions:"
echo "      - Is the critical analysis insightful and well-structured?"
echo "      - Are the hypotheses scientifically plausible?"
echo "      - Is the blog post clear and engaging for non-specialists?"
echo "      - Does the presentation tell a coherent story?"
echo "      - Are citations properly formatted in references.bib?"
echo "============================================"

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
