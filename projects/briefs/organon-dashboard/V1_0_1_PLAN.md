# v1.0.1+ Implementation Plan — Organon Dashboard

**Created:** 2026-05-07, after the v1.0 ship gate (commit `d5a4eb2`).
**Branch:** `main`. **Source of truth:** `DOGFOOD_REPORT_v2.md` (1 🔴 closed, 14 🟠 + 18 🟡 captured).

This plan is self-contained. A fresh session reading only this doc and the source files it points at can land any of Phases 10–16 without re-deriving context. Read §1–§4 always; pick the phase you want to land in §5 onward.

---

## 1. Where things stand on day 0 of v1.0.1

```
d5a4eb2  Phase 9 hotfix (v1.0 ship gate) — code-span guard for cite/fig/math   ← latest
74a1d64  stress-suite — sync 4 assertions with Phase 5 + Phase 8 contracts
678f2bb  Phase 8 (fix-sprint) — strict __root__ flip
fbc059b  Phase 7 (fix-sprint) — renderer parity + UX polish
71863ed  Phase 6 (fix-sprint) — direct-Python stat tests + LLM as opt-in interpret
a00140c  Phase 5 (fix-sprint) — citation pipeline correctness
```

**Verified gates after `d5a4eb2`:**
- `npm test` → **108 / 108** (99 baseline + 9 Phase 9 regression)
- `npm run typecheck` → clean
- `npm run build` → clean (37 routes)
- `python3 tests/stress-suite.py` → **52 / 52**
- Live walk verification: backticked `\cite{paper-id}` / `\fig{fig-id}` / `$\Delta$` / `$$\bar{x}$$` render as inline-code in preview; export 201 for empty manuscripts.

**v1.0 status: SHIP-READY pending tag + push** (`git tag v1.0 && git push organon v1.0` then `git push organon main`). Don't push to `origin` (chronically diverged).

---

## 2. The contract

The 9 Phase 9 regression tests in `tests/draft-code-spans.test.mjs` ARE the contract. Touching them means breaking the v1.0 ship guarantee. If a v1.0.1 feature requires that contract to flex, write a *new* assertion that documents the exception — do NOT loosen the existing one.

Same with the 8 invariants from `NEXT_SESSION_2026-05-07.md` §5. They survived 9 phases. v1.0.1 must preserve them too.

---

## 3. Pre-flight (run before every phase)

```bash
cd /Users/keremdelikoyun/Projects/scientific-os
git log --oneline -5            # confirm d5a4eb2 (or later) on top

cd projects/briefs/organon-dashboard
npm test                        # expect 108/108 minimum
npm run typecheck && npm run build
lsof -i :8769                   # if empty: npm run dev
python3 tests/stress-suite.py   # 52/52
```

If anything is not green — diagnose first. Don't start a new phase on a broken baseline.

---

## 4. Phase ordering rationale

Order is by **researcher impact × shared-infra coupling**, not by finding-letter:

| Phase | Why this order | Couples with |
|---|---|---|
| 10 — Generate with AI | DR-3 was the single most-cited researcher finding. Until per-section AI generation exists, every fresh user hits the same "how does Organon help me write" question. | Touches `/api/draft` + sci-writing skill; reuses Phase 4 RunStateCard contract. |
| 11 — Workspace state persistence | L-1 + H-1 are identical fix shapes. Doing them together is one PR not two. | Lifts state to URL + localStorage; `/draft` will benefit too once Phase 10 lands. |
| 12 — Stat workspace polish | Mix of 🟠 + 🟡; D-9 (regression diagnostics) is research-correctness load-bearing. | `scripts/run_stat_test.py` extension. |
| 13 — Hypothesis workspace | Persona editor + per-persona progress signals. H-4 desync bug is confusing. | sci-council emit upgrade for per-persona artifacts. |
| 14 — Figures workspace | ANNOTATE-vs-MASK separation is the biggest UX cleanup; new annotation layer is non-trivial. | New `<canvas>` annotation persistence layer. |
| 15 — Draft workspace polish | KaTeX accents, verify-gate code-span awareness, etc. — small additions on top of Phase 9 / 10 foundation. | Touches the same files as Phase 9 + 10. |
| 16 — Export polish | One UI-only fix (EX-1). | Standalone. |

After Phase 16, the v1.0.1 surface is closed. v1.1+ feature track follows in §13.

---

## 5. Phase 10 — "Generate with AI" sprint

**Goal:** close DR-3 + DR-5. After this phase, a researcher creating a fresh manuscript can press one button per section to have Organon draft from linked papers + stat results + brief, and one button on create-manuscript to propose 3–5 candidate titles.

### 5.1 Scope

- Per-section **GENERATE** button (visually distinct from the DRAFT/REVIEWED/FINAL status badge). Click → fires sci-writing skill in section-aware mode → SSE → result replaces the section body.
- Manuscript-level **Draft all sections** wizard. Optional one-click "draft everything" that fans out across sections sequentially (or parallel with cap=2 to avoid LLM rate limits).
- Manuscript-create form **Propose title** button. Click → fires sci-writing skill in `title` mode → returns 3–5 candidates → user picks → field is populated.

### 5.2 Files touched

| File | Change |
|---|---|
| **NEW** `src/components/draft/section-generate-button.tsx` | per-section generate button; renders next to status badge but visually distinct |
| **NEW** `src/app/api/draft/[slug]/generate-section/route.ts` | SSE route that spawns sci-writing with section_type + context |
| **NEW** `src/app/api/draft/[slug]/generate-title/route.ts` | one-shot route returning 3–5 title candidates |
| `src/components/draft/section-list.tsx` | wire generate-button alongside the status badge |
| `src/components/draft/manuscript-workspace.tsx` | add "Draft all sections" header button + RunStateCard mount on /draft (closes deferred H-5 follow-up too) |
| `src/components/draft/manuscript-create-form.tsx` | propose-title button + multi-candidate picker UI |
| `.claude/skills/sci-writing/SKILL.md` | document section-mode (`introduction` / `methods` / `results` / `discussion` / `abstract` / `title`) parameter; specify output shape (markdown body, no JSON) |
| `tests/draft-generate.test.mjs` | NEW — 6+ regression tests |

### 5.3 sci-writing section-mode contract (must lock before coding the route)

The skill takes:
- `section_type`: one of `introduction | methods | results | discussion | abstract | title`
- `manuscript_brief`: the brief.md contents
- `linked_papers`: array of paper artifacts (id, cite_key, title, abstract, year)
- `linked_stat_results`: array of stat-result artifacts (for results section)
- `linked_figures`: array of figure artifacts (for results / discussion)
- `existing_sections`: array of {title, body} for whole-manuscript context (Phase 10b — wire in if cheap, otherwise leave for Phase 13)

Returns:
- `markdown` body for the section (NO `<span>` HTML; use `\cite{cite_key}` and `\fig{fig_id}` markdown-native tokens; KaTeX-subset math via `$...$` or `$$...$$`)
- `cited_papers`: list of cite_keys actually used (so the route can update linked_paper_ids)
- `cited_figures`: list of fig_ids actually used

For the title mode specifically: return `candidates: [{title, rationale}]` — 3–5 entries.

### 5.4 Tests (regression contract for Phase 10)

```javascript
// tests/draft-generate.test.mjs
test("section-generate-button is visually distinct from the status badge");
test("/api/draft/[slug]/generate-section spawns sci-writing with section_type param");
test("/api/draft/[slug]/generate-section emits the standard runner exit contract (Phase 4)");
test("/api/draft/[slug]/generate-title returns 3-5 candidates with rationale");
test("Draft-all wizard fans out sequentially with cap=2 parallelism");
test("RunStateCard now mounts on /draft (closes Phase 6 deferred follow-up)");
```

### 5.5 Effort + risks

- **Effort:** ~1 day end-to-end.
- **Risk 1 — sci-writing skill section-mode doesn't exist yet.** Likely needs a new file under `.claude/skills/sci-writing/references/` documenting per-section prompts. Allocate 2 hours for the skill side alone.
- **Risk 2 — claude-runner cwd = organonRoot.** Per Phase 1 invariant, the runner cwd stays at organonRoot; the active project is communicated via `active_project_slug=` in the prompt. Don't accidentally change cwd.
- **Risk 3 — SSE `done` event must include `success / reason / exit_code / message`** per Phase 4 contract. Use the same `lastExit` capture pattern as `data/interpret`, `draft/[slug]/action`, `hypothesis/reconcile`.

### 5.6 Commit pattern

`dashboard: Phase 10 (v1.0.1) — per-section GENERATE button + propose-title + RunStateCard on /draft`

One atomic commit. Stage explicit (not `git add .`).

---

## 6. Phase 11 — Workspace state persistence

**Goal:** close L-1 + H-1 + H-8. After this phase, navigating Lit → Hypothesis → back to Lit preserves the search query + results; same for the hypothesis claim form; and a hydration badge confirms loaded data is complete.

### 6.1 Scope

- Lift `/lit` search state to URL query params (already partially there — `?q=…&sources=…` exists; need `&saved=...&page=...` for full restore).
- Add `localStorage` ring-buffer keyed by project slug for "recent searches" (~10 entries).
- Same for `/hypothesis` claim form (URL params for hyp_id; localStorage for the WIP claim text).
- New `hydrationStatus = { critiques: N/M, synthesis: 'present' }` on `/hypothesis` server response; render as a small badge in the workspace header.

### 6.2 Files touched

| File | Change |
|---|---|
| `src/app/lit/page.tsx` | hydrate from URL params on mount |
| `src/components/lit/lit-workspace.tsx` | reflect URL state, write to localStorage on search; add "Recent" dropdown |
| `src/app/hypothesis/page.tsx` | same shape for claim form + hyp_id |
| `src/components/hypothesis/hypothesis-workspace.tsx` | same; add hydrationStatus badge render |
| **NEW** `src/lib/state/recent-searches.ts` | thin localStorage wrapper with project-slug keying + 10-entry ring |
| `tests/state-persistence.test.mjs` | NEW — 4 regression tests |

### 6.3 Tests

```javascript
test("lit-workspace re-hydrates query + sources + saved-papers from URL params");
test("recent-searches localStorage ring keeps max 10 entries per project");
test("hypothesis-workspace re-hydrates claim form draft from localStorage");
test("hypothesis page server response includes hydrationStatus { critiques, synthesis }");
```

### 6.4 Effort + risks

- **Effort:** half day.
- **Risk 1 — localStorage SSR issue.** Next.js 16 RSC default. Wrap localStorage reads in `useEffect` and `typeof window !== 'undefined'` guards.
- **Risk 2 — URL bloat.** If `saved=...` becomes a long list of paper IDs, the URL gets ugly. Cap at 5 most-recent saves; full library still renders from server state.

### 6.5 Commit pattern

`dashboard: Phase 11 (v1.0.1) — workspace state persistence (L-1 + H-1 + H-8)`

---

## 7. Phase 12 — Stat workspace polish

**Goal:** close D-1, D-2, D-3, D-4, D-5, D-7, D-8, D-9. Most are 🟡 polish; D-7 + D-9 are 🟠 and merit dedicated commits.

### 7.1 Sub-phases (commit one each)

**12a — Result management (D-7).** Add × button per result card; soft-archive flag; "Show N archived" toggle. Files: `src/components/data/results-panel.tsx` + new DELETE `/api/data/[file]/results/[run]` route. Tests: 3 (delete, archive, show-archived).

**12b — Regression diagnostics (D-9).** Extend `scripts/run_stat_test.py` linear-regression branch to compute Breusch-Pagan (homoscedasticity), Shapiro on residuals (residual_normality), Durbin-Watson if a time-like predictor exists (linearity proxy), VIF (no_multicollinearity). Emit them in the result card alongside ANOVA's PASS/FAIL pattern. Files: `scripts/run_stat_test.py` + `src/components/data/result-card.tsx` (already renders ANOVA assumptions; just unblock the regression branch). Tests: 3 (each diagnostic emits).

**12c — Polish bundle (D-1, D-2, D-3, D-4, D-5, D-8).**
- D-1: rename UNKNOWN → PENDING with tooltip "checked at run time".
- D-2: claude-runner attaches `< /dev/null` by default + filters runner stderr from the SSE prose stream.
- D-3: result panel "result is for outcome X / picker shows Y" hint when they diverge.
- D-4: run-id generator uses local-day not UTC (or the inverse — be consistent).
- D-5: file-upload icon in `src/components/data/file-upload.tsx`.
- D-8: select-all / select-none on regression-picker columns (combine with H-2 fix shape — write as a shared `BulkSelect` component).

Files: across `src/components/data/`, `src/lib/skills/claude-runner.ts`, `src/lib/runs/id.ts`. Tests: 4 (one per non-trivial change).

### 7.2 Effort

- 12a: 3 hours.
- 12b: 4 hours (Python diagnostics are well-known stats).
- 12c: 5 hours (six small fixes + shared BulkSelect).
- **Total Phase 12: ~1.5 days.**

### 7.3 Commit pattern

```
dashboard: Phase 12a (v1.0.1) — discard / archive stat result (D-7)
dashboard: Phase 12b (v1.0.1) — regression assumption diagnostics (D-9)
dashboard: Phase 12c (v1.0.1) — stat workspace polish bundle (D-1 D-2 D-3 D-4 D-5 D-8)
```

---

## 8. Phase 13 — Hypothesis workspace

**Goal:** close H-2, H-3, H-4, H-5, H-6, H-7. H-1 + H-8 already covered in Phase 11.

### 8.1 Sub-phases

**13a — Persona editor refactor (H-3 + H-4).** Add `active: boolean` to persona schema; add per-persona checkbox; fix the editor/header desync (bind header to editor state directly, not last-saved). Files: `src/components/hypothesis/personas-editor.tsx` + `hypotheses/personas.json` shape. Tests: 4 (active toggle, save flush, header sync, defaults-button warning).

**13b — Per-persona progress + per-persona retry (H-5 + U4 from v2 walk).** Two coupled additions, both required because the failure mode the walk found is "one persona's critique came back empty" — without per-persona emit there's no way to know *which* one, and without per-persona retry the only recovery is to re-run all three.

  - **Per-persona emit:** sci-council skill emits one `{"_artifact":"persona-critique", "persona": "skeptic", ...}` JSON line per persona as each finishes. `hypothesis-workspace.tsx` consumes them and updates per-persona cards independently.
  - **Per-persona retry:** when a critique arrives with empty `commentary` (or no critique arrives for a persona by the time the run completes), the per-persona card surfaces a `Retry {persona}` button that fires `/api/hypothesis/[id]/retry-persona` with `{persona_slug}`. The route spawns sci-council in single-persona mode (`personas=[skeptic]`), the workspace replaces only that persona's critique on the new artifact event. Existing two-persona critiques remain in place — no full re-fanout.
  - **Files:** `.claude/skills/sci-council/SKILL.md` Step 1.5 emit + single-persona mode contract; `src/components/hypothesis/council-fanout.tsx` (per-persona Retry button on empty-critique cards); `src/app/api/hypothesis/[id]/retry-persona/route.ts` (NEW); `src/components/hypothesis/hypothesis-workspace.tsx` (route hookup, emptiness-detection helper).
  - **Tests:** 3 (mid-run emit, late-finishing persona shows correctly, retry-persona replaces only the targeted critique without disturbing siblings).

**13c — Synthesis structured render + apply (H-6 + H-7).** "PROPOSED EXPERIMENT" JSON renders as collapsible numbered stages; "papers_to_drop_from_linked_set" / "papers_to_retain_as_evidence" arrays surface as APPLY button. Files: `src/components/hypothesis/synthesis-card.tsx` + new mutation route. Tests: 3.

**13d — Bulk-select on paper picker (H-2).** Combine with D-8 — share the same `BulkSelect` component. Files: `src/components/hypothesis/paper-picker.tsx`.

### 8.2 Effort + risks

- 13a: 4 hours. Risk: schema change to `personas.json` — write a migration that backfills `active: true`.
- 13b: 5 hours. Risk: changing sci-council emit protocol affects Session 4's existing critiques on disk. Make consumer tolerant of both old (single end-of-run emit) and new (per-persona emit) shapes.
- 13c: 4 hours. Risk: synthesis JSON shape may vary across runs. Use a permissive zod-style parse with falls-back to raw-JSON-block if schema mismatches.
- 13d: 1 hour (after Phase 12c lands the shared BulkSelect).
- **Total Phase 13: ~1.5 days.**

### 8.3 Commit pattern

```
dashboard: Phase 13a (v1.0.1) — persona editor refactor (H-3 + H-4)
dashboard: Phase 13b (v1.0.1) — per-persona progress signal (H-5)
dashboard: Phase 13c (v1.0.1) — structured synthesis render + apply-recommendation (H-6 + H-7)
dashboard: Phase 13d (v1.0.1) — paper picker bulk-select (H-2)
```

---

## 9. Phase 14 — Figures workspace

**Goal:** close F-1, F-2, F-3, F-4. F-5 (detailed legend generator) is v1.1+ — defer.

### 9.1 Sub-phases

**14a — Workflow guided-flow (F-4).** Step indicator across the top of `/figures`: "1. Generate ✓ · 2. Mask · 3. Edit prompt · 4. Apply edit · 5. Lock + caption" with each step lighting up as available. Progressive disclosure: hide EDIT PROMPT until a mask exists; hide LOCK + CAPTION until an edit landed. Files: `src/app/figures/page.tsx` + `src/components/figures/figure-canvas.tsx`. Tests: 3.

**14b — Annotate vs Mask separation (F-2).** New ANNOTATE mode toolbar with PEN (with color + thickness) / ARROW / TEXT / ERASER (selective delete) — does NOT trigger inpaint. Existing CIRCLE / LASSO / RECTANGLE renamed to MASK mode and shown only when "Edit with AI" mode is active. Files: `src/components/figures/figure-canvas.tsx` + new annotation layer + persistence under each figure's directory. Tests: 4.

**14c — Version history (F-3).** Every APPLY EDIT bumps version (v1 → v2 → v3); version selector in header; original always retrievable via dropdown. Files: `src/components/figures/figure-canvas.tsx` + `src/lib/figures/version-store.ts`. Tests: 3.

**14d — Project switcher search/grouping (F-1).** Search input at top of project dropdown; group BRIEFS / PROJECTS into collapsible sections; pinned-favorites at top (localStorage). Files: `src/components/header/project-switcher.tsx`. Tests: 2.

### 9.2 Effort + risks

- 14a: 3 hours.
- 14b: 6 hours. Risk: persistence shape for annotation strokes (probably a sibling `<fig>.annotations.json` per figure). Ensure round-trip preserves stroke order.
- 14c: 3 hours. Risk: existing figures already have implicit v1 only; backfill `versions: ["v1"]` array on first load.
- 14d: 2 hours.
- **Total Phase 14: ~2 days.**

### 9.3 Commit pattern

```
dashboard: Phase 14a (v1.0.1) — figures guided-flow header (F-4)
dashboard: Phase 14b (v1.0.1) — ANNOTATE mode + selective delete (F-2)
dashboard: Phase 14c (v1.0.1) — figure version history (F-3)
dashboard: Phase 14d (v1.0.1) — project switcher search + grouping (F-1)
```

---

## 10. Phase 15 — Draft workspace polish

**Goal:** close DR-2, DR-4. DR-3 + DR-5 already in Phase 10. DR-6, DR-7, DR-8 are v1.1+ — defer.

### 10.1 Sub-phases

**15a — KaTeX accent expansion (DR-2).** Add `\bar`, `\hat`, `\tilde`, `\vec`, `\dot`, `\ddot` to the vendored KaTeX subset. ~30 lines of additions in `src/lib/draft/katex-subset.ts`. Tests: 1 covering all six accents.

**15b — verify_ops.py code-span awareness (DR-4).** `check_inline_attributions` skips fenced code blocks AND inline backtick spans when scanning for citation markers. Closes the false-positive on dogfood reports describing citation syntax. Files: `scripts/verify_ops.py:check_inline_attributions` + tests under `tests/python/`. This is python-side, not dashboard — but Phase 9 already proved the bug exists.

### 10.2 Effort

- 15a: 2 hours.
- 15b: 2 hours.
- **Total Phase 15: half day.**

### 10.3 Commit pattern

```
dashboard: Phase 15a (v1.0.1) — KaTeX accent expansion (DR-2)
sci-writing: Phase 15b (v1.0.1) — verify_ops code-span awareness (DR-4)
```

(Note: 15b commit subject is `sci-writing:` not `dashboard:` since it touches the verify-gate, not the dashboard.)

---

## 11. Phase 16 — Export polish (EX-1)

**Goal:** close EX-1.

### 11.1 Scope

Export error pill expandable to a full panel listing unresolved cite-keys + fig-ids, with "fix in editor" links per row.

### 11.2 Files touched

- `src/components/draft/export-menu.tsx` — render expanded panel on click
- `src/app/api/draft/[slug]/export/route.ts` — confirm 422 response body shape includes the `unresolvedCites` + `unresolvedFigs` arrays (already does via `assembleMarkdown`; verify no truncation)

### 11.3 Tests

```javascript
test("export menu expands to a panel listing unresolved cite-keys + fig-ids");
test("each unresolved entry has a 'fix in editor' link that scrolls to the section");
```

### 11.4 Effort + commit

- 1 hour.
- `dashboard: Phase 16 (v1.0.1) — expandable export error panel (EX-1)`

---

## 12. Cumulative effort + ordering chart

| Phase | Items | Effort | Commit count | Files touched |
|---|---|---|---|---|
| 10 | DR-3 + DR-5 | 1 day | 1 | 8 |
| 11 | L-1 + H-1 + H-8 | 0.5 day | 1 | 6 |
| 12 | D-1..D-5, D-7, D-8, D-9 | 1.5 days | 3 | ~10 |
| 13 | H-2..H-7 | 1.5 days | 4 | ~8 |
| 14 | F-1..F-4 | 2 days | 4 | ~6 |
| 15 | DR-2, DR-4 | 0.5 day | 2 | 3 |
| 16 | EX-1 | 1 hour | 1 | 2 |
| **Total v1.0.1** | **20 items** | **~7 days** | **16 atomic commits** | **~43 files** |

If shipped as v1.0.1, this closes everything except v1.1+ feature requests.

---

## 13. v1.1+ feature track (NOT in v1.0.1 scope)

These are real feature work (not bug fixes). Planning them belongs in a separate roadmap doc, not in v1.0.1. Captured here so they don't get lost:

| ID | Feature | Why deferred to v1.1+ |
|---|---|---|
| D-6 | Ad-hoc chat-driven data analysis tab | New skill route + new UI surface — not a polish fix |
| DR-6 | Whole-paper-aware AI editing + chat panel with selection-context (Cursor-style) | Architectural addition; multi-week build |
| DR-7 | Drag-and-drop figure placement in preview | Bidirectional source-to-rendered position map needed |
| DR-8 | Typography / layout controls (justified, fonts, two-column) | Stylesheet preset registry + venue-style configs |
| F-5 | Detailed figure-legend generator with iterative edit | New sci-writing mode + new UI panel |

---

## 14. Single-session decision tree

Pick one phase per session. Do NOT mix phases — each is one atomic-commit-scoped sprint.

```
Have appetite for ≥ 6 hours?
├── Yes — pick Phase 10 (Generate with AI). Biggest researcher unlock.
└── No — pick Phase 11 (state persistence). Half day, single commit, big UX win.

Already shipped Phase 10 + 11?
├── Yes — pick by what bugged you most in the v2 walk:
│   ├── Stats felt thin — Phase 12.
│   ├── Hypothesis workflow felt incomplete — Phase 13.
│   ├── Figures editing confusing — Phase 14.
│   └── Just want to ship small wins — Phase 16, then Phase 15.
└── No — circle back.
```

---

## 15. Common pitfalls (carry-forward from Phases 1–9)

These bit during the fix-sprint and will bite v1.0.1 work. Already documented in `NEXT_SESSION_2026-05-07.md` §9; reproducing the load-bearing ones:

1. **`npm install` is denied** — don't add deps. Hand-roll if needed (KaTeX subset is ~140 lines, Phase 9's code-aware helper is ~50 lines).
2. **`request.signal` aborts the runner on tab close** — don't fight it.
3. **`claude-runner` cwd is `organonRoot()`, not `project.path`** — never change this.
4. **Test files run under plain Node ESM, no TS** — read source as text + regex-match for structural assertions; mirror behaviour in plain JS.
5. **Read-before-edit hook is over-eager** — fires even on files just written. Edits succeed regardless.
6. **`?project=` strict mode (Phase 8)** — every API route fetch needs the param explicitly. New routes added in v1.0.1 must use `resolveProjectFromRequest`.
7. **Tailwind tokens live in the theme** — `bg-bg-soft`, `text-text-dim`, `text-accent`, etc. Don't reach for arbitrary colors.
8. **Stage commits scope explicit** — never `git add .`. Dogfood data dirs are intentionally untracked.
9. **Co-author convention** — `Co-Authored-By: Claude <noreply@anthropic.com>` only.
10. **Push to `organon` remote, not `origin`** — origin is chronically diverged; never force-push it.
11. **Phase 9 hotfix is the contract** — `tests/draft-code-spans.test.mjs` 9 tests must pass. If a v1.0.1 feature seems to need them to flex, write a NEW assertion documenting the exception.

---

## 16. Pre-Phase-10 checklist (next session opens here)

```bash
# 1. Confirm v1.0 ship state.
cd /Users/keremdelikoyun/Projects/scientific-os
git log --oneline -3
# Expected: d5a4eb2 (Phase 9 hotfix) on top.

# 2. Tag + push if not done. Per user memory: organon remote, not origin.
git tag v1.0
git push organon v1.0
git push organon main

# 3. Confirm gates green.
cd projects/briefs/organon-dashboard
npm test                          # 108/108
npm run typecheck && npm run build
lsof -i :8769                     # if empty: npm run dev
python3 tests/stress-suite.py     # 52/52

# 4. Read the v2 dogfood report for context on what Phase 10 closes.
$EDITOR ../dogfood-glp1-weight-regain/DOGFOOD_REPORT_v2.md  # focus on Stage 5 §DR-3

# 5. Read the section that will change.
$EDITOR src/components/draft/section-list.tsx
$EDITOR src/components/draft/manuscript-workspace.tsx
$EDITOR src/components/draft/manuscript-create-form.tsx     # for DR-5
$EDITOR src/app/api/draft/                                  # confirm route patterns

# 6. Confirm sci-writing skill location + understand current shape.
ls /Users/keremdelikoyun/Projects/scientific-os/.claude/skills/sci-writing/
$EDITOR /Users/keremdelikoyun/Projects/scientific-os/.claude/skills/sci-writing/SKILL.md
```

Then dive into Phase 10 §5.

---

## 17. Closing note

Phase 9 wrapped the "make v1.0 trustworthy" arc. Phases 10–16 are the "make v1.0 useful" arc. Different shape — feature work, not bug fixing. Write tests as contracts, not as smoke. Each commit ships one self-contained slice. If you find a 🔴 mid-phase, treat it like Phase 9 did DR-1: log it in a fresh `DOGFOOD_REPORT_v3.md` and decide whether to ship-and-fix or pause-and-fix in-session.

Default cadence: 1 phase per session, atomic commit per sub-phase, push to `organon` after green gates. Don't batch.
