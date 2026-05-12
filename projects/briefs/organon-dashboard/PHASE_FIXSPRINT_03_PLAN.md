---
phase: fixsprint-03
title: Persistence-layer correctness — bare ids, cite_key first-class, HTML decode, dogfood backfill
date: 2026-05-06
fixplan_phase: 2 (T2.1, T2.2, T2.3, T2.4, T2.5, T2.6)
estimated_effort: 0.5 day (actual)
---

# Phase fixsprint-03 — PLAN

## Phase 0.5 audit

Five concrete bugs land in this phase, all surfaced by the dogfood report:

| Bug | Surface | Root cause |
|---|---|---|
| Finding #4 — `pmid-pmid:NNNNN` filenames | `papers/` listing | `pubmed.ts` returned `id: \`pmid:\${pmid}\`` and `search.ts:181` re-prefixed with `pmid-`. |
| Finding #5 — only PubMed sources persisted | `/lit` save UI showed Saved but JSON never landed | `openalex.ts` returned `id: work.id` (full URL). `path.join(libraryDir, "${id}.json")` got slashes in the filename. Silent FS fail. |
| Finding #7 — BibTeX cite-keys used FIRST names | export blob | `bibtex.ts:bibtexKey` took `authors[0].split(/\s+/)[0]` — for PubMed's "First Last" the [0] is the first name. |
| Finding #25 — persisted JSONs had no `cite_key` | `\cite{<token>}` resolution | Cite-key was BibTeX-export-time derived only; not stored on the artifact. Different consumers re-derived differently → "Missing from library." |
| Finding #3 — HTML entities in journal/abstract | preview, BibTeX, bib | PubMed XML ships `&amp;`, `&lt;sub&gt;`, `&#x2014;`. Nothing decoded them on the way to disk. |

Each is a one-spot fix. The combined surface area is small.

## Goal (one sentence)

The persist layer normalizes source ids, decodes HTML, and stamps a
unique surname-based `cite_key` on every paper at save time; the dogfood
library is backfilled to match.

## Non-goals (explicit)

- **Do NOT change the PaperArtifact schema_version.** New `cite_key`
  is optional + nullable so legacy artifacts parse fine; backfill fills
  the gap. A schema_version bump waits for a real breaking change.
- **Do NOT auto-rewrite manuscript `\cite{<token>}` tokens.** The dogfood
  manuscript wrote `\cite{Sara2025}` (legacy first-name form) and
  `\cite{Patrice2026}` (similar). With cite_keys now `Shah2026` etc.,
  those tokens won't resolve. The fix here is *tolerant* lookup
  (cite_key OR id), not data rewrite — that's the user's call.
- **Do NOT touch run-state surfacing.** That's Phase 4 (FIXPLAN P3).

## Tasks

### T3.A — Strip source-prefix from each search source's id

| File | Change |
|---|---|
| `src/lib/paper-search/pubmed.ts:89` | `id: \`pmid:${pmid}\`` → `id: pmid` |
| `src/lib/paper-search/arxiv.ts:67` | `id: \`arxiv:${arxivId}\`` → `id: arxivId` |
| `src/lib/paper-search/semanticscholar.ts:41` | `id: \`s2:${paper.paperId}\`` → `id: paper.paperId` |
| `src/lib/paper-search/openalex.ts:71` | `id: work.id` (full URL) → `id: bareWorkId` (extracted W-id) |

Closes Finding #4 (PubMed double-prefix) and Finding #5 (OpenAlex slashes
broke filename).

### T3.B — `cite_key` first-class on PaperArtifact

- `src/lib/artifacts/types.ts` — add `cite_key?: string | null`.
- New `src/lib/lit/cite-key.ts`:
  - `firstAuthorSurname(paper)` — handles "First Last", "Last, First",
    single-token. Returns "Anonymous" on empty.
  - `paperToCiteKey(paper, existingKeys)` — surname + year + collision
    suffix (`b`/`c`/.../`z`); fallback `${base}-${id.slice(0,8)}` past 26.
- `src/lib/lit/library.ts:savePaper`:
  - If `paper.cite_key` not set, read sibling JSONs (excluding self), gather
    cite_keys, compute unique key, stamp it.
  - Idempotent: re-saving the same paper keeps its key (because the self-row
    is excluded from `existingKeys`).
- `src/lib/lit/bibtex.ts:bibtexKey` — reads `paper.cite_key` first;
  legacy first-token derivation kept as fallback for un-backfilled libraries.
- `src/lib/draft/bib.ts:compileBibliography` — builds two indices
  (`byCiteKey` + `byId`); lookup is `byCiteKey ?? byId`. Closes the dogfood
  Finding #24 cause for `\cite{Sara2025}`-style tokens.
- `src/lib/draft/render.ts:175` — same tolerant lookup at `\cite{}`
  resolution time.

### T3.C — HTML entity decode + safe-tag strip

New `src/lib/lit/html-decode.ts`:
- `decodeEntities(s)` — named (`&amp;` → `&`, plus 18 others), decimal
  (`&#039;`), hex (`&#x2014;`). Unknown entities pass through unchanged.
- `stripSafeTags(s)` — strips `b/i/em/strong/sub/sup` *only*, preserves
  contents, leaves all other tags intact.

`savePaper` calls `stripSafeTags(decodeEntities(...))` on `journal` and
`abstract` before the atomic write. Closes Finding #3.

Zero deps — no `he` package. The 20 named entities + numeric/hex coverage
handles everything PubMed/OpenAlex/arXiv ship in practice.

### T3.D — `scripts/backfill-papers.mjs`

Walks `<root>/projects/**/papers/*.json`. For each paper:
1. Strip redundant prefix from `id` (`pmid-pmid:` → `pmid-`, etc.).
2. Strip prefix from `source_ids.<source>`.
3. Decode HTML entities + strip safe tags in journal/abstract.
4. Compute `cite_key` if missing (deterministic order: year ASC, id ASC).
5. Update `library_path` to track the rename.
6. Write new file atomically; remove old file if id changed.
7. Update sibling `hypotheses/<hyp_id>/hypothesis.json` `paper_ids` to
   match renames.

`--dry-run` (default) and `--apply` flags. Idempotent. Pure Node 20+
stdlib — mirrors the cite-key + html-decode logic in plain JS so the
script doesn't need a TS compile step.

### T3.E — Run backfill on dogfood

Dry-run: 16 paper changes (10 in arena-agentic-upgrade just adding
cite_key — those papers were already prefix-clean; 6 in dogfood needing
rename + cite_key + entity decode), 1 hypothesis update tracking the 3
dogfood paper renames.

Apply: all 16 paper changes + 1 hypothesis update. `pmid-pmid:NNNNN.json`
files renamed to `pmid-NNNNN.json`; `cite_key` populated:
- pmid-41889156 → Shah2026
- pmid-41909366 → QuimbayoCifuentes2026
- pmid-41931049 → Rosen2026
- pmid-41978101 → Kim2026
- pmid-42055215 → Hubert2026
- pmid-42068458 → Mack2026

Idempotent re-run: 0 changes.

### T3.F — Regression test `tests/route-paper-persistence.test.mjs`

9 tests covering each of T3.A–T3.E:
- Bare id in each search source (source-text scan).
- `cite_key` field declared on PaperArtifact.
- Pure-fn unit tests for `paperToCiteKey` collision suffixing.
- Pure-fn unit tests for `decodeEntities` (named/decimal/hex) +
  `stripSafeTags` (allow-list scope).
- savePaper wires cite-key + html-decode (source-text scan).
- bibtexKey prefers cite_key; bib lookup is cite_key OR id.
- Backfill script flags + apply-is-opt-in.
- FS post-state: every dogfood paper file has cite_key, no double prefix,
  no `source_ids.pmid` prefix, hypothesis paper_ids track renames.

## Verification checklist

- [x] `find projects/briefs/dogfood-glp1-weight-regain/papers -name 'pmid-pmid:*'` returns nothing.
- [x] Every persisted dogfood paper has a `cite_key` field.
- [x] Every persisted dogfood paper has prefix-clean `source_ids`.
- [x] `npm test` clean: 34/34 (25 prior + 9 P3).
- [x] `npm run typecheck` clean.
- [x] `npm run build` clean.
- [x] `node scripts/backfill-papers.mjs --dry-run` after apply reports 0 changes.

## Commit message

```
dashboard: Phase 3 (fix-sprint) — persistence correctness + cite_key + HTML decode + dogfood backfill

Closes FIXPLAN Phase 2 (T2.1–T2.6) and dogfood Findings #3, #4, #5, #7, #25.

- pubmed/arxiv/semanticscholar/openalex source modules now return a
  bare id (no `pmid:` / `arxiv:` / `s2:` prefix; OpenAlex returns the
  bare W-id, not the full URL). The original `https://openalex.org/...`
  URL is preserved as `url` for the deep-link UI. This single fix closes
  Finding #4 (pmid-pmid: double prefix) and Finding #5 (OpenAlex slashes
  broke `papers/<id>.json` filename → silent persist failure).
- New src/lib/lit/cite-key.ts: surname-based cite-key generator with
  collision suffix (a/b/c/.../z, then `${base}-${id.slice(0,8)}` for
  the pathological case). PaperArtifact now carries `cite_key?: string`
  optional + nullable.
- savePaper computes a unique cite_key when the artifact doesn't carry
  one (re-saving the same paper is idempotent — self-row excluded from
  the existingKeys set).
- New src/lib/lit/html-decode.ts: zero-dep decodeEntities (named +
  decimal + hex; 20 named entities) + stripSafeTags (b/i/em/strong/
  sub/sup allow-list, preserves contents). savePaper applies both to
  journal + abstract before write.
- bibtexKey now prefers paper.cite_key (legacy first-token derivation
  kept as fallback). compileBibliography + draft/render lookup resolve
  by cite_key OR id, so manuscripts authored with either form still
  render their bibliography correctly.
- New scripts/backfill-papers.mjs (Node 20 stdlib, no deps).
  --dry-run is the default; --apply opt-in. Walks every
  projects/**/papers/*.json, fixes ids + source_ids, decodes HTML,
  computes cite_keys, renames files, updates sibling
  hypotheses/<hyp_id>/hypothesis.json paper_ids to track renames.
  Idempotent.
- Ran the backfill: 16 paper changes (10 in arena-agentic-upgrade,
  6 in dogfood) + 1 hypothesis update. Dogfood papers renamed from
  `pmid-pmid:NNNNN.json` to `pmid-NNNNN.json`; cite_keys assigned
  (Shah2026, Rosen2026, ...).
- New tests/route-paper-persistence.test.mjs (9 tests).

Verification:
- npm test: 34/34 PASS (25 prior + 9 P3)
- npm run typecheck: clean
- npm run build: clean

Out of scope (Phase 4 ≈ FIXPLAN Phase 3): async run-state surfacing —
the biggest UX bug per the dogfood report (silent SIGTERM at ~3:35
in the council fanout, no UI failure state, no Cancel/Retry button).
```
