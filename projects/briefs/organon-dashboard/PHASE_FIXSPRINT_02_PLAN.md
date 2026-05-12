---
phase: fixsprint-02
title: Path canonicalization + assertWithinProject invariant + dogfood split migration
date: 2026-05-06
fixplan_phase: 1 (T1.1, T1.2, T1.3, T1.4 — the rest of FIXPLAN.md Phase 1 after fix-sprint Phase 1 shipped the helper + dedup)
estimated_effort: 0.5 day (actual)
---

# Phase fixsprint-02 — PLAN

## Phase 0.5 audit (already done)

Read every prompt-template + persister site under `src/app/api/` and
`src/lib/`. Surface area to fix:

| Site | Verdict |
|---|---|
| `src/app/api/images/generate/route.ts:44-45` | **BROKEN** — slug-interpolated `projects/${project.slug}/figures/${figId}/v1.png` in prompt + JSON line. Confirmed root cause for dogfood Finding #22. |
| `src/app/api/images/edit/route.ts` | clean — uses `path.relative(root, pngPath(...))` already. |
| `src/app/api/images/lock/route.ts` | clean — embeds `existing.png_path` (already-stored relative). |
| `src/app/api/draft/[slug]/action/route.ts` | clean — embeds `\fig{}` / `\cite{}` tokens, not paths. |
| `src/app/api/hypothesis/route.ts` | clean — uses `path.relative(organonRoot(), path.join(project.path, ...))`. |
| 7 persisters (savePaper, savePreview, saveFigure, saveSection, saveResult, saveCritique, saveHypothesis) | clean today, but no invariant guards them. Future regressions undetectable. |
| `appendVersion` (figures), `createManuscript` (manuscripts) | also write to disk; same gap. |

So Phase 2 fixes one bad site, adds the invariant at every persister to
catch the next one, and runs the merge migration on the dogfood split that
Phase 1 dedup made non-blocking but did not actually clean up.

## Goal (one sentence)

Every write target across the dashboard is asserted to live under
`project.path`, no source file embeds a `projects/${slug}/...` path string,
and the dogfood project's split tree is collapsed into the brief tree.

## Non-goals (explicit)

- **Do NOT change persister signatures.** They take `projectPath: string`,
  not `Project`. Adding the invariant the FIXPLAN's way would refactor every
  caller; the runtime contract is identical with `assertWithinProject(target,
  projectPath)`.
- **Do NOT touch async run-state surfacing.** That's Phase 3 (the biggest
  UX win). Phase 2 is path correctness only.
- **Do NOT change persistence shape, schemas, or cite-key logic.** That's
  Phase 3+ in the new sprint numbering (≈ FIXPLAN's Phase 2).
- **Do NOT migrate any other split tree.** The dogfood is the only one
  Phase 0.5 surfaced, and the migration script handles future splits with
  the same logic.

## Tasks

### T2.A — Fix slug-interpolated paths in `images/generate/route.ts`

File: `src/app/api/images/generate/route.ts`

Compute the figure-dir + PNG paths from `project.path` via
`figureDir(project.path, figId)` and `pngPath(project.path, figId, 1)`,
then `path.relative(organonRoot(), ...)` to get the prompt-friendly relative
path. Replace the four `projects/${project.slug}/...` literals in the
prompt body and the embedded JSON line with these computed strings.

Imports added: `node:path`, `organonRoot`, `figureDir`, `pngPath`.

**Acceptance**: `grep -E '\$\{(project\.slug|slug)\}' src/app/api src/lib`
returns ZERO hits. (The remaining `projects/...` mentions in source are
JSDoc comments.)

### T2.B — `assertWithinProject(target, projectPath)` in `src/lib/projects.ts`

```ts
export function assertWithinProject(target: string, projectPath: string): void {
  const t = path.resolve(target);
  const p = path.resolve(projectPath);
  if (t === p) return;
  if (!t.startsWith(p + path.sep)) {
    throw new Error(`Path-construction bug: ${t} is not within project ${p}. ...`);
  }
}
```

Diverges from FIXPLAN's `assertProjectPath(p, project)` signature in two
ways: (1) takes a string `projectPath` so persisters don't need refactor,
(2) uses `p + path.sep` to avoid `/a-foo` matching `/a`.

### T2.C — Wire the invariant into 7 persisters + 3 secondary write sites

| Persister | File | Callsites |
|---|---|---|
| `savePaper` | `src/lib/lit/library.ts` | 1 |
| `savePreview` | `src/lib/data/files.ts` | 1 |
| `saveFigure` | `src/lib/figures/store.ts` | 1 |
| `saveResult` | `src/lib/results/store.ts` | 1 |
| `saveCritique` | `src/lib/hypothesis/critiques.ts` | 1 |
| `saveHypothesis` | `src/lib/hypothesis/store.ts` | 1 |
| `saveSection` + `createManuscript` | `src/lib/draft/store.ts` | 3 (meta + section md + sidecar) |
| `appendVersion` | `src/lib/images/versions.ts` | 1 |

Each callsite is one line, placed immediately before the atomic
tmp-write. No-op cost in the hot path (one `path.resolve` + one prefix
check).

### T2.D — `scripts/migrate-split-projects.mjs`

Pure Node 20 stdlib, ESM. Two flags: `--dry-run` (default) and `--apply`.

For each slug present at both `projects/<slug>/` and
`projects/briefs/<slug>/`, walks every file in the non-brief tree and
classifies:

| Action | When |
|---|---|
| `MOVE` | file in src only |
| `DUPLICATE_REMOVE` | both exist, sha-256 identical |
| `OVERWRITE_NEWER_SRC` | both exist, src mtime newer (Δ ≥ 60 s) |
| `DST_NEWER_REMOVE_SRC` | both exist, dst mtime newer (Δ ≥ 60 s) |
| `TIE_SKIP` | mtime difference < 60 s and bytes differ |
| `ERROR` | unreadable / FS denied |

Runs in O(n) of files; deterministic; idempotent (re-runs after a
successful apply produce no plan).

### T2.E — Run migration on dogfood + verify

Dry-run output: 31 files, 31 safe, 0 blocked.
- 1 `DUPLICATE_REMOVE` (`data-20260506-a96e4d.csv` byte-identical)
- 1 `OVERWRITE_NEWER_SRC` (preview json, src ~3 h newer)
- 29 `MOVE` (figures, manuscripts, results, run logs)

Apply: `applied: 31, blocked: 0, src-remaining: false`.
Idempotent re-run: "No duplicate slugs found. Nothing to do."

### T2.F — Regression test `tests/route-project-paths.test.mjs`

5 tests:

1. `assertWithinProject` exported with the right signature + uses
   `path.resolve` + `startsWith(p + path.sep)` + `throw`.
2. Every persister imports + calls the invariant the documented number
   of times.
3. Static lint scan: zero `projects/${...}` template-literal patterns
   under `src/app/api/` or `src/lib/`. Comments stripped before scanning.
4. `scripts/migrate-split-projects.mjs` exists with both `--dry-run`
   and `--apply` flags; apply must be opt-in.
5. Live FS state: dogfood brief tree exists, non-brief sibling does not,
   merged children are present.

## Verification checklist

- [x] `grep -rE '\$\{(project\.slug|slug)\}' src/app/api src/lib` → 0 hits.
- [x] `npm test` clean: 25/25 (16 prior + 4 P1 + 5 P2).
- [x] `npm run typecheck` clean.
- [x] `npm run build` clean.
- [x] `node scripts/migrate-split-projects.mjs --dry-run` reports the
      dogfood split correctly.
- [x] `node scripts/migrate-split-projects.mjs --apply` merges and removes
      the duplicate.
- [x] After migration, `ls projects/dogfood-glp1-weight-regain/` returns
      "no such file" and the brief tree contains figures + manuscripts +
      results + papers + hypotheses + data.

## Commit message

```
dashboard: Phase 2 (fix-sprint) — path canonicalization + invariant + dogfood migration

Closes the rest of FIXPLAN Phase 1 (T1.1, T1.2, T1.3, T1.4) — the helper
and dedup landed in commit 3f76409 (fix-sprint Phase 1).

- Fixed src/app/api/images/generate/route.ts:44-45: replaced four
  `projects/${project.slug}/...` template-literal paths with values
  computed via figureDir(project.path, ...) + pngPath(...). This was
  the root cause for the dogfood Finding #22 split-projects bug.
- New assertWithinProject(target, projectPath) invariant in
  src/lib/projects.ts. Wired into 7 persisters + appendVersion +
  createManuscript: any future write-site that constructs a path via
  slug interpolation throws at runtime instead of writing to the wrong
  tree silently.
- New scripts/migrate-split-projects.mjs (Node 20 stdlib, no deps).
  --dry-run is the default; --apply opt-in. Walks every file in the
  non-brief tree and classifies MOVE / DUPLICATE_REMOVE /
  OVERWRITE_NEWER_SRC / DST_NEWER_REMOVE_SRC / TIE_SKIP / ERROR by
  sha-256 + mtime comparison. Idempotent (re-running after apply finds
  nothing).
- Ran the migration on dogfood-glp1-weight-regain: 31 actions applied
  (1 byte-identical removal, 1 newer-src overwrite, 29 moves). Source
  tree gone; brief tree now holds the merged figures, manuscripts,
  results, run logs, plus its prior papers + hypotheses.
- New tests/route-project-paths.test.mjs (5 tests): asserts the
  invariant signature, every persister wiring, zero slug-interp paths
  in source, migration script flags, and live FS post-state.

Verification:
- npm test: 25/25 PASS
- npm run typecheck: clean
- npm run build: clean

Out of scope (Phase 3 ≈ FIXPLAN Phase 2): persistence-layer
correctness — cite_key first-class, all-sources persistence (not just
PubMed), pmid-pmid double-prefix, HTML-entity decode in journal/abstract.
```
