---
name: viz-nano-banana
description: >
  Generate images, infographics, and visual content via Gemini 3 Pro Image.
  Six styles: technical, notebook, comic, color, mono, scientific.
  Direct prompt or SVG blueprint modes.
  Triggers on: "generate an image", "create an infographic", "nano banana",
  "notebook sketch", "comic strip", "hand-drawn diagram", "visual for",
  "make an image of", "sketchnote", "storyboard", "generate a visual",
  "image of", "draw me", "scientific illustration", "diagram",
  "experimental setup", "pathway", "cell diagram", "molecular mechanism",
  "scientific figure", "schematic".
  Image generation backend for all skills needing visuals.
  Does NOT trigger for Excalidraw diagrams, charts/graphs, slide decks,
  or text-only content.
---

# Nano Banana — Image Generation via Gemini

Generate images and infographics using Gemini 3 Pro Image. The skill's value is in prompt construction — combining tested style templates with the user's content to get consistent, high-quality visual output.

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `context/learnings.md` | `## viz-nano-banana` section | Apply previous feedback |

No research_context files needed. This skill produces visuals, not branded copy.

## Dependencies

| Skill | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| None | — | `scripts/generate_image.py` is bundled directly | — |

## Step 0: Check API Key

Before generating, verify `GEMINI_API_KEY` is set. If missing, tell the user:
- "Image generation needs a Gemini API key. Get one free at https://ai.google.dev/"
- "Add `GEMINI_API_KEY=your-key` to your `.env` file"
- This skill cannot fall back — image generation requires the API.

## Step 1: Read Learnings

Read `context/learnings.md` → `## viz-nano-banana` for any previous feedback on styles, prompt patterns, or quality issues.

## Step 2: Understand the Request

Figure out what the user wants to visualize. Ask if unclear:
- What concept, workflow, or content to illustrate?
- Any style preference? (If not stated, suggest one based on context)
- For scientific illustrations: What biological/chemical/physical process? What level of detail (overview vs detailed)? Any reference figures to match? (Accept user style examples/descriptions and log preferences per D-16)
- Aspect ratio needs? (social post = 1:1, presentation = 16:9, story = 9:16)

## Step 3: Pick a Style — MUST CONFIRM WITH USER

Six styles available. Read `references/styles.md` for full prompt templates.

| Style | Best for | Suggest when |
|-------|----------|-------------|
| `technical` | Architecture, workflows, annotated screenshots | User mentions "workflow", "architecture", "annotate", SaaS tools |
| `notebook` | Educational content, summaries, how-tos | User mentions "notes", "summary", "explain", "learn" |
| `comic` | Step-by-step stories, sequences, narratives | User mentions "story", "steps", "before/after", "journey" |
| `color` | Marketing infographics, concept explainers | User mentions "infographic", "visual", "social post", marketing content |
| `mono` | Technical docs, dark-mode, minimalist | User mentions "clean", "minimal", "technical", "B&W" |
| `scientific` | Scientific illustrations, diagrams, schematics | User mentions "scientific", "experiment", "pathway", "cell", "molecular", "mechanism", "diagram", "schematic", "figure for paper" |

**MANDATORY: Always confirm the style with the user before generating.** Never auto-select silently. The flow is:

1. Based on the user's request and context (scientific paper? blog post? social media?), **suggest** 1-2 appropriate styles with a brief reason for each.
2. **Wait for the user to confirm** which style to use before proceeding.
3. Only skip confirmation if the user explicitly names a style (e.g., "use scientific style") or if running in a headless/pipeline context where the style is pre-specified in the prompt.

Example for a scientific paper request:
> "For figures in a scientific paper, I'd recommend:
> - **scientific** — publication-quality diagrams with clean labels and consistent color coding
> - **mono** — if you prefer a cleaner black-and-white look for print
>
> Which style works better for your paper?"

Example for a blog post request:
> "For a science blog post, I'd suggest:
> - **color** — warm, editorial-style illustrations that are engaging for non-specialists
> - **scientific** — if you want a more formal, publication-quality look even in the blog
>
> Which direction do you prefer?"

Note: For the `scientific` style, read `references/scientific-styles.md` for scientific prompt templates and sub-styles.

### Step 3b: Scientific Sub-Style — MUST CONFIRM WITH USER

Read `references/scientific-styles.md` for sub-style templates. Scientific illustrations have sub-types:

| Sub-Style | Best for | Suggest when |
|-----------|----------|-------------|
| `experimental-setup` | Lab equipment layouts, protocol diagrams | "experiment", "setup", "protocol", "equipment" |
| `biological-pathway` | Signaling pathways, metabolic pathways | "pathway", "signaling", "cascade", "metabolic" |
| `cell-diagram` | Cell cross-sections, organelle layouts | "cell", "organelle", "membrane", "nucleus" |
| `molecular-mechanism` | Protein interactions, binding events | "molecular", "protein", "binding", "receptor" |
| `flowchart` | Process flows, decision trees, algorithms | "flow", "process", "steps", "algorithm", "pipeline" |
| `conceptual-figure` | Abstract concepts, theory illustrations | "concept", "theory", "model", "framework", "overview" |

**MANDATORY: Always confirm the sub-style with the user before generating.** Suggest 1-2 sub-styles with reasoning, then wait for confirmation:

> "Based on your request, I'd suggest:
> - **conceptual-figure** — works well for illustrating the overall framework with abstract shapes and visual hierarchy
> - **flowchart** — better if you want to emphasize the step-by-step pipeline flow
>
> Which approach works better for your figure?"

**Style learning (per D-16):** After generating, if the scientist provides feedback or reference examples, log their preferences to `context/learnings.md` -> `## viz-nano-banana` with date and specific style notes (e.g., "Prefers clean minimalist pathways over detailed textbook-style, as of 2026-04-04"). In future sessions, read learnings and **propose** previously preferred styles — but still confirm: "Last time you preferred the clean minimalist approach for pathway diagrams — want to use that again, or try something different?"

## Step 4: Choose Generation Mode

### Mode A: Direct Prompt (default)

Best for most requests. Claude constructs a detailed prompt by combining:
1. The style template from `references/styles.md`
2. The user's content description
3. Composition instructions (what goes where, relative sizing, emphasis)

The prompt should be specific and visual — describe what the viewer sees, not abstract concepts. Include spatial relationships ("top-left", "center", "flowing right to left"), relative sizes, and the visual hierarchy.

### Mode B: SVG Blueprint (complex layouts only)

Use when the user needs precise control over element placement — multi-panel infographics, specific spatial relationships, or content-dense layouts. Read `references/layout-patterns.md` and `references/svg-construction.md`.

1. Build an SVG blueprint with exact positions, sizes, and text
2. Use the SVG as detailed composition instructions in the prompt: describe each element's position, size, color, and relationship to other elements
3. The SVG itself is not sent to Gemini — it's a planning tool for writing a better prompt

## Step 5: Generate

Run the bundled script:

```bash
uv run .claude/skills/viz-nano-banana/scripts/generate_image.py \
  --prompt "FULL CONSTRUCTED PROMPT" \
  --filename "projects/viz-nano-banana/{descriptive-name}_{YYYY-MM-DD}.png" \
  --resolution 1K \
  --aspect-ratio 16:9
```

**Options:**
- `--resolution`: `1K` (default), `2K`, `4K`
- `--aspect-ratio`: `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `4:5`, `5:4`, `21:9`
- `--input-image` / `-i`: For editing existing images (up to 14)
- `--dry-run`: Log the full constructed prompt and all parameters **without calling the Gemini API**. Use this to verify prompt construction and skill routing before spending API credits. Output includes: model, resolution, aspect ratio, output path, and the full prompt text.

**Dry-run example:**
```bash
uv run .claude/skills/viz-nano-banana/scripts/generate_image.py \
  --prompt "FULL CONSTRUCTED PROMPT" \
  --filename "output.png" \
  --resolution 1K \
  --aspect-ratio 16:9 \
  --dry-run
```

**Do NOT read the generated image back.** Report the saved path only.

## Step 6: Save and Report

**Always save output to disk.** Create the folder if it doesn't exist.

Save to: `projects/viz-nano-banana/{descriptive-name}_{YYYY-MM-DD}.png`

Tell the user the file path so they can view it.

## Step 7: Feedback

Ask: "How does this look? Want to adjust the style, composition, or try a different approach?"

Log feedback to `context/learnings.md` → `## viz-nano-banana` with date and context.

---

## Rules

*Updated when the user flags issues. Read before every run.*

---

## Self-Update

If the user flags an issue — wrong style, bad composition, missed detail — update the `## Rules` section immediately with the correction and today's date.
