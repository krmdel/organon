<!-- no-cite reason="Internal engineering plan; cite-marker patterns appear only in code-fence examples illustrating the dashboard's draft renderer behavior, not as real bibliographic citations." -->
---
project: organon-dashboard
plan: v1.0 ship-gate fix sprint
date: 2026-05-06
revision: r2 (critic-applied 2026-05-06)
inputs: DOGFOOD_REPORT.md (26 findings) + code-level audit + FIXPLAN_CRITIQUE.md
target: re-run the GLP-1 dogfood end-to-end with zero workarounds
estimate: 5–5.5 working days, 10 commits, one ship gate
---

# Organon Dashboard v1.0 — Fix-Sprint Plan

## Revision 2 — applied critic findings (read FIRST, supersedes specific tasks below)

The original plan (everything below the `---` after this section) misdiagnosed
root causes in three of the most-cited findings. The critic's full report is
at `FIXPLAN_CRITIQUE.md` (5 critical, 13 major, 9 minor). The critical
findings change the **ordering, scope, and effort estimate** of the plan.
Read this section first, then the original plan as historical context.

### What changed

**1. New Phase 0.5 — "Diagnose before fix" (half day, gates Phases 1+).**
Three findings have speculative root causes. Before writing any fix code,
add temporary instrumentation, reproduce, and confirm. Specifically:

- **For #14 silent SIGTERM (Phase 4 / old Phase 3):** add `console.error` at
  `src/app/api/execute/route.ts:39` capturing `signal.aborted`, `signal.reason`,
  and a stack trace on `request.signal.abort`. Re-run the dogfood council
  scenario. If the abort fires from `request.signal` (browser disconnect / tab
  inactivity / Chrome MCP teardown) — which is the critic's hypothesis — the
  fix is **decouple the runner from `request.signal`** (fire-and-forget +
  tail-able SSE), not "add a runner-side timeout."
- **For #5 OpenAlex persistence (Phase 3 / old Phase 2):** the original
  diagnosis ("client-side POST is not happening for non-PubMed") is verifiably
  WRONG — `src/components/lit/lit-workspace.tsx:223-239` POSTs unconditionally.
  Instrument `handleSave` to log every POST request body + every response body.
  Re-run a save on a fresh OpenAlex paper. **Capture the actual failure mode
  before writing the fix.** Surface non-2xx responses in the UI (red banner +
  revert SAVED badge) — currently the catch swallows.
- **For #22 split-roots (Phase 2 / old Phase 1):** verify that
  `resolveProject("dogfood-glp1-weight-regain")` returns the brief or the
  non-brief on a fresh repo. The actual root cause is in
  `src/lib/projects.ts:31-94` — `listProjects()` registers TWO `Project`
  entries with the same slug if both `projects/{slug}/` and
  `projects/briefs/{slug}/` exist, and `resolveProject().find()` returns
  the FIRST match (non-brief, because non-briefs are appended first). Slug
  interpolation in `images/generate` is a real but separate bug.

Phase 0.5 is half a day. Each instrumentation task ends with a one-line
finding logged to `FIXPLAN_DIAGNOSIS.md` that confirms or refutes the
hypothesis.

**2. Phase reordering. The new order is:**

| New phase | Old phase | Scope |
|---|---|---|
| 0 | 0 | Pre-flight decisions D1–D5 |
| 0.5 | (new) | Diagnose-before-fix instrumentation |
| **1** | **7** | Project resolution helper + `__root__` becomes opt-in WITH backwards-compat (warnings, not 400, until Phase 9) |
| **2** | **1** | Path canonicalization + `resolveProject` dedup (T1.0 NEW) + migration |
| **3** | **2** | Persistence correctness + manuscript cite-key migration (T2.4b NEW) |
| **4** | **3** | Run-state surfacing — but the fix is "decouple from request.signal" not "add timeout" |
| **5** | **4** | Citation pipeline — but 422 is opt-in (`?strict=true`), default is 200-with-warnings (M4 fix) |
| **6** | **5** | Direct-Python stat tests + T5.0 vocabulary reconciliation (NEW) |
| **7** | **6** | Renderer + UX polish — biomedical heuristic via "for briefs, always rerank arXiv to bottom" (drop keyword list) |
| 8 | 8 | Regression suite (re-estimated 1.5 days) |
| 9 | 9 | Re-run dogfood ship gate |

**Why Phase 7 → Phase 1**: critic C4. The original plan made `__root__` an
explicit opt-in (returns 400 when project missing). That breaks
`tests/stress-suite.py` and every external caller on day 1. The new shape:
Phase 1 keeps `__root__` working (silent fall-through with a server-log
warning) AND adds `resolveProjectFromRequest` priority (query → form →
referer). The `400-when-missing` strict mode lands in Phase 9 only after
the migration + dogfood are clean.

**Why Phase 1 → Phase 2 with new T1.0**: critic C1. Migrating the split is
necessary but not sufficient. Without `listProjects()` dedup, any future
stray `projects/{slug}/` directory flips `resolveProject` permanently to
the wrong root. New T1.0: dedup-by-slug in `listProjects` (brief wins),
plus a server-startup check that refuses to boot if duplicate slugs are
detected without a `--ignore-split` flag.

**Why Phase 2 → Phase 3 with new T2.4b**: critic C3. The dogfood
manuscript types cite-marker tokens like `Sara2025` (the buggy first-name
form). After Phase 3's cite_key backfill writes `Berg2025` to the paper
JSON, the manuscript still doesn't resolve — `Sara2025` is neither cite_key
nor paper.id. New T2.4b: scan manuscripts for unresolved cite-marker tokens
post-backfill, write a per-manuscript `.cite-migration-pending.md` listing
each unresolved token with a fuzzy-match suggestion. Optional interactive
remap CLI.

**3. Effort re-estimates.**

| Phase | Old estimate | New estimate | Reason |
|---|---|---|---|
| 0.5 | (new) | 0.5 day | Diagnose three speculative root causes |
| 4 (was 3) | 1 day | 1.5 days | 12+ files across server/client/test infra; split into 4a (server) + 4b (client) |
| 5 (was 4) | (in 1) | 0.5 day | Render lookup + export resolver + manuscript-meta `cite_alias` field |
| 6 (was 5) | 0.5 day | 1 day | T5.0 vocab reconciliation + 8 new test impls (not "factor existing skill") |
| 8 | 0.5 day | 1.5 days | 13 unit test specs + 5+ stress cases + 25-step smoke walk doc |
| **Total** | **4 days** | **5.5 days** | |

**4. Specific in-task changes (Major findings applied).**

- **T1.3 migration tiebreaker (M1):** prefer **hash-equal → keep brief side**;
  fall back to mtime only when hashes differ. Print user-facing diff for
  hash-different children. Mtime alone is wrong: dogfood case has identical
  hashes but the **non-brief** copy has the newer mtime, so "prefer newer"
  picks the wrong winner.
- **T1.2 `assertProjectPath` (M2):** two-tier — `throw` only when the
  in-memory persist call constructs an out-of-bounds path (build bug);
  `warnOnce` when listing finds an out-of-bounds artifact (data on disk).
  Avoids bricking the dashboard on a single legacy stray.
- **T2.3 cite_key generation (M3):** make collision suffixes deterministic
  by sorting colliding papers lexicographically by paper.id (not by
  insertion order). On delete, write a tombstone to
  `.cite-key-tombstones.json` per project — never reuse a key that was
  ever assigned.
- **T3.1 / Decision D3 timeouts (M5):** per-route timeouts, not a blanket
  default. Stat: 30s; figure-gen: 180s; figure-edit: 300s; council POST:
  600s; draft action: 300s. Document the SLO in each route module.
- **T3.5 /runs Rerun (M9):** rerun allocates fresh `run_id` /
  `fig_id` / `hypothesis_id`. Old run stays in /runs history with a
  `superseded_by` link.
- **T2.5 HTML-entity decode (M8):** add numeric entity fallback
  (`&#NNN;` and `&#xHH;` via `String.fromCodePoint`). Inline 50+ common
  entity table covering PubMed efetch's typical output.
- **T4.3 export 422 (M4):** flip default — 200-with-warnings (existing
  behavior modulo the renderer fix). 422 is `?strict=true` opt-in for
  CI / publish flows. UX surface: red badge on the export status indicator
  when warnings are present.
- **T6.6 biomedical heuristic (M6):** drop the keyword list. For brief
  projects, always rerank arXiv to the bottom unless the user explicitly
  toggles arXiv. Non-brief projects keep current ordering.
- **T7.1 `resolveProjectFromRequest` (M7-related):** the critic's actual
  diagnosis of #5 — instrument BEFORE fixing — is now the Phase 0.5 task.
  The Phase 1 `resolveProjectFromRequest` helper still ships as planned.

**5. Stress-suite (M12).** New target is **57+/57+** (52 existing + 5 new
enumerated cases): missing project → 400, unresolved cite → 422,
non-zero subprocess exit → SSE failure, scatter Y default differs from X,
sub-style required validation. The `60+` claim was unsupported.

### What did NOT change

- The 5 pre-flight decisions D1–D5 stand. The critic agreed with the
  shape; the disagreements were about specific implementation tactics
  inside each decision.
- Phase 9 (re-run dogfood) shape stays. The acceptance criteria remain
  identical; only the path to reach them changes.
- The "lock the contract" working principle (regression test + invariant
  + smoke walk per fix) stays.
- Constraint reminders (no `npm install`, no `pip install`, GSD workflow,
  Claude-only co-authorship) stay.

### How to read the rest of this document

The 9-phase plan below is the **original v1**. Where the revision changes a
specific task or commit message, the new shape is in this Revision 2
section. When in doubt, Revision 2 wins.

The original plan stays in this document for two reasons: (1) traceability
of the critic-driven changes, (2) the Major + Minor findings the critic
raised against specific tasks need the original task text to reference.

Begin original plan ↓

---

> Fix-sprint scope. The surface (Phases 1–6) ships; this plan does not add
> features. Every change is either a bug fix, an observability hook, or a
> regression test that locks the bug out. The ship gate at the end is a
> repeatable end-to-end dogfood against the same `dogfood-glp1-weight-regain`
> brief project — same research question, zero workarounds.

## Constraint reminders (from CLAUDE.md)

- `npm install` is denied. **No new npm dependencies.** All test infrastructure
  must use Node's built-in `node:test` + `node:assert/strict` (the existing
  `npm test` runner already uses them).
- `pip install` and `brew install` are denied. Stay on the existing `.venv`
  Python and existing system binaries (matplotlib, pandas, scipy already
  there).
- Use the GSD workflow for substantial work: `/gsd:plan-phase` before code,
  `/gsd:execute-phase` for the implementation, atomic commits per phase.
- Co-author commits as Claude, not WOZCODE.
- One project = one canonical root (after Phase 1).

## Working principle: "lock the contract"

Every fix in this plan ships with one or more of:

- A **regression test** that fails before the fix and passes after.
- An **invariant assertion** in the code that throws if the bug recurs.
- A **smoke-walk** entry in `tests/phase{N}-smoke-walk.md` covering the path.

A bug is not "fixed" until a future regression cannot reintroduce it
silently.

---

# Phase 0 — Pre-flight decisions

These resolve before any code changes. **Lock these answers in the next
session before opening Phase 1.**

## Decision D1 — single-canonical-root choice

The bug: lit/data/hypothesis write to `projects/briefs/{slug}/`, draft +
figures + results write to `projects/{slug}/`. Two branches must collapse to
one.

| Option | Pro | Con |
|---|---|---|
| **A. Brief projects keep `projects/briefs/`; non-brief stay at `projects/`** (status quo, but enforce single-root per project) | Matches CLAUDE.md output convention (Level 2 = `projects/briefs/{name}/`) | Requires `Project.path` consistency audit across every persister and every prompt template. |
| B. All projects flatten to `projects/{slug}/`; briefs live there too with a `brief.md` marker file | Simpler resolution, single tree | Breaks existing `projects/briefs/*/` dirs — migration churn for org/dashboard, citation-pipeline-hardening, cross-project-memory, organon-whitepaper. |
| C. All projects nest under `projects/{slug}/`; symlink `projects/briefs/{slug}` → `projects/{slug}` for compat | Bridges old + new | Symlinks add fragility on Windows (rare, but).

**Recommendation: A** — the pain is "audit every path-construction site to use
`Project.path`, never `slug`." Option B churns five real briefs. Option C
introduces symlink complexity.

**Migration strategy for A**: a one-time migrator at
`scripts/migrate-split-projects.mjs` that walks `projects/{slug}/` and, when it
finds a sibling `projects/briefs/{slug}/`, merges children into the brief
side and deletes the duplicate. Idempotent, dry-run by default.

## Decision D2 — observability primitive

The bug: long-running subprocess SIGTERM at ~3:35 with no UI feedback (Finding #14).

Fix shape: every long-running run (council, stat, figure-gen, draft action)
exposes three states to the UI: `running` / `succeeded` / `failed (reason)`.
Currently only the SSE close event distinguishes them, and the client treats
non-zero exit the same as success.

**The mechanism:** the client SSE consumer reads the final `exit` event, sets
state based on `code === 0` vs non-zero, and shows a `Retry` button + cached
prompt on failure. Implementation in Phase 3.

## Decision D3 — `claude-runner` timeout

The runner has no timeout; it waits forever. The 3:35 SIGTERM came from
elsewhere (likely Next 16 server route default or AbortSignal somewhere
upstream).

**Decision: configurable per-call timeout, default 8 minutes** for
council/stat/figure (each is bounded by the skill's own internal step count),
with `--no-timeout` opt-out for users who explicitly extend. The runner emits
a `timeout` event distinct from `exit` so the UI can distinguish a clean
non-zero exit from a hard kill. A keepalive heartbeat every 15s on the SSE
channel prevents proxy idle-timeouts.

## Decision D4 — cite-key as a first-class field

Currently cite_key is computed at BibTeX-export time only and is broken
(first-name based — Finding #7). Fix shape: store `cite_key` on the persisted
PaperArtifact, derived correctly from surname + year + collision suffix.
Render + export + BibTeX all read this single field.

**Decision:** cite_key generation is a single function `paperToCiteKey(paper,
existingKeys)` in `lib/lit/cite-key.ts`, called at exactly **one** place — the
paper persister `savePaper` — so every downstream consumer sees the same
value. BibTeX export simply reads `paper.cite_key`.

## Decision D5 — stat tests: direct-python or via-skill

A Pearson correlation does not need an LLM. Plot generation already runs
direct Python (`scripts/generate_plot.py` via `lib/data/plot.ts`) and
returns in ~5s.

**Decision:** factor a `runStatTestDirect()` function that spawns
`scripts/run_stat_test.py` (new) the same shape as `generate_plot`. The
`/api/data/analyze` route runs this first; if it succeeds, the result lands
immediately. The narrative interpretation can stay as an *optional*
follow-up via the skill (a separate "Interpret" button on the result card),
not a blocking step.

This makes the stat path **deterministic and reliable** — the LLM is
removed from the critical numeric path.

---

# Phase 1 — Project root canonicalization

**Scope:** every code path that constructs a project artifact path must
resolve through `Project.path` from `resolveProject()`. No string
interpolation of `projects/{slug}/...` anywhere.

**Why first:** every other fix downstream assumes one true project tree.
Doing this last leaves us patching duplicates.

## Tasks

### T1.1 — Audit and fix path construction sites

| File | Bug | Fix |
|---|---|---|
| `src/app/api/images/generate/route.ts:45-46` | Prompt template hardcodes `projects/{slug}/figures/...` | Use `path.relative(organonRoot(), figureDir(project.path, figId))` and embed that string in the prompt instead. |
| `src/app/api/images/generate/route.ts:46` (artifact JSON line) | `png_path` interpolated from slug | Same — relative-from-root path computed from `project.path`. |
| `src/app/api/images/lock/route.ts` (likely same shape) | Audit + same fix | — |
| `src/app/api/images/edit/route.ts` (likely same shape) | Audit + same fix | — |
| `src/app/api/draft/[slug]/action/route.ts` (action prompt — likely contains slug-interpolated paths for section references) | Audit + same fix | — |
| `src/app/api/hypothesis/route.ts` (council prompt — does it carry paper IDs? Yes; see #10) | Verify the prompt does not embed slug-interpolated paths to papers | If found, switch to `path.relative(organonRoot(), libraryDir(project.path))`. |

**Audit command:** `grep -rn "projects/.{project.slug.}\|projects/.\{slug.}" src/`
should return zero hits in `app/api/` and `lib/` after this phase. The few
in `scripts/*.py` argparse help-text are documentation strings and are fine.

### T1.2 — Add an invariant: `assertNoSlugPathConstruction()`

A small lint-like helper at `src/lib/projects.ts`:

```ts
export function assertProjectPath(p: string, project: Project): void {
  if (!p.startsWith(project.path)) {
    throw new Error(
      `Path-construction bug: ${p} does not start with project.path ${project.path}. ` +
      `Use figureDir(project.path, ...) etc., not interpolation of slug.`,
    );
  }
}
```

Called inside `savePaper`, `savePreview`, `saveFigure`, `saveSection`,
`saveResult`, `saveCritique`, `saveHypothesis`. If the path was constructed
correctly via `project.path`, this is a no-op. If a future caller passes a
slug-interpolated path, the assertion fires immediately at write time.

### T1.3 — Migration script for the split

`scripts/migrate-split-projects.mjs`:

```
Usage:
  node scripts/migrate-split-projects.mjs --dry-run
  node scripts/migrate-split-projects.mjs --apply

For each slug S where both projects/S/ AND projects/briefs/S/ exist:
  - Read brief.md (S is a brief)
  - For every child dir in projects/S/ NOT present in projects/briefs/S/,
    move it into projects/briefs/S/.
  - For every child dir present in BOTH, prefer the newer mtime; print a
    warning for the user to manually resolve if mtimes are within 60s.
  - After merging, rm projects/S/ (only after confirmation in --apply mode).
```

Dry-run output for the dogfood project should report:

```
projects/dogfood-glp1-weight-regain/  ->  projects/briefs/dogfood-glp1-weight-regain/
  data/        - merge (newer in non-brief, brief copy is identical hash)
  figures/     - move
  manuscripts/ - move
  results/     - move
  .organon/    - move (run logs)
After: projects/dogfood-glp1-weight-regain/ deleted.
```

### T1.4 — Regression test

`tests/parser-phase1-paths.test.mjs`:

```js
// 1. For every brief in fixtures, call resolveProject(slug) and assert
//    project.path includes "projects/briefs/".
// 2. For every persister (savePaper, saveSection, ...), call with a brief
//    project and assert the returned library_path starts with
//    "projects/briefs/{slug}/".
// 3. For the images-generate prompt builder (extract into a pure fn first),
//    assert the produced prompt contains the brief's full relative path,
//    NOT slug-interpolated.
```

### Verification

- [ ] `grep -rn "projects/.{slug.}" src/` returns zero hits.
- [ ] `node scripts/migrate-split-projects.mjs --dry-run` reports the dogfood split.
- [ ] `node scripts/migrate-split-projects.mjs --apply` merges and removes the duplicate.
- [ ] After migration, `ls projects/dogfood-glp1-weight-regain/` returns
  "no such file" and `ls projects/briefs/dogfood-glp1-weight-regain/` shows
  papers + data + figures + manuscripts + results + hypotheses.
- [ ] `npm run typecheck && npm run build && npm test` clean.

**Commit:** `dashboard: Phase 1 path canonicalization — single project root, migration tooling, invariant assertions`

---

# Phase 2 — Persistence-layer correctness

**Scope:** the persist layer is broken in three concrete ways that the dogfood
surfaced. All three are simple. None require API changes.

## Tasks

### T2.1 — Persist all sources, not just PubMed (Finding #5)

The OpenAlex / S2 papers showed in the library UI but never wrote to
`papers/`. Root cause: probably the `/api/lit/library` POST receives a
`PaperArtifact` for OpenAlex sources but the parser or persister rejects
something.

**Investigation step (first 30 min):**

```bash
grep -rn "openalex\|semanticscholar" src/lib/lit src/lib/artifacts --include="*.ts"
```

then run the dogfood `/lit` search again with a network capture
(`mcp__claude-in-chrome__read_network_requests` after T2.1 begins) — capture
the POST /api/lit/library request body for an OpenAlex paper, see why
`savePaper` rejects it.

**Likely root cause:** the OpenAlex artifact has no `source_ids.pmid` and
the persister's filename derivation works fine, but the client-side POST is
not happening for non-PubMed entries. Check `components/lit/save-button.tsx`
(or equivalent) — it may filter on source.

**Fix shape:** the POST should fire for any `_artifact: paper` regardless of
source. The library UI's optimistic-update should also reconcile with the
server response so a failed POST doesn't show a phantom SAVED state.

### T2.2 — Fix the `pmid-pmid:` double-prefix (Finding #4)

Two paths to the same place. Pick one.

**Option A (preferred):** stop encoding `pmid:` into the source_ids value at
parse time. The parser stores `source_ids.pmid = "41889156"` (no prefix). The
artifact id is then `pmid-${source_ids.pmid}` -> `pmid-41889156`. Filename
is `pmid-41889156.json`. Tracked in `lib/artifacts/parser.ts`.

**Option B:** strip the redundant prefix in the persister (`savePaper` does
`paper.id.replace(/^pmid-pmid:/, "pmid-")`). Quick but leaves the
inconsistency in the in-memory artifact.

**Decision: A.** Touch the parser, not the persister. Fix the inconsistency
at its source.

### T2.3 — Generate `cite_key` at persist time (Finding #25 root cause)

New file `src/lib/lit/cite-key.ts`:

```ts
import type { PaperArtifact } from "../artifacts/types";

/** Extract surname from "Last, First" or "First Last" forms. */
export function firstAuthorSurname(paper: PaperArtifact): string {
  const a = paper.authors[0]?.trim();
  if (!a) return "Anonymous";
  if (a.includes(",")) return a.split(",")[0].trim();
  const words = a.split(/\s+/);
  return words[words.length - 1];
}

/**
 * Generate a stable cite-key from surname + year. Disambiguation suffix
 * (a/b/c) is the caller's responsibility — pass `existingKeys` to get a
 * unique key.
 */
export function paperToCiteKey(
  paper: PaperArtifact,
  existingKeys: ReadonlySet<string>,
): string {
  const surname = firstAuthorSurname(paper).replace(/[^A-Za-z0-9]/g, "");
  const year = paper.year && paper.year > 0 ? String(paper.year) : "n.d.";
  const base = `${surname || "Unknown"}${year}`;
  if (!existingKeys.has(base)) return base;
  for (let i = 1; i < 26; i += 1) {
    const candidate = `${base}${String.fromCharCode(96 + i + 1)}`; // b, c, d ...
    if (!existingKeys.has(candidate)) return candidate;
  }
  return `${base}-${paper.id}`;
}
```

Wire-up:

- `lib/lit/library.ts:savePaper` reads existing cite-keys from the library
  before writing, computes a unique cite_key, and stores it on the artifact.
- `lib/lit/bibtex.ts:bibtexKey` -> reads `paper.cite_key` if present, falls
  back to the legacy first-token derivation only when missing (transitional —
  remove once all libraries are re-keyed).
- `lib/draft/render.ts:175` -> look up by cite_key not by id (Phase 4).
- `lib/draft/bib.ts:compileBibliography` -> same.

### T2.4 — One-time backfill script

`scripts/backfill-cite-keys.mjs`:

```
For every paper JSON under projects/ ** /papers/ *.json:
  - If cite_key field is missing or null,
    - read all sibling JSONs in the same papers/ dir to build existingKeys,
    - compute the new cite_key,
    - rewrite the JSON in place.
  - Idempotent: rerunning produces no change.

After backfill, for the dogfood project:
  pmid-41889156.json   -> cite_key: "Shah2026"
  pmid-41909366.json   -> cite_key: "Hubert2026"
  pmid-41931049.json   -> cite_key: "Rosen2026"
  pmid-41978101.json   -> cite_key: "Mack2026"
  pmid-42055215.json   -> cite_key: "Hubert2026b" (collision — see T2.3)
  ...
```

Run dry-run first, confirm the new keys, then `--apply`.

### T2.5 — Decode HTML entities in journal/abstract fields (Finding #3)

In `lib/artifacts/parser.ts` (paper case): apply `decodeHtmlEntities()` to
`journal` and `abstract` before persisting. Strip safe inline tags before
save (preserve as plain text).

Tiny helper `lib/lit/html-decode.ts`:

```ts
const ENTITIES: Record<string, string> = {
  "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'",
  "&nbsp;": " ",
};
export function decodeEntities(s: string): string {
  return s.replace(/&[a-z#0-9]+;/g, (m) => ENTITIES[m] ?? m);
}
export function stripSafeTags(s: string): string {
  return s.replace(/<\/?(b|i|sub|sup|em|strong)[^>]*>/g, "");
}
```

(Keep zero-dependency. We're not bringing in `he`.)

### T2.6 — Regression tests

`tests/parser-phase2-persistence.test.mjs`:

```js
// 1. Persist a PubMed paper, an arXiv paper, an OpenAlex paper, an S2 paper.
//    Assert four files exist on disk.
// 2. Persist a paper whose source_ids.pmid is "41889156". Assert filename
//    is "pmid-41889156.json" (not double-prefixed).
// 3. Persist three papers with same surname+year. Assert cite_keys
//    {Smith2026, Smith2026b, Smith2026c}.
// 4. Persist a paper with journal "Diabetes &amp; metabolism". Assert
//    saved JSON has journal "Diabetes & metabolism".
```

### Verification

- [ ] `find projects/briefs/dogfood-glp1-weight-regain/papers -name 'pmid-pmid:*'` returns nothing.
- [ ] After re-running `/lit` search + save, all 9 papers persist (not just 6).
- [ ] Every persisted JSON has a `cite_key` field.
- [ ] `npm test` clean.

**Commit:** `dashboard: Phase 2 persistence — all sources persist, cite-keys at save time, no double-prefix, HTML entities decoded`

---

# Phase 3 — Async run-state surfacing (the biggest UX bug)

**Scope:** every long-running subprocess call surfaces three states
(`running` / `succeeded` / `failed`) plus a Cancel + Retry affordance. SSE
keepalive prevents proxy timeouts. The runner gets a configurable timeout.

This is the **single biggest researcher-experience improvement** in the
sprint.

## Tasks

### T3.1 — Runner emits `timeout` and surfaces non-zero exit

`src/lib/claude-runner.ts`:

```ts
export type RunnerOptions = {
  ...
  timeoutMs?: number; // default 480_000 (8 min)
  heartbeatMs?: number; // default 15_000
};

// New event types
export type RunnerEvent =
  | { type: "start"; ... }
  | { type: "stdout"; ... }
  | { type: "stderr"; ... }
  | { type: "heartbeat"; ts: string } // NEW
  | { type: "timeout"; ts: string; ms: number } // NEW
  | { type: "exit"; ts: string; code: number | null };
```

Implementation:

- After spawn, set a `setTimeout(timeoutMs, kill)` that calls
  `child.kill("SIGTERM")` (SIGKILL after 5s grace).
- Emit `timeout` event before `kill`.
- Set up a `setInterval(heartbeatMs)` that yields `heartbeat` events; clear
  on close.
- Treat `code === 0` as success; everything else (including null from
  signal-kill) as failure.

### T3.2 — SSE route forwards heartbeat + exit code

Routes that stream RunnerEvents through SSE (`/api/data/analyze`,
`/api/draft/[slug]/action`, `/api/images/generate`, `/api/images/lock`,
`/api/hypothesis` (POST), `/api/hypothesis/reconcile`):

- Forward `heartbeat` events as `event: heartbeat` SSE messages (clients
  ignore them but the connection stays alive).
- Forward `exit` events with full `{code, success: code === 0}` payload.
- Forward `timeout` events with `event: timeout`.

### T3.3 — Client SSE consumer surfaces failure state

`src/lib/sse/consume.ts` (or wherever the shared consumer lives — find via
`grep -rn "EventSource\|onmessage" src/lib src/components`):

- Handler for `exit` event: read `code`, set workspace's `runState` to
  `succeeded` or `failed`.
- Handler for `timeout`: set `runState` to `failed` with reason like
  `Timed out after Xm. The skill may need a longer cap or the LLM is stuck.`
- Handler for `error` (network failure): set `runState` to `failed` with
  reason `Connection lost — your run may have completed; refresh to check.`

### T3.4 — UI: failure card + Cancel + Retry

Components affected:

- `components/hypothesis/persona-card.tsx` (or equivalent) — when
  `runState=failed`, show error message + cached prompt + Retry button.
- `components/data/stat-result-card.tsx` — same.
- `components/figures/figures-workspace.tsx` — same; lift the existing
  `GENERATING…` indicator into a proper state machine.
- `components/draft/action-bar.tsx` — same.

Cancel: each component holds the `AbortController` it passed to its fetch;
Cancel calls `controller.abort()` which triggers the runner's `abortSignal`
which `child.kill("SIGTERM")` and propagates the exit downstream.

Retry: replays the last request body (already in component state) against
the same endpoint. No new API surface needed.

### T3.5 — `/runs` workspace surfaces failed runs prominently

When a run row's terminal `exit.code` is non-zero, render the row with red
left-border + a "rerun" button that re-emits the start event's prompt. This
makes "did my council finish?" answerable from one place.

`src/app/runs/page.tsx` and `src/components/runs/*` likely already parse run
JSONLs; just add the failed-state filter and rerun affordance.

### T3.6 — Server-side: 504 distinct from 500

`/api/data/analyze`, `/api/images/generate`, etc. when the runner's exit
event has `code !== 0` AND a prior `timeout` event was emitted, the route
emits the response stream's terminal status as `code: -1, kind: "timeout"`.

### T3.7 — Integration test for the failure path

`tests/runner-failure.test.mjs`:

```js
// 1. spawn a runner with a fake `claude` command (test harness binary that
//    sleeps 6s). Set timeoutMs=2000. Iterate the generator. Assert events
//    in order: start, stdout|stderr*, timeout, exit (code !== 0).
// 2. spawn a runner that exits with code 143 (SIGTERM). Iterate. Assert
//    final exit event has code === 143.
// 3. Spawn with abortSignal pre-aborted. Assert immediate exit.
```

The test harness binary: a small `tests/fixtures/fake-claude.mjs` that
takes argv and sleeps / exits as instructed. Zero deps.

### Verification

- [ ] In a manual test (terminal): kill the subprocess mid-run with `kill -TERM`. UI shows red Failed card with reason + Retry within 1s.
- [ ] In a manual test: trigger a council run, watch SSE in DevTools, see `event: heartbeat` every 15s.
- [ ] `tests/runner-failure.test.mjs` passes.
- [ ] `/runs` page renders a recent failed run with red border + Rerun button.

**Commit:** `dashboard: Phase 3 run-state surfacing — heartbeat, timeout, failure state, Cancel + Retry, /runs failure rendering`

---

# Phase 4 — Citation pipeline correctness

**Scope:** cite-marker tokens resolve end-to-end through preview AND export.
"Missing from library" disappears for any paper the user actually saved.

Depends on: Phase 2 (cite_key on disk).

## Tasks

### T4.1 — Renderer looks up by cite_key, not paper.id

`src/lib/draft/render.ts:175`:

```ts
// before
const paper = input.library.find((p) => p.id === id);

// after
const paper = input.library.find(
  (p) => p.cite_key === id || p.id === id, // accept both during transition
);
```

Same in `src/lib/draft/bib.ts:compileBibliography`:

```ts
const byKey = new Map<string, PaperArtifact>();
for (const p of library) {
  if (p.cite_key) byKey.set(p.cite_key, p);
  byKey.set(p.id, p); // legacy fallback
}
```

### T4.2 — Export uses the same renderer as preview (Finding #24)

`src/app/api/draft/[slug]/export/route.ts`: when exporting markdown, do not
ship raw cite-marker tokens. Instead, run the same `renderManuscript` that
the preview uses, then **convert HTML back to markdown** for the markdown
export.

But — `renderManuscript` returns HTML, not markdown. So the export flow
needs a markdown branch too.

**Fix shape:** factor the cite/fig resolution into a pre-render pass that
operates on markdown:

```ts
// src/lib/draft/resolve.ts (new)
export function resolveCitesAndFigs(
  md: string,
  library: PaperArtifact[],
  figures: FigureArtifact[],
  style: CitationStyle,
  citationOrder: string[],
  figureOrder: string[],
): { md: string; refs: string[] };
// returns markdown with cite tokens replaced by [3], fig tokens replaced
// by ![](path)
```

Both export and preview call this pre-pass. Preview then HTML-renders;
export ships markdown.

### T4.3 — Bibliography section in export: actual entries, not "Missing"

After resolveCitesAndFigs runs, the export route appends the formatted
bibliography (using `compileBibliography`) at the bottom of the markdown.
If a cite-key truly has no library entry, **fail the export with a 422 +
list of unresolved keys**, do not silently ship "Missing from library:" lines.

The user can then either:
- Add the missing paper to the library and re-export, or
- Edit the section to remove the citation, or
- Pass `?force=true` to ship the export anyway with the warning footer.

### T4.4 — Author/year cache uses surname extractor from `lib/draft/bib.ts`

Right now `render.ts:177` has its own surname extractor. Replace with
`firstAuthorSurname` from `bib.ts`. Single source of truth.

### T4.5 — Embed-autocomplete picker offers cite_key, not paper.id

`components/draft/embed-autocomplete.tsx`: the dropdown that fires on the
cite-marker prefix should suggest `Shah2026`, `Hubert2026`, etc. (the
cite_key field), sorted by recency. Not `pmid-41889156`.

### T4.6 — Regression tests

`tests/parser-phase4-citations.test.mjs`:

```js
// Fixture: library with 3 papers, cite_keys ["Smith2026", "Jones2026",
// "Lee2025"].
// 1. Render markdown using cite-marker for Smith2026 -> "[1]" + bibliography
//    entry for Smith.
// 2. Render same markdown when Smith has cite_key="Smith2026"
//    AND id="pmid-12345" -> resolves via cite_key.
// 3. Markdown using cite-marker for Phantom2099 -> export route returns 422 with
//    {unresolved: ["Phantom2099"]}.
// 4. Same with ?force=true -> export returns 200 with
//    "Missing from library: Phantom2099" footer.
// 5. Resolved markdown does not contain literal cite-marker syntax anywhere.
```

### Verification

- [ ] Re-export the dogfood manuscript: numbered citations inline; full
  bibliography at the bottom; zero "Missing from library" lines.
- [ ] Diff preview HTML vs export markdown: same set of citations
  resolved, same bibliography order.
- [ ] `npm test` clean.

**Commit:** `dashboard: Phase 4 citation pipeline — render+export resolve cites + figs via cite_key, single resolver path, 422 on unresolved`

---

# Phase 5 — Direct-Python stat tests

**Scope:** stat tests run as a 5s direct-Python subprocess (like plots),
not a 60s+ LLM call. The LLM is reserved for an *optional* narrative
follow-up.

## Tasks

### T5.1 — `scripts/run_stat_test.py`

Mirror of `scripts/generate_plot.py` shape. Takes `--data-path`, `--test`,
`--params-json`, `--out-path`. Runs scipy/statsmodels, emits one
`{"_artifact":"stat-result", ...}` JSON line on stdout.

Tests supported (matches stat-picker recommendations):

- Pearson, Spearman, Kendall correlation
- Independent t, Welch t, Mann-Whitney U
- One-way ANOVA, Kruskal-Wallis
- Chi-squared, Fisher exact
- Linear regression (OLS)
- Power analysis (statsmodels.stats.power)

Each emits the artifact with `assumption_checks[]` (Shapiro-Wilk for
normality on relevant tests; Levene for equal-variance; n-check; etc.) and
a one-paragraph plain-English `interpretation`.

### T5.2 — `lib/data/stat-test.ts`

TS-side wrapper, same shape as `lib/data/plot.ts`:

```ts
export async function runStatTest(opts: {
  dataPath: string;
  fileId: string;
  runId: string;
  test: StatTest;
  params: Record<string, unknown>;
  projectSlug: string;
  projectPath: string;
}): Promise<StatResultArtifact>;
```

Spawns the Python subprocess with cwd=organonRoot, 30s timeout, parses the
JSON line, persists via `saveResult`.

### T5.3 — `/api/data/analyze` route uses direct path

Simplify dramatically:

```ts
export async function POST(request: Request) {
  // ... existing project resolution + body parse ...
  try {
    const result = await runStatTest({...});
    return Response.json({ result }, { status: 201 });
  } catch (err) {
    // 504 on timeout, 500 otherwise
  }
}
```

No SSE. No subprocess LLM call. Just a 5s POST that returns the result. The
client's stat-result-card renders it immediately.

### T5.4 — Optional "Interpret" follow-up

When the result card is rendered, add a small button "AI interpretation"
that fires the OLD via-skill path (sci-data-analysis with the result
context). This is gated behind a click — the numeric path doesn't depend
on it.

The skill keeps its `Step 4 Validate` mode for CLI users; the dashboard
just doesn't auto-fire it.

### T5.5 — Regression tests

`tests/run-stat-test.test.mjs`:

```js
// Fixtures: a 60-row CSV with known r=-0.430 between cols A and B.
// 1. Run pearson on (A, B). Assert artifact.statistic ~ -0.43 +/- 0.01,
//    p < 0.001, n=60.
// 2. Run pearson on (A, A). Assert r=1.0 + warning about identical cols.
// 3. Run with bad params (missing column). Assert ProfileError-like 400.
// 4. Run with timeout=100ms (forced). Assert 504.
```

### Verification

- [ ] /data -> STATS tab -> Recommend -> RUN. Result card renders in <10s.
- [ ] No `.organon/runs/...stat-...jsonl` is created (only direct-Python now).
- [ ] Old via-skill path still works for CLI users — verify by running the
  skill directly from a terminal.
- [ ] `npm test` clean.

**Commit:** `dashboard: Phase 5 direct-Python stat tests — /api/data/analyze no longer routes through subprocess LLM; AI interpretation moved to opt-in button`

---

# Phase 6 — Renderer parity + minor UX

**Scope:** the small finish work. Most are XS effort.

## Tasks

### T6.1 — Hand-rolled markdown renderer strips raw HTML in section bodies (Finding #20)

`src/lib/draft/render.ts`: when rendering a section's markdown, strip raw
HTML tags (except for the cite/fig substitutions the renderer itself
inserts). The default placeholder text in `DEFAULT_SECTIONS`
(`store.ts:33`) should also be cleaned up to NOT contain raw HTML.

### T6.2 — Default placeholders use plain prose (Finding #20)

`src/lib/draft/store.ts:33-41`:

Drop the `<span>` markup. The cite/fig form in backticks renders as inline
code in the preview, which is the right hint.

### T6.3 — Scatter plot Y default differs from X default (Finding #15)

`components/data/plot-picker.tsx` (or wherever the form initializes): when
`X` is set to the first numeric column, default `Y` to the SECOND numeric
column (or the first non-X numeric column if X was changed).

### T6.4 — `/figures` workspace tolerates legacy single-version plots (Finding #18)

`components/figures/figures-workspace.tsx`: when a figure has no
`versions[]`, render a single-card view from `library_path` directly. Treat
the missing versions field as `[{version: 1, png_path: library_path,
locked: true}]`.

Eliminates the "fig_id has no versions" error banner for plots created in
`/data`.

### T6.5 — Sub-style validation in figure gen form (was Finding #19/#26)

`components/figures/style-picker.tsx`: when style ∈ {scientific, technical}
which require sub-styles, the GENERATE button is disabled until a sub-style
is chosen. A red asterisk on the sub-style label.

`/api/images/generate`: server-side, return 400 with a clear message if
sub-style is required but missing. Currently it might silently pass an
empty sub-style to the skill.

### T6.6 — Lit search: arXiv off by default for biomedical queries (Finding #1)

Heuristic: if query contains any of {drug names, disease names, "patient",
"trial", "efficacy", "treatment", ...}, default arXiv to off. A small
biomedical-keyword list at `lib/lit/query-class.ts`.

Or simpler: the project's brief.md `level` and `field` (when set) control
default sources. For brief projects without metadata, arXiv defaults off.

User can re-enable with one click. The current behavior of "all 4 sources
on" stays for non-brief projects.

### T6.7 — Lit search: ranking arXiv lower on biomedical queries

If arXiv is on AND query is biomedical, post-rank arXiv results below
PubMed/OpenAlex/S2 results. Single function in `lib/lit/search.ts`:

```ts
function rerankByDomain(results: PaperArtifact[], queryClass: QueryClass): PaperArtifact[] {
  if (queryClass === "biomedical") {
    return [...results].sort((a, b) => {
      const aIsBio = a.sources.includes("pubmed") || a.sources.includes("openalex");
      const bIsBio = b.sources.includes("pubmed") || b.sources.includes("openalex");
      if (aIsBio && !bIsBio) return -1;
      if (!aIsBio && bIsBio) return 1;
      return 0;
    });
  }
  return results;
}
```

### Verification

- [ ] Visual smoke walk: create a fresh manuscript, default placeholders
  read clean (no raw HTML).
- [ ] Scatter on dogfood data: Y defaults to a different column than X.
- [ ] `/figures` workspace on a project with a `/data`-generated plot:
  no error banner.
- [ ] Try GENERATE with style=scientific, no sub-style: button disabled.
- [ ] Search "GLP-1 weight regain": arXiv off in source filters; results
  are PubMed/OpenAlex dominated.

**Commit:** `dashboard: Phase 6 renderer + UX polish — placeholder cleanup, scatter Y default, /figures legacy-plot tolerance, sub-style required, biomedical query ranking`

---

# Phase 7 — Form-body / query-string project resolution

**Scope:** `/api/data/load` reads `project_slug` from form body only. External
uploaders without that field default to `__root__`. The fix: read from form
body OR query string OR Referer URL, in priority order.

This is the small bug that started the cascade in the dogfood. Listed late
because the fix is tiny.

## Tasks

### T7.1 — `resolveProjectFromRequest()` helper

`src/lib/projects.ts`:

```ts
export function resolveProjectFromRequest(
  request: Request,
  formData?: FormData,
): Project | null {
  const url = new URL(request.url);
  // Priority 1: query string ?project=
  let slug = url.searchParams.get("project");
  // Priority 2: form-body field "project"
  if (!slug && formData) {
    const fromForm = formData.get("project");
    if (typeof fromForm === "string") slug = fromForm;
  }
  // Priority 3: Referer URL
  if (!slug) {
    const ref = request.headers.get("referer");
    if (ref) {
      try {
        slug = new URL(ref).searchParams.get("project");
      } catch {}
    }
  }
  return resolveProject(slug ?? "__root__");
}
```

### T7.2 — Replace ad-hoc resolution in every route

Audit every API route's first 5 lines. Replace `body.project ?? "__root__"`
or `searchParams.get("project") ?? "__root__"` patterns with
`resolveProjectFromRequest(request, formData)`. Single source of truth.

### T7.3 — Regression test

`tests/route-project-resolution.test.mjs`:

```js
// 1. POST /api/data/load with multipart, no project field, no ?project= ->
//    expect 400 ("project required"), NOT silent fall-through to __root__.
// 2. Same multipart with project=foo -> resolves to foo.
// 3. Same multipart with no body field but ?project=foo in URL -> resolves.
// 4. No project anywhere, but Referer URL has ?project=foo -> resolves.
```

**Decision:** make `__root__` an explicit opt-in (`?project=__root__`), not
the silent default. Routes return 400 if no project resolution succeeds.
This is the safety net that prevents future "file landed at repo root"
incidents.

### Verification

- [ ] `curl -F file=@x.csv http://localhost:8769/api/data/load` (no project)
  returns 400.
- [ ] `curl -F file=@x.csv 'http://localhost:8769/api/data/load?project=foo'`
  works.
- [ ] All existing UI flows work (UI sets the form field).

**Commit:** `dashboard: Phase 7 project resolution — single helper across all routes, query/form/referer priority, no silent __root__ default`

---

# Phase 8 — Regression suite + smoke walk

**Scope:** lock every dogfood finding into the test suite. Future
regressions of these specific bugs fail CI before merge.

## Tasks

### T8.1 — Test suite by finding

For each finding, ensure at least one test asserts the bug doesn't recur.

| Finding | Test file | Asserts |
|---|---|---|
| #4 double-prefix | tests/parser-phase2-persistence.test.mjs | filenames don't double-prefix |
| #5 OpenAlex persistence | (same) | OpenAlex artifact persists |
| #7 first-name BibTeX keys | tests/parser-phase2-persistence.test.mjs | cite_key uses surname |
| #11 council timeout silent | tests/runner-failure.test.mjs | exit/timeout events surface |
| #12/#17 query-string ignored | tests/route-project-resolution.test.mjs | 400 when project missing |
| #13 stat tests slow | tests/run-stat-test.test.mjs | <10s wall clock for n=60 Pearson |
| #14 silent SIGTERM | tests/runner-failure.test.mjs | UI failure-state event emitted |
| #15 scatter Y=X default | tests/parser-phase6.test.mjs | Y default differs |
| #20 placeholder HTML leak | tests/parser-phase6.test.mjs | section default body has no raw HTML |
| #22 split-projects | tests/parser-phase1-paths.test.mjs | every persister writes under project.path |
| #24 export resolves cites | tests/parser-phase4-citations.test.mjs | exported markdown has no raw cite tokens |
| #25 cite_key resolution | tests/parser-phase4-citations.test.mjs | cite-marker resolves |
| #26 figures workspace refresh | tests/parser-phase6.test.mjs | legacy single-version figures render |

### T8.2 — End-to-end stress suite re-run

`tests/stress-suite.py` already covers 52 endpoints. Extend it with:

- A multipart upload to `/api/data/load` WITHOUT a project field — assert 400.
- A POST to `/api/draft/{slug}/export` with an unresolved cite-key — assert 422.
- A figure-gen (mocked subprocess that exits non-zero) — assert SSE failure event.

Target: **stress-suite.py reports 60+/60+ PASS** (was 52/52).

### T8.3 — Smoke-walk doc

`tests/v1-ship-gate-smoke-walk.md`: a 25-step manual walk that mirrors the
dogfood. Each step has a clear pass/fail criterion. Future humans run this
before any v1.x release.

Steps cover: project picker discovery -> /lit search relevance -> save 9
papers (all sources persist) -> BibTeX export with surname cite-keys ->
/hypothesis council fanout (with a real exit, not a hang) -> /data upload +
stat in <10s + plot in <5s -> /figures gen + lock + caption -> /draft
4-section with cite/fig resolved -> markdown export with full bibliography
-> no "Missing from library" lines.

### Verification

- [ ] `npm test` -> all unit + parser tests pass (target: ~30+ tests).
- [ ] `python3 tests/stress-suite.py` -> 60+/60+ PASS.
- [ ] Manual smoke walk -> 25/25 PASS.

**Commit:** `dashboard: Phase 8 regression suite — every dogfood finding locked into automated tests`

---

# Phase 9 — Re-run dogfood as ship gate

**Scope:** the same researcher loop as the May 6 dogfood, against the
existing `dogfood-glp1-weight-regain` brief project, with **zero
workarounds**. This is the v1.0 ship gate.

## Pre-conditions

- All Phases 1–8 commits merged.
- `dogfood-glp1-weight-regain` brief migrated to single root.
- Existing 6 PMID papers remain on disk; backfill has populated cite_key.

## Walk-through (must complete with zero manual fixes)

1. Open `http://localhost:8769/`. Pick `Dogfood Glp1 Weight Regain` from
   the project picker.
2. `/lit` -> search "GLP-1 weight regain after discontinuation".
   - **Pass criterion:** arXiv pre-disabled OR arXiv results ranked below
     PubMed/OpenAlex.
3. Save Berg 2025 (OpenAlex), Hubert 2026 (PubMed), Shah 2026 (PubMed),
   Wu 2025 (OpenAlex).
   - **Pass criterion:** all 4 papers persist to disk with `cite_key`
     populated.
4. EXPORT BIBTEX. Open the file.
   - **Pass criterion:** cite-keys are `Berg2025`, `Hubert2026`, `Shah2026`,
     `Wu2025` (surnames, not first names).
5. `/hypothesis`. Form claim "longer GLP-1 RA duration predicts slower
   regain rate". Link 3 papers. Click GENERATE VIA COUNCIL.
   - **Pass criterion:** within 5 minutes, all 3 personas surface critiques
     OR a clean Failed card with Retry button. No silent hang.
6. Click RECONCILE -> SYNTHESIS.
   - **Pass criterion:** synthesis card renders OR clean Failed card.
7. `/data`. Upload `glp1_regain_cohort.csv`.
   - **Pass criterion:** file lands at the brief's data dir (single root).
8. STATS tab -> Correlation -> X=`duration_months`, Y=`regain_rate_kg_per_month`
   -> Recommend -> Run.
   - **Pass criterion:** result card renders in **under 10 seconds** with
     r ≈ -0.43, p < 0.001, n=60. (Was 60+ seconds + sometimes silent timeout.)
9. PLOTS tab -> Scatter -> X=`duration_months`, Y defaults to a different
   numeric column -> set Y=`regain_rate_kg_per_month` -> Color=`drug` -> Generate.
   - **Pass criterion:** scatter renders in <10 seconds with stratified legend.
10. `/figures` -> New figure -> "schematic of weight trajectory ..." -> style
    Scientific -> sub-style Conceptual -> Generate.
    - **Pass criterion:** GENERATE button disabled until sub-style chosen;
      after gen, image appears in workspace within ~60s; figure list shows
      the new figure WITH versions.
11. Lock + caption.
    - **Pass criterion:** caption appears in card; locked=true on disk.
12. `/draft` -> New manuscript "Treatment duration predicts ...".
13. Introduction section: write text using a cite marker for `Berg2025` and
    a fig marker for the scatter id.
    - **Pass criterion:** preview resolves the cite marker to `[1]` and
      embeds the scatter inline.
14. Methods, Results, Discussion: add minimal content. Use cite marker for
    `Hubert2026` in Discussion.
15. Export -> Markdown.
    - **Pass criterion:** the exported markdown contains:
      - Numeric citations like `[1]`, `[2]` (not raw cite-marker tokens)
      - Embedded image markdown (not raw fig-marker tokens)
      - A bibliography section with proper APA / Nature / IEEE / Vancouver
        entries (depending on style)
      - **Zero `Missing from library:` lines.**
16. `/runs`. Inspect the council and stat runs.
    - **Pass criterion:** each run has a terminal status (succeeded/failed),
      not "still running" indefinitely.

## Outcome doc

After the walk: write `tests/v1-ship-gate-RESULT.md` with pass/fail per
step. If all 25 steps pass, the dashboard ships as v1.0. If any fail, the
specific failure becomes a new finding for a v1.0.1 sprint.

**Commit:** `dashboard: v1.0 ship gate — dogfood re-run, all 25 steps PASS`

---

# Out of scope (deferred to v1.x)

- FAL FLUX inpaint full roundtrip (gated on `FAL_KEY`; the API path is
  stable, just untested live).
- Pandoc/Marp PDF/DOCX exports (gated on user-side install).
- Substack export beyond the 501 stub.
- The 3 epistemic limits documented in `CLOSURE.md` (NLI contradiction,
  paywalled full-text, ledger HMAC) — those are documented limits, not
  bugs.
- Phase 2 markdown features (tables, footnotes, KaTeX) — researchers using
  inline math will see literal text in preview. Worth its own phase later.
- Reorder UI: drag-and-drop instead of arrow buttons. Cosmetic.

---

# Estimated timeline

| Day | Work | Outcome |
|---|---|---|
| 1 | Phase 0 decisions + Phase 1 (path canonicalization + migration) | One canonical project root, dogfood project migrated |
| 1 | Phase 2 (persistence correctness) | All sources persist, cite-keys correct, no double-prefix |
| 2 | Phase 3 (run-state surfacing) | Failure state visible in UI, /runs shows failed runs |
| 2 | Phase 4 (citation pipeline) + Phase 5 (direct stats) | Cites resolve in export, stats < 10s |
| 3 | Phase 6 (renderer + UX polish) + Phase 7 (project resolution) | Polished + robust to external uploaders |
| 3 | Phase 8 (regression suite + smoke walk doc) | Bugs locked out of CI |
| 4 | Phase 9 (ship gate dogfood re-run) | v1.0 ships or v1.0.1 list |

**Total: 4 working days, 8 atomic commits, one ship gate.**

# Final note on reliability

The biggest reliability win is Phase 3 (run-state surfacing) + Phase 5
(direct stats). After these, the dashboard's failure modes become *visible*
instead of *silent*. Future bugs degrade to "researcher sees red Failed
card and retries" rather than "researcher waits forever and loses work".

That is the difference between a v1.0 that researchers can trust and a
v0.9 that requires them to know its quirks.
