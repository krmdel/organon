---
name: viz-presentation
description: >
  Generate presentation slide decks from markdown using Marp. Convert blog posts,
  tutorials, manuscripts, academic PDFs, or topic descriptions into professional
  slides with math equations, code highlighting, extracted figures, diagrams,
  and speaker notes. Includes narrative-driven paper-to-slides mode using RST
  discourse analysis for academic talks. Outputs PDF, PPTX, and HTML.
  Triggers on: "presentation", "slide deck", "slides", "make a presentation",
  "convert to slides", "create slides about", "prepare a talk", "lecture slides",
  "conference presentation", "seminar presentation", "poster presentation",
  "paper to slides", "pitch deck", "turn this paper into a talk".
  Does NOT trigger for: diagrams only (use viz-diagram-code), illustrations
  (use viz-nano-banana), blog posts (use sci-communication).
---

**Outcome:** Marp markdown file (.md) + rendered outputs (PDF, PPTX, HTML) saved to `projects/viz-presentation/{name}/`. Professional scientific presentations with math, code, and embedded diagrams.

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `research_context/research-profile.md` | field + preferences | Tailor content depth and terminology |
| `context/learnings.md` | `## viz-presentation` section | Previous feedback |
| `templates/catalog.json` | registry | List of available visual templates |
| `templates/*.md` | frontmatter fragments | Reusable theme blocks prepended to every deck |

## Dependencies

| Skill / Tool | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| `viz-diagram-code` | Optional | Pre-rendered Mermaid diagrams (SVG/PNG) for embedding | Text descriptions instead of diagrams |
| `viz-nano-banana` | Optional | Scientific illustrations for visual slides | Text-only slides |
| `sci-data-analysis` | Optional | Data plots for results slides | Reference data without plots |
| PyMuPDF (`pymupdf`) | Bundled by the project installer | Default PDF extractor for paper mode | Extraction fails — re-run project installer |
| Docling (Python) | Optional upgrade | Better layout + structured table extraction | PyMuPDF fallback (figures + text, no structured tables) |

Requires: Node.js (for marp-cli). Paper mode works out of the box after running the project installer from the repo root. Users who want Docling's richer extraction can opt in via `bash .claude/skills/viz-presentation/scripts/setup.sh --with-paper`.

## Step 0: Auto-Setup

marp-cli and PyMuPDF are installed by the project installer (run once from the repo root). This step is a no-op in normal use. Only re-run this skill's `scripts/setup.sh` if marp-cli went missing, or `scripts/setup.sh --with-paper` to opt into Docling.

## Step 1: Determine Source and Mode

Parse what the user needs:
- **convert** — "convert this blog post to slides", "turn my tutorial into a presentation" — takes existing content and restructures into slides
- **create** — "create a presentation about CRISPR", "lecture slides on attention mechanisms" — generates slide content from topic description
- **template** — "presentation template for a lab meeting", "conference talk template" — generates a structured empty template
- **paper** — "turn this paper into a talk", "paper to slides", path to a `.pdf`, or file in `research_artifacts/papers/` — narrative-driven slides with extracted figures. See Step 2b.

Source types:
| Source | How to handle |
|--------|--------------|
| Existing markdown file (blog/tutorial) | Read, extract key points, restructure into slides |
| Manuscript from sci-writing | Read, create talk version with key findings |
| Topic description (no file) | Generate slide content from expertise + optional literature |
| Pasted text/outline | Structure into slides directly |
| **PDF file (academic paper)** | **Route to paper mode — Step 2b** |

## Step 1.5: Template Selection (always run before writing slides)

Before generating any deck, offer the template gallery so the user can pick a visual style. Skip only if the user explicitly names a template up front ("use dark-academia") or explicitly opts out ("just default").

1. Run `bash .claude/skills/viz-presentation/scripts/preview_themes.sh` — renders every `templates/*.md` with a 4-slide sample body, starts a local HTTP server, prints a gallery URL like `http://localhost:8765/index.html`.

2. Open the gallery in Chrome via `mcp__claude-in-chrome__navigate` if available; otherwise show the URL and ask the user to open it.

3. Ask the user to pick: *"Gallery loaded at {URL}. Which one — `default`, `gaia`, `uncover`, `dark-academia`, or something else? Or say 'use default' / 'skip' to proceed without picking."*

4. Remember the chosen `template_id` for Step 3. If the user skips or says "default", use `default`.

5. If the user wants a **new** template from a screenshot or reference, go to Step 7 instead — create it first, then come back here.

## Step 2: Structure the Presentation

Read `references/slide-structures.md` for structure templates.

For **convert** mode:
1. Read the source content
2. Identify natural slide boundaries (## headings, key concepts, transitions)
3. Extract: title, key points (3-5 per slide), code blocks, data/figures, takeaways
4. Trim prose to concise bullets — presentations are NOT blog posts
5. Identify where diagrams/illustrations would strengthen a slide
6. Add speaker notes with the detailed prose that was trimmed

For **create** mode:
1. Identify the topic and audience level
2. Use structure template from references (research talk, tutorial, lecture, lab meeting)
3. Generate content for each slide
4. Suggest diagram/figure placements

## Step 2b: Paper Mode (PDF → narrative talk)

Triggered when the source is a `.pdf` (academic paper). Read `references/paper-narrative.md` — it contains the full RST discourse + commitments + critique pipeline. The short version:

1. **Extract** — run the PDF through `scripts/extract_paper.py` using the project venv:
   ```bash
   .venv/bin/python .claude/skills/viz-presentation/scripts/extract_paper.py \
       {pdf_path} projects/viz-presentation/{slug}/_extracted/
   ```
   Produces `paper.md`, `assets/fig-*.png`, `assets/tbl-*.md`, and `assets.json`. PyMuPDF is bundled by the project installer, so this should just work. If extraction fails with an import error, the venv is missing `pymupdf` — tell the user to re-run `bash scripts/install.sh`, then retry.

2. **Confirm the talk shape** — before planning slides, ask the user two things in one message:
   - **Duration?** 5-min lightning / 15-min conference / 20-min job talk / custom
   - **Audience?** same-field experts / adjacent field / general scientific / lay

   Defaults if no answer: 15-min, same-field experts.

3. **Write commitments** — inline (not to disk), draft a ~10-line contract per `paper-narrative.md` Step B: thesis, ranked takeaways, narrative spine, slide budget, what to cut.

4. **Discourse-parse + plan** — per `paper-narrative.md` Steps A + C, tag paragraphs with rhetorical roles and group into slides. Every slide title must be a claim statement, not a topic noun.

5. **Self-critique (max 2 rounds)** — run the checklist in Step D. If a check fails, revise the plan and re-check once; a second failure means the commitments are wrong, go back to step 3.

6. **Match figures** — per Step E, assign one asset from `assets.json` to each slide that needs a visual. Use caption keyword overlap + page proximity. Tables: retype the 2-3 rows that matter; full tables go to appendix / speaker notes.

7. **Hand off to Step 3** — now render the Marp markdown with figure paths pointing into `_extracted/assets/`.

## Step 3: Write Marp Markdown

Read `references/marp-syntax.md` for the full Marp syntax reference.

**Frontmatter from chosen template:** copy the contents of `.claude/skills/viz-presentation/templates/{template_id}.md` verbatim as the frontmatter block. Do NOT hand-write YAML — the template is the source of truth for theme + style.

Generate the .md file with:
- Template frontmatter prepended (from Step 1.5 choice)
- `---` between slides
- Marp directives for layout: `<!-- _class: lead -->` for title slides, `<!-- _class: invert -->` for emphasis
- Math via `$...$` (inline) and `$$...$$` (block)
- Code blocks with language tags for syntax highlighting
- **Image embedding — use the `sizing_hint` from `assets.json`**: paper mode writes an aspect-aware Marp directive for every extracted figure (e.g. `w:900 center` for wide, `h:420 center` for landscape, `h:460 center` for near-square, `h:470 center` for tall). Copy it directly. Templates also include a `max-height: 470px` CSS safety net, so overflow is bounded even if an explicit directive is wrong.
- Speaker notes: `<!-- speaker notes go here -->`
- Background images: `![bg](image.png)` or `![bg right](image.png)` for split layouts

**Figure sizing lookup** (for figures without a pre-computed hint):

| Aspect (w/h) | Shape | Directive | Use case |
|---|---|---|---|
| ≥ 2.5 | Wide banner | `w:900 center` | Architecture, pipeline flows |
| 1.5 – 2.5 | Landscape | `h:420 center` | Bar charts, line plots |
| 0.9 – 1.5 | Near-square | `h:460 center` | Heatmaps, SHAP plots, matrices |
| < 0.9 | Portrait / tall | `h:470 center` + **no bullets** | Multi-panel stacks — give the figure the whole slide |

**When a slide has no matching figure** (no asset with overlapping caption keywords, no figure on the same page as the cited paragraph), route to Step 4 — do NOT leave a text-only slide where a visual would help the claim.

Save to `projects/viz-presentation/{name}/{name}.md`

**To switch templates later:** `bash .claude/skills/viz-presentation/scripts/apply_template.sh {template_id} projects/viz-presentation/{name}/{name}.md` — swaps the frontmatter + re-renders without touching the body.

## Step 4: Generate Missing Visuals (always offered)

After Step 3, scan the deck for slides that need a visual but don't have one. A slide needs a visual when its title makes a claim that a figure would strengthen — architectures, data trends, comparisons, mechanisms, workflows — but no extracted/provided figure fits.

**Always surface this to the user in one message:**

```
These slides would benefit from a visual, and I don't have a matching figure yet:
  • Slide 3 "Our insight: consensus assembly" → architecture diagram
  • Slide 7 "Temperature dominates prediction" → conceptual schematic
  • Slide 11 "Pipeline stages" → flowchart

Generate them? (pick any combination)
  - diagrams: Mermaid flowcharts/architecture via viz-diagram-code (fast, precise text)
  - illustrations: scientific figures via viz-nano-banana (realistic or sketchnote)
  - skip: leave as text-only for now
```

Wait for the user's choice. Don't generate without confirmation — image gen burns an API call and quota.

**Routing rules:**

| What you need | Route to | Best for |
|---|---|---|
| Flowchart, sequence diagram, architecture, mind map, timeline | `viz-diagram-code` (Mermaid) | Precise text labels, structural clarity |
| Scientific illustration, cell/pathway/schematic, experimental setup | `viz-nano-banana` (Gemini 3 Pro Image) | Realistic visuals, textbook-style figures |
| Hand-drawn architecture or workflow | `viz-excalidraw-diagram` | Sketchy aesthetic, informal diagrams |
| Data plot (chart/graph from actual numbers) | `sci-data-analysis` | Matplotlib/Plotly from a CSV or computation |

After generation, each produced image goes into `projects/viz-presentation/{name}/assets/` and is embedded with an aspect-aware Marp directive (see Step 3's sizing table) — image generators typically return 1024×1024 or 1024×768 so `h:460 center` is the default.

**Re-render (Step 5) after adding new images.**

## Step 5: Render

Run: `bash .claude/skills/viz-presentation/scripts/render_presentation.sh {path}.md all`

Default output: PDF + PPTX + HTML written alongside the .md file.

## Step 6: Auto-Preview (always, IDE-first)

After render succeeds, **always** open the deck. No opt-in prompt. Preference order: **IDE → browser**.

1. **Open PDF in IDE** — `cursor projects/viz-presentation/{name}/{name}.pdf` (falls back to `code {path}`). Cursor/VS Code render PDFs natively in a new editor tab. The PDF viewer extension (`tomoki1207.pdf`) is installed by the project installer via `setup-ide-previews.sh`.

2. **Open HTML live preview in IDE** — `cursor projects/viz-presentation/{name}/{name}.html`. With the Live Preview extension (`ms-vscode.live-server`, also bundled by the installer), the HTML renders in a webview split pane with keyboard nav (Space/arrows for slide advance, F for fullscreen).

3. **Only if IDE preview fails** (neither `cursor` nor `code` on PATH → server/CI environment), fall back to browser:
   ```bash
   URL=$(bash .claude/skills/viz-presentation/scripts/serve_preview.sh projects/viz-presentation/{name})
   ```
   Then open via `mcp__claude-in-chrome__navigate` at `${URL}/{name}.html`.

4. Copy PDF + PPTX to `~/Downloads/` for easy access.

4. Tell the user where the files are (absolute path) and that the preview is live. Offer **Drive push** per CLAUDE.md's Drive Push Gate for the PPTX/PDF.

5. Ask: *"How do these slides land? Want to adjust layout, swap template, or edit content?"* Common follow-ups:
   - **Template swap**: run `apply_template.sh {new_id} {deck.md}` — body is preserved
   - **Content edit**: edit the .md directly and re-run Step 5
   - **Figure size fix**: templates include a 470px max-height safety net, but explicit `h:X` on the image markdown is more predictable than `w:X`

6. Log feedback to `context/learnings.md` under `## viz-presentation`.

## Step 7: Learn a new template from a reference

Triggered when the user says "here's a style I like" + supplies a screenshot / URL / reference image, OR "save this style as a template" after a deck renders.

Full procedure in `references/template-catalog.md`. The critical point: templates are **two-file units** — a CSS frontmatter file AND a matching sample body that exercises its layouts. Skip the sample body and every template in the gallery will look identical except for color/font.

1. **Capture the reference** — if the user gave a file path, use `Read` directly. If a URL, run `.venv/bin/python /tmp/fc-screenshot.py {url} {out.png}` to get a PNG then `Read` that. For JS-heavy sites, Firecrawl is more reliable than WebFetch.

2. **Extract both layers — don't skip layer 2.** Per `template-catalog.md` Step 1:
   - **Layer 1 (visual system)**: background / gradient / hex codes / font family / 2 accent colors / decorative elements with positions
   - **Layer 2 (layout archetypes)**: for each slide type seen, note title position, decoration placement, annotations. Minimum: `lead` (title) and `content`. Ideal: `lead`, `content`, `stats`, `quote`, `figure`, `closing`.

3. **Ask user for id + description + best-for** (batched, one message).

4. **Write `templates/{id}.md`** — the CSS frontmatter. Every layout archetype from layer 2 becomes a `section.CLASS` rule. Include decorative `::before`/`::after` blobs with `position: absolute` on `section` + `overflow: hidden`. Always keep `section img { max-height: 470px; object-fit: contain }`.

5. **Write `templates/{id}.sample.md`** — the showcase body. Each slide exercises one layout class via `<!-- _class: NAME -->`. Include only the classes the template actually defines. This is what makes the gallery preview show real differences, not just color swaps.

6. **Register in `templates/catalog.json`** — append entry with id, name, description, best_for, base_theme, tags.

7. **Preview + confirm** — run `bash scripts/preview_themes.sh`, open gallery in browser. The new template renders against its own sample body, so layout differences are visible. If visual intent doesn't match: adjust `{id}.md` CSS or `{id}.sample.md` class usage, re-run. Iterate until it matches.

8. **Offer to apply** to the active deck via `apply_template.sh {id} {deck.md}`.

User-added templates persist in `.claude/skills/viz-presentation/templates/` and are available to every future deck.

## Rules

<!-- Populated by learnings feedback -->

- **Preview is mandatory after render** — Step 6 always runs, never behind a prompt.
- **Template gallery is the default** — Step 1.5 runs unless the user explicitly names a template or says "skip preview".
- **Figures default to height-constrained** (`h:X`) not width-constrained (`w:X`) — prevents the near-square / tall-figure overflow issue.
- **Never hand-write frontmatter** — pull from `templates/{id}.md`. Hand-written frontmatter won't match the catalog and won't benefit from future template updates.
- **Templates are two files, not one** — when learning a template (Step 7), always write both `{id}.md` (CSS + layout classes) AND `{id}.sample.md` (body that exercises those classes). Skipping the sample body makes the gallery preview identical across all templates except for color.
- **Extraction must capture layout archetypes**, not just palette. For each distinct slide type in the reference, map to a `section.CLASS` rule. Minimum `lead` + `content`; ideal also includes `stats`, `quote`, `figure`, `closing`.
