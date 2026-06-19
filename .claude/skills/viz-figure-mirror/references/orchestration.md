# Orchestration — the loop spec

The Drawer and the Reviewer never talk directly. The orchestrator (the main
session) shuttles artifacts between them and decides when to stop. This file is the
authoritative wiring.

Original clean-room prose distilling the FigMirror loop (open project, no license
file). The decision rule and select-best fallback are reimplemented; the validator
and `select_best` live in `scripts/review_schema.py`.

---

## Roles

- **Orchestrator** (this session) — drives the iter loop, validates the Reviewer's
  JSON, decides accept / revise, forwards the Reviewer's `focus_themes` AND
  `anchor.what_is_right` (as a hard preserve list) back to the Drawer for the next
  iter.
- **Drawer** (`references/drawer.md`) — produces `figure_iter<N>.py`,
  `img_iter<N>.png`, `notes_iter<N>.md`, `floor_selfcheck_iter<N>.txt`. Runs its own
  floor check before handoff. Records anchor measurements at iter 0. Refuses to move
  a preserved property out of its class.
- **Reviewer** (`references/reviewer.md`) — fresh-context, vision-only. Sees
  reference + draft + L2 library + prior audit. Emits ONE strict JSON object.

State flows through workspace files; the roles are stateless across dispatch.

## Workspace layout

```
projects/viz-figure-mirror/{slug}/
  inputs/
    reference.png          # the cleaned reference crop (L1 anchor)
    data.txt               # parsed user data
  figure_iter0.py  img_iter0.png  notes_iter0.md  floor_selfcheck_iter0.txt
  audit_iter0.json
  ...                      # one set per iter
  selection.md             # chosen iter + reasoning (only if select-best ran)
  figure.py  figure.png  figure.pdf   # canonical artifacts (copies of chosen iter)
```

Pre-create every directory before dispatching — agents Write into existing dirs only.

## Pipeline

### 1. Preprocess

Stage the uploaded reference to `inputs/reference.png`. If the upload has captions,
page text, screenshot chrome, or neighbouring panels, crop conservatively to the
target figure first (preserve all axes, ticks, labels, legends, panel titles). If
no safe crop exists, keep the raw image and note it.

### 2. Data echo

Parse the user's data (CSV / TSV / markdown table / dirty terminal text). Echo back
rows x cols, column names, NaN cells, and a sample row. Proceed when the user
confirms (or has pre-authorized). Persist the echo. The Reviewer never sees this.

### 3. Iterate (default `max_iters = 6`)

For `N` in `0 .. max_iters - 1`:

1. **Drawer.** At N=0, brief: read the L2 library, do the iter-0 anchor pass, write
   `## Anchor measurements`. At N>0, brief: the prior audit JSON verbatim, the
   preserve list with its `[L1]/[L2]/[L1+L2]` prefixes, "address
   `violation_kinds` first, then `focus_themes` in order, but never move a
   preserved property out of its class." Do NOT translate themes into matplotlib
   parameters before handoff — that collapses the role separation.
2. The Drawer renders and runs its own floor check via `scripts/figure_quality.py`.
   It must not hand off a draft that fails its own check.
3. **Reviewer.** Stage the audit view: `reference.png` + `img_iter<N>.png` + the L2
   library + (if N>0) `audit_iter<N-1>.json`. Never stage the data or the code.
   Dispatch the Reviewer; capture its stdout as `audit_iter<N>.json`.
4. **Validate** with `validate_review` from `scripts/review_schema.py`. A schema
   error means the Reviewer misbehaved — re-dispatch once with a reminder that the
   output must be a single JSON object.
5. **Decide:**
   - `floor.passed && verdict == "ship"` -> accept iter N, stop.
   - else if `N == max_iters - 1` -> stop, fall through to select-best.
   - else -> continue (the Drawer addresses the floor / themes next iter).

The decision rule is intentionally small: three inputs (`floor.passed`, `verdict`,
budget remaining), one output (continue or stop). No score arithmetic.

### 3b. Reviewer unavailable (degraded / floor-only mode)

The Reviewer step needs a vision-capable model. If the Reviewer cannot run — no
multimodal model available, the dispatch errors, or it still returns non-JSON after
the single step-4 re-dispatch — do NOT stall or crash the loop. Degrade to
**floor-only mode**:

1. Treat the mechanical floor (`check_floor`) as the only judge for that iter.
   Synthesize a minimal audit record in place of the Reviewer JSON:
   `{"iter": N, "quality_floor": {"passed": <floor result>}, "fidelity": {"verdict": "close"}, "anchor": {"what_is_right": []}, "focus_themes": []}`.
   `verdict == "close"` (never `"ship"`) so the loop keeps improving until the budget,
   then hands off to select-best rather than declaring visual fidelity it cannot judge.
2. Persist it as `audit_iter<N>.json` and note `vision audit skipped (Reviewer
   unavailable)` in `notes_iter<N>.md` so the trajectory is honest.
3. At the budget, run the normal select-best fallback. With no `ship` and only
   floor-passing `close` iters, it picks the lowest-drift floor-passing iter (or the
   least-bad one if none passed the floor).
4. In the final summary to the user, state plainly that the figure cleared the
   mechanical floor but did **not** receive a vision fidelity review, so the style
   match against the reference is unverified — they should eyeball it before use.

Floor-only mode still produces a valid, floor-clean, editable figure; it only loses
the aesthetic-fidelity guarantee. Never silently present a floor-only result as if it
passed the Reviewer.

### 4. Select-best fallback (only if `ship` never fired)

Call `select_best(iterations)` from `scripts/review_schema.py`. Its policy:

1. Candidate set = iters whose floor passed AND verdict == `close`.
2. Among candidates, pick the lowest drift, where
   `drift = |aspect_drift| + |spine_count_drift|` when the Reviewer recorded those
   under `anchor.measurements`, else the iteration index (so an earlier, less-drifted
   iter wins). The most recent iter is NOT automatically best — that is the classic
   drift mistake.
3. No `close` candidate -> any floor-passing iter, lowest drift.
4. Nothing passed the floor -> least-bad (lowest drift overall).

Document the choice in `selection.md`. If the chosen iter is not the most recent,
that itself signals the loop drifted.

### 5. Canonical artifacts

Copy the chosen iter's `.py` and `.png` to `figure.py` / `figure.png`. Re-render
`figure.pdf` with `pdf.fonttype = 42`. Surface `figure.png` inline, give the paths
to `figure.py` / `figure.pdf`, and a one to two sentence trajectory summary. Then
follow the CLAUDE.md gates (Drive Push, Obsidian, IDE auto-open).

## What the orchestrator must NOT do

- Do not score the figure itself; the Reviewer is the only judge.
- Do not summarise the Reviewer's JSON in prose for the Drawer; pass it verbatim.
- Do not translate `focus_themes` into matplotlib mechanisms before handoff.
- Do not feed the data file or any code into the Reviewer's view. Vision only.
