---
name: viz-diagram-code
description: >
  Generate polished diagrams from code using Mermaid -- flowcharts, sequence
  diagrams, architecture diagrams, mind maps, timelines, class diagrams, and
  comparison layouts. Produces SVG + PNG with precise text, professional
  styling, and color themes. Ideal for blog posts, tutorials, and educational
  content where text accuracy matters.
  Triggers on: "mermaid diagram", "flowchart", "sequence diagram",
  "architecture diagram", "mind map diagram", "timeline diagram",
  "class diagram", "process diagram", "comparison diagram",
  "diagram with code", "styled diagram", "code diagram".
  Does NOT trigger for: hand-drawn/sketch diagrams (use viz-excalidraw-diagram),
  AI-generated illustrations (use viz-nano-banana), data plots (use sci-data-analysis).
---

# viz-diagram-code

**Outcome:** Mermaid diagram files (.mmd) + rendered SVG + PNG saved to `projects/viz-diagram-code/{diagram-name}/`. Every diagram has precise text labels and professional styling.

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `context/learnings.md` | `## viz-diagram-code` section | Previous feedback |

No brand context needed -- this skill produces technical diagrams.

## Dependencies

| Skill | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| None | -- | `scripts/setup.sh` handles mermaid-cli installation | -- |

Requires: Node.js (for npx mmdc). Run `scripts/setup.sh` if mmdc is missing.

---

## Methodology

### Step 0: Auto-Setup

Run `bash .claude/skills/viz-diagram-code/scripts/setup.sh` to check/install mermaid-cli.
Only runs if `npx mmdc --version` fails.

### Step 1: Understand the Request

Parse what the user needs:
- **Type**: flowchart, sequence, architecture, mind map, timeline, class, state, comparison
- **Content**: what concepts/components to include
- **Style preferences**: colors, orientation (TB/LR), theme (neutral/forest/dark)
- **Context**: is this for a blog post, tutorial, paper, or standalone?

If the user provides a concept description, translate it into the right diagram type.
Default to `flowchart` if ambiguous.

**Type selection guide:**
| User describes... | Use |
|-------------------|-----|
| A process, pipeline, workflow | flowchart (TB) |
| Message passing, protocols, API calls | sequence diagram |
| System components, layers | flowchart with subgraphs (architecture) |
| Concept breakdown, brainstorm | mind map |
| Historical events, project phases | timeline |
| Data models, class hierarchies, taxonomies | class diagram |
| States and transitions (experimental protocols) | state diagram |
| Side-by-side contrast of two approaches | flowchart LR with parallel subgraphs |

### Step 2: Generate Mermaid Code

Read `references/diagram-types.md` for syntax and patterns.
Read `references/styling-guide.md` for themes and color palettes.

1. Write the Mermaid code (.mmd file)
2. Apply styling:
   - Use `%%{init: {'theme': 'neutral'}}%%` for scientific content (default)
   - Add `classDef` statements for color-coding components
   - Use descriptive node IDs for readability
3. For complex diagrams, use subgraphs to group related components
4. Create output directory: `projects/viz-diagram-code/{diagram-name}/`
5. Save to `projects/viz-diagram-code/{diagram-name}/{diagram-name}.mmd`

**Label safety — MANDATORY.** Mermaid v10+ treats unquoted `*`, `?`, `:`, `/`, `<br/>`, `@`, `#`, `$`, `%` inside node labels (`[...]`) or diamond decisions (`{...}`) as syntax-breaking, producing a silent "Syntax error in text" bomb icon at render time. Always wrap any label containing these characters in double quotes:

```
✗ WRONG                               ✓ RIGHT
SCI[sci-* science skills]             SCI["sci-* science skills"]
Mem[context/memory/date.md]           Mem["context/memory/date.md"]
Check{is it ready?}                   Check{"is it ready?"}
SOUL[SOUL.md<br/>contract]            SOUL["SOUL.md<br/>contract"]
```

Replace unicode arrows (`→`) and comparators (`≥`) inside labels with ASCII (`->`, `+`) to stay safe across parsers.

### Step 2.5: Lint before render

Before calling the renderer, lint the `.mmd` (or the host `.md` if the diagram lives inside a markdown file) via the repo-level utility:

```bash
python3 scripts/preview-md.py <file>.md --lint-only
```

The linter flags every unsafe bare-bracket label with a line number and the exact fix. Fix all warnings before proceeding to Step 3 — a `.mmd` that lints clean renders reliably; one that doesn't will waste a render cycle.

### Step 3: Render to Image

Run:
```bash
bash .claude/skills/viz-diagram-code/scripts/render_diagram.sh {path}.mmd {output_base} {theme}
```

This produces:
- `{diagram-name}.svg` -- vector format, scales perfectly
- `{diagram-name}.png` -- raster format for embedding

### Step 4: Validate and Iterate

Show the rendered PNG to the user. Ask:
- "Does this capture the concept correctly?"
- "Want to adjust colors, layout, or add/remove components?"

If the user wants changes, edit the .mmd file and re-render. Mermaid code is easy to iterate on.

### Step 5: Auto-download

Copy PNG and SVG to `~/Downloads/` for easy access.
Show the full absolute file paths so the user can click to open.

---

## Rules

*Empty -- populated by user feedback via context/learnings.md*
