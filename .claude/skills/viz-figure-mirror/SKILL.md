---
name: viz-figure-mirror
description: >
  Transfer the visual style of a reference paper figure onto the user's own data.
  Takes a screenshot of a figure from a paper plus tabular data and produces an
  editable matplotlib script in that figure's register, gated by a mechanical
  quality floor and a Drawer/Reviewer refinement loop. Output is a self-contained
  .py + PNG + Type-42 PDF. Triggers on: "match this figure style", "figure in the
  style of", "make my plot look like this paper", "publication figure from
  reference", "style transfer figure", "reproduce this figure with my data",
  "NeurIPS-quality version of this chart". Does NOT trigger for: plain data plots
  with no reference image (use sci-data-analysis), AI-generated illustrations (use
  viz-nano-banana), flowcharts/architecture/sequence diagrams (use
  viz-diagram-code), hand-drawn sketches (use viz-excalidraw-diagram).
---

# Figure Mirror

Render the user's data in the *visual style* of a reference figure from a top-tier
paper. The output is not a copy of the reference; it is the user's numbers wearing
the reference's typographic voice, palette, spine treatment, gridline weight, and
layout density. The deliverable is an editable matplotlib script the user owns,
plus a rendered PNG and a camera-ready Type-42 PDF.

Inspired by **FigMirror** (open project, no license file); the floor algorithm,
prompt prose, and convention values here are an independent clean-room
reimplementation.

## Outcome

A workspace under `projects/viz-figure-mirror/{slug}/`:

- `figure.py` — self-contained script with an inline DATA SECTOR and
  `pdf.fonttype = 42`. The user edits this.
- `figure.png` — rendered preview.
- `figure.pdf` — Type-42 camera-ready export.
- per-iteration artifacts (`figure_iter*.py`, `img_iter*.png`, `audit_iter*.json`).

## Input / output contract

| In | Out |
|----|-----|
| Reference image (PNG/JPG screenshot of a paper figure) | `figure.py` (editable matplotlib) |
| User data (CSV / TSV / pasted table / dirty terminal text) | `figure.png` + Type-42 `figure.pdf` |

Trigger requires **both** a reference image and data. With only data and no
reference, route to `sci-data-analysis` instead.

## Context Needs

| File | Load level | How it shapes this skill |
|------|-----------|--------------------------|
| `research_context/research-profile.md` | — | Not used |
| `context/learnings.md` | `## viz-figure-mirror` section | Apply previous feedback before starting |

## The two-role loop

The work is split between two roles that never talk directly. The orchestrator
(this session) shuttles artifacts between them.

- **Drawer** (`references/drawer.md`) — writes `figure_iter<N>.py`, renders it,
  runs its OWN floor self-check (`scripts/figure_quality.py`) before handoff, and
  records anchor measurements at iter 0. Grounds every choice in L1 or L2.
- **Reviewer** (`references/reviewer.md`) — a fresh-context vision-only audit. Sees
  the reference + the draft + the L2 library + the prior audit (never the data, never
  the code). Emits ONE strict JSON object validated by `scripts/review_schema.py`.

Full wiring, stop conditions, and the select-best fallback live in
`references/orchestration.md`.

## The grounding hierarchy (L1 / L2 / L3)

Every property of the figure traces to exactly one source:

- **L1 — the reference image.** Highest authority. What the reference visibly does
  is what the draft does. Measure PIL-reliable properties (full-image aspect,
  palette of large filled regions); eyeball the brittle ones with acknowledged
  uncertainty.
- **L2 — `references/aesthetic-library.md`.** Paper-figure conventions. The fallback
  class vocabulary for properties PIL cannot measure reliably (spine colour/width,
  gridline width, font weight) and the extension menu when the data has more series
  than the reference.
- **L3 — your own taste.** **Banned.** "I think it would look better" diverges the
  loop. If a choice cannot cite L1 or L2, drop it.

## The quality floor (mechanical, deterministic)

Before any aesthetic judgement, a figure must clear a mechanical floor enforced by
`scripts/figure_quality.py`. The floor is binary and catches the two defect classes
that make a figure unshippable regardless of style:

- `assert_no_text_overlap(fig)` — no two visible text bboxes (tick labels, titles,
  axis labels, annotations) may overlap.
- `assert_no_clipped_labels(fig)` — no text bbox may fall outside the canvas (tick
  labels centred on an axis extreme get a small font-proportional allowance; titles,
  axis labels, and annotations stay strict).
- `assert_no_legend_data_overlap(fig)` — no legend may sit on top of plotted data ink
  (bars, markers, lines, error bars). Conservative: a legend over empty whitespace, or
  one placed outside the axes, passes; only a legend clearly occluding data is flagged.
- `check_floor(fig) -> {"passed": bool, "violations": [...]}` — same checks, no
  raise, for the loop (`violation kind` ∈ `text_overlap` / `label_clipped` /
  `legend_over_data`).

The module also carries `PUBLICATION_RCPARAMS` (anti-slop: hairline left+bottom
spines, no tick marks, light-grey gridlines, Type-42 fonts, real minus glyph) and
`apply_publication_style(ax)`. The Drawer self-checks the floor before every
handoff; the Reviewer never sees a draft that fails the Drawer's own check.

## Workflow

1. **Stage workspace.** Create `projects/viz-figure-mirror/{slug}/inputs/`. Save the
   reference to `reference.png`, the parsed data to `data.txt`.
2. **Echo the data parse.** Show the user rows x cols, columns, NaN cells, a sample
   row. Confirm before drawing.
3. **Iterate** up to `max_iters` (default 6). Per iter: Drawer renders + self-checks
   floor -> Reviewer audits -> validate JSON -> decide.
4. **Stop** when `floor.passed && verdict == "ship"`. Otherwise at the budget, run
   the select-best fallback (`select_best` in `scripts/review_schema.py`).
5. **Write canonical artifacts** (`figure.py` / `.png` / Type-42 `.pdf`), then offer
   the Drive Push Gate and Figure Proposal follow-ups per CLAUDE.md.

## Self-containment

This skill carries its OWN floor module (`scripts/figure_quality.py`) and its OWN
schema validator (`scripts/review_schema.py`). It does not import from other skills.

## Dependencies

| Dependency | Required? | Provides | Fallback without it |
|---|---|---|---|
| `matplotlib` | Required | Figure rendering, the mechanical quality floor, Type-42 PDF export | None — the skill is non-functional |
| `pillow` (`PIL`) | Required | PIL-measurement of the reference image (aspect, palette of large filled regions) | None — L1 measurement + floor color checks non-functional |
| `numpy` | Required (transitive via matplotlib) | Array handling in generated scripts | None — installed with matplotlib |
| Vision-capable model | Required for the Reviewer audit | Multimodal reference-vs-draft critique that drives the refinement loop | **Floor-only mode** — the loop runs the mechanical floor + `select_best` without aesthetic review (see `references/orchestration.md` → "Reviewer unavailable") |

Run `bash scripts/setup.sh` once per machine to verify/install `matplotlib` + `pillow`.
No API key and no network are needed for the mechanical floor; only the Reviewer audit
needs a vision-capable model.
