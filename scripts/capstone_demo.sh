#!/usr/bin/env bash
set -euo pipefail

# capstone_demo.sh -- Ship-readiness demo for Organon v1.1
#
# Processes a real scientific article through the full skill routing system:
#   Stage 1: Critical analysis (CAP-01, CAP-02)
#   Stage 2: Research hypotheses (CAP-03)
#   Stage 3: Blog post with figures + DOCX/PDF render (CAP-04)
#   Stage 4: Presentation pitch deck with overflow-safe Marp (CAP-05)
#   Stage 5: Citation verification + BibTeX export (CAP-06)
#   Stage 6: Consolidated two-column article (HTML/DOCX/PDF)
#
# Usage: bash scripts/capstone_demo.sh
#
# Pre-requisites:
#   - claude CLI installed and authenticated
#   - docs/2510.16080v1.pdf present at repo root
#   - GEMINI_API_KEY in .env (optional -- Stage 3 AI illustrations degrade without it)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

ARTICLE="docs/2510.16080v1.pdf"
OUTPUT_DIR="projects/capstone"
TIMESTAMP=$(date +%Y-%m-%d)

# Pre-flight checks
command -v claude >/dev/null 2>&1 || { echo "ERROR: claude CLI not found. Install via: npm install -g @anthropic-ai/claude-code"; exit 1; }
[[ -f "$ARTICLE" ]] || { echo "ERROR: Source article not found at $ARTICLE"; exit 1; }

# Optional GEMINI_API_KEY warning
if [[ -f ".env" ]]; then
    if ! grep -q "GEMINI_API_KEY" ".env" 2>/dev/null; then
        echo "WARNING: GEMINI_API_KEY not found in .env -- Stage 3 AI illustrations may be skipped."
        echo "         Blog post will still be generated, but without AI-generated scientific figures."
        echo ""
    fi
else
    echo "WARNING: No .env file found -- GEMINI_API_KEY unavailable. Stage 3 AI illustrations may be skipped."
    echo ""
fi

# Clean previous run and create output directories
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/figures" "$OUTPUT_DIR/presentation"

echo "============================================"
echo "  Capstone Full Pipeline Demo"
echo "  Organon v1.1"
echo "  Source: $ARTICLE"
echo "  Output: $OUTPUT_DIR/"
echo "  Date:   $TIMESTAMP"
echo "============================================"
echo ""

# Stage 1: Critical Analysis (CAP-01, CAP-02)
echo ">>> Stage 1/6: Critical Analysis"
echo "    Reading article and producing structured critical analysis..."
claude -p "Read the scientific article at $ARTICLE. Produce a structured critical analysis identifying the paper's key contributions, then systematically examine gaps, methodological weaknesses, and areas for improvement. Structure the output with clear headings: Summary, Key Contributions, Gaps and Limitations, Methodological Concerns, and Suggestions for Improvement. Save the complete analysis to $OUTPUT_DIR/critical-analysis.md" \
  --dangerously-skip-permissions
echo "    Stage 1 complete."
echo ""

# Stage 2: Research Hypotheses (CAP-03)
echo ">>> Stage 2/6: Research Hypotheses"
echo "    Generating testable hypotheses from identified gaps..."
claude -p --continue "Based on the critical analysis you just produced at $OUTPUT_DIR/critical-analysis.md, generate 3-5 testable research hypotheses that address the identified gaps. For each hypothesis, include: the hypothesis statement, confidence level (high/medium/low), supporting rationale from the paper's gaps, falsifiability criteria, and a brief suggested experimental approach. Save to $OUTPUT_DIR/hypotheses.md" \
  --dangerously-skip-permissions
echo "    Stage 2 complete."
echo ""

# Stage 3: Blog Post with Figures (CAP-04)
echo ">>> Stage 3/6: Blog Post with Figures"
echo "    Writing science blog post with AI illustrations and diagrams..."
claude -p --continue "Write a science blog post about the paper at $ARTICLE for a technically literate but non-specialist audience. The blog post should explain what the paper does, why it matters, and what the open questions are.

Include 2-3 figures in the blog post:
1. At least one Mermaid concept diagram rendered to PNG/SVG via the viz-diagram-code skill or mmdc CLI. Keep Mermaid diagrams simple and horizontal where possible so they fit well in documents.
2. At least one AI-generated illustration via the viz-nano-banana skill (uses Gemini image generation). Since this is a science blog post for non-specialists, use the 'scientific' style with 'conceptual-figure' sub-style for an overview figure, or alternatively the 'color' style for a warmer editorial look. Pre-specified for headless mode -- in interactive sessions the skill would confirm style with the user first. If GEMINI_API_KEY is not available, fall back to a detailed SVG illustration and note the fallback.
3. All figure images must be saved to $OUTPUT_DIR/figures/ as PNG files.

Figure references in the markdown must use relative paths: ![caption](figures/filename.png)

After saving the markdown blog post to $OUTPUT_DIR/blog-post.md, also render it to DOCX and PDF formats with figures embedded:
- Use pandoc to generate: pandoc $OUTPUT_DIR/blog-post.md -o $OUTPUT_DIR/blog-post.docx --standalone --resource-path=$OUTPUT_DIR
- Use pandoc or Chrome headless to generate $OUTPUT_DIR/blog-post.pdf with figures rendered inline.
- Copy the PDF and DOCX to ~/Downloads/ for easy access.

The blog post must be a polished, self-contained document with properly sized figures and captions." \
  --dangerously-skip-permissions
echo "    Stage 3 complete."
echo ""

# Stage 4: Presentation Pitch Deck (CAP-05)
echo ">>> Stage 4/6: Presentation Pitch Deck"
echo "    Creating slide deck summarizing the paper..."
claude -p --continue "Create a short presentation pitch deck (8-12 slides) summarizing the paper at $ARTICLE using Marp markdown format. Include: title slide, problem statement, methodology overview, key results, limitations (from the critical analysis), future directions, and references.

IMPORTANT formatting rules to prevent slide overflow:
- Each slide must fit within a single Marp page -- do NOT overflow content beyond the slide boundary.
- Use base font-size of 26px or smaller in the Marp style block.
- Limit each slide to 6-8 bullet points maximum. If content is dense, split into two slides.
- For two-column layouts, use a table or simple side-by-side divs -- never nest more than 4 items per column.
- For background images (bg right), use 'fit' keyword to constrain image size: ![bg right:50% fit](path).
- Remove unnecessary vertical spacers (no empty &nbsp; lines).
- Test: no text should be cut off at the bottom of any slide.

Render the Marp markdown to PDF, PPTX, and HTML using marp-cli. Copy rendered files to ~/Downloads/.
Save all presentation files to $OUTPUT_DIR/presentation/" \
  --dangerously-skip-permissions
echo "    Stage 4 complete."
echo ""

# Stage 5: Citation Verification + BibTeX Export (CAP-06)
echo ">>> Stage 5/6: Citation Verification"
echo "    Verifying citations and exporting consolidated BibTeX..."
claude -p --continue "Review all the outputs you generated in $OUTPUT_DIR/. Verify that every text file (critical-analysis.md, hypotheses.md, blog-post.md) traces citations back to the source article. Generate a consolidated BibTeX file at $OUTPUT_DIR/references.bib containing the source article and any other papers referenced across all outputs. List any citation gaps found." \
  --dangerously-skip-permissions
echo "    Stage 5 complete."
echo ""

# Stage 6: Consolidated Article (combines all outputs)
echo ">>> Stage 6/6: Consolidated Article"
echo "    Generating structured article combining all pipeline outputs..."
claude -p --continue "Create a structured two-column academic article that consolidates the capstone pipeline outputs into a single polished document. The article should combine:

1. Introduction (from critical analysis context)
2. Framework Architecture (from the paper)
3. Key Contributions (from critical-analysis.md)
4. Experimental Results with tables (from critical-analysis.md)
5. Critical Analysis: Gaps and Limitations (from critical-analysis.md)
6. Research Hypotheses (from hypotheses.md) -- present as numbered hypothesis boxes
7. Science Communication Perspective (from blog-post.md key points)
8. Conclusion
9. References (from references.bib)

Embed all figures from $OUTPUT_DIR/figures/ at appropriate locations with numbered captions (Figure 1, Figure 2, etc.). Constrain figure heights so they don't dominate pages -- use max-height CSS for HTML or width percentages for pandoc.

Generate the article in three formats:
- $OUTPUT_DIR/article.html -- two-column layout using CSS flexbox (NOT css columns which break with page breaks). Use a grid of left/right div pairs for columns.
- $OUTPUT_DIR/article.docx -- via pandoc from a markdown source with figure references
- $OUTPUT_DIR/article.pdf -- render the HTML to PDF via Chrome headless (--headless --print-to-pdf --print-to-pdf-no-header)

Copy PDF and DOCX to ~/Downloads/.

The article must look like a proper academic paper with: title block, abstract, numbered sections, properly sized figures with captions, tables, and a reference list." \
  --dangerously-skip-permissions
echo "    Stage 6 complete."
echo ""

echo "============================================"
echo "  Pipeline complete!"
echo "  Outputs in: $OUTPUT_DIR/"
echo ""
echo "  Deliverables:"
echo "    - critical-analysis.md    (CAP-01, CAP-02)"
echo "    - hypotheses.md           (CAP-03)"
echo "    - blog-post.md/docx/pdf   (CAP-04)"
echo "    - presentation/           (CAP-05)"
echo "    - references.bib          (CAP-06)"
echo "    - article.html/docx/pdf   (consolidated)"
echo ""
echo "  Next step: verify the outputs:"
echo "    bash scripts/capstone_verify.sh"
echo "============================================"
