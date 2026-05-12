---
phase: fixsprint-05
title: Citation pipeline correctness — single resolver, 422 on unresolved, cite_key autocomplete
date: 2026-05-06
fixplan_phase: 4 (T4.1–T4.6)
estimated_effort: 0.5 day (actual)
---

# Phase fixsprint-05 — PLAN

## Phase 0.5 audit

The dogfood Finding #24 was the citation-pipeline split:

> The three-pane editor's live preview resolves `\fig{fig-...}` to the
> matplotlib scatter inline. But `Export → Markdown` ships the raw
> `\fig{}` and `\cite{}` LaTeX tokens — the export doesn't run the same
> renderer the preview does. Bibliography section was always "Missing
> from library:" because the `library.find(p => p.id === id)` lookup at
> render time uses paper.id but cite-marker tokens are surnames.

Phase 3 closed the lookup half (`cite_key` first-class on the artifact;
preview/render bib both fall back to id). The export half was still raw.

Other gaps the audit surfaced:
- `render.ts:184` had its own surname extractor (`paper.authors[0]?.split(",")[0]?.split(" ").pop()`)
  duplicating `firstAuthorSurname` from `bib.ts`. Two places, two slightly
  different rules — stale by definition.
- `embed-autocomplete.tsx` offered `paper.id` (e.g. `pmid-41889156`) as the
  insertable token — users got long opaque ids instead of the cite_keys
  they ought to type.

## Goal (one sentence)

Preview HTML and markdown export run through one resolution pass; the
export route fails fast (422) on unresolved tokens unless the user passes
`force=true`; the autocomplete picker offers `cite_key` as the inserted
token sorted by recency.

## Non-goals (explicit)

- **Do NOT auto-rewrite the dogfood manuscript.** The user typed
  `\cite{Sara2025}` and `\cite{Patrice2026}` against the legacy first-name
  cite-keys. Phase 3's surname-based keys are `Shah2026`, `Rosen2026`, etc.
  Those tokens stay unresolved by design — the user's call whether to
  rewrite or live with the warning.
- **Do NOT add a footer formatter.** The unresolved cite-marker leaves a
  visible breadcrumb (`[unresolved \cite{Sara2025}]`) in the markdown so
  the export reader sees what's missing without an extra footer pass.
- **Do NOT touch direct-Python stat tests.** That's Phase 6 (FIXPLAN P5).

## Tasks

### T5.A — `src/lib/draft/resolve.ts` — single pre-resolution pass

`resolveCitesAndFigs(input)` →
`{resolvedSections, citationOrder, figureOrder, unresolvedCites, unresolvedFigs, citationLabel, figureLabel}`.

Pure function. Lookup is `cite_key OR paper.id` (Phase 3 contract).
APA → `(Surname, Year)` per cite; numeric (Nature/IEEE/Vancouver) →
`[N]` per cite, multi-cite collapses to `[1, 2]`. Figures become
`![alt](url)\n\n*Fig. N.* caption`.

Unresolved tokens stay as `[unresolved \cite{tok}]` /
`[unresolved \fig{id}]` markdown breadcrumbs AND show up in the
unresolved sets so the export route can decide.

### T5.B — `assembleMarkdown` returns `{md, unresolvedCites, unresolvedFigs}`

`render.ts`. Same function name; new return shape. Internally calls
`resolveCitesAndFigs` once, then appends the formatted bibliography (via
`compileBibliography`). Default `figureUrl` is `figures/<fig_id>/<png>`
(relative to the exported `.md` file; Pandoc/Marp can find PNGs sitting
next to the export).

### T5.C — Surname unification

`render.ts` — replace inline `paper.authors[0]?.split(",")[0]?.split(" ").pop()`
with `firstAuthorSurname` from `bib.ts`. Single source of truth.

### T5.D — Export route 422 on unresolved + `force=true` opt-in

`src/app/api/draft/[slug]/export/route.ts`:

- Pull `figures = listFigures(project.path)` for token resolution.
- `assembled = assembleMarkdown(meta, sections, library, figures)` —
  carries unresolved sets.
- If `!body.force && (unresolvedCites.length > 0 || unresolvedFigs.length > 0)`:
  return 422 with `{error, unresolved_cites, unresolved_figs}`.
- Otherwise ship; the response carries a `warnings: string[]` field listing
  any breadcrumbs that survived the force flag.

### T5.E — Embed autocomplete offers `cite_key`

`src/components/draft/embed-autocomplete.tsx`:

- Sort library by `saved_at` descending so freshly-saved papers float to
  the top of the picker.
- The inserted token is `paper.cite_key ?? paper.id`. Sub-line shows the
  paper.id so users can still locate the file on disk if needed.

### T5.F — Regression test `tests/draft-citations.test.mjs`

6 tests:
1. resolve.ts exports the documented shape + `byCiteKey ?? byId` lookup.
2. Pure-fn mirror: APA → `(Surname, Year)`; numeric → `[N]`; multi-cite
   collapses to `[1, 2]`; unresolved tokens populate the result + leave
   breadcrumbs.
3. Pure-fn mirror: cite_key OR paper.id resolves both legacy + new tokens.
4. assembleMarkdown returns `{md, unresolvedCites, unresolvedFigs}` and
   uses `firstAuthorSurname`.
5. Export route 422s on unresolved + accepts `force=true` to bypass +
   forwards `unresolved_cites`/`unresolved_figs` arrays.
6. Embed autocomplete inserts `cite_key`, sorts by saved_at, shows
   paper.id in the sub-line.

## Verification checklist

- [x] `npm test` clean: 49/49 (43 prior + 6 P5).
- [x] `npm run typecheck` clean.
- [x] `npm run build` clean.
- [x] Existing dogfood manuscript (`\cite{Sara2025}` / `\cite{Patrice2026}`)
      now correctly returns 422 from the export route — those tokens
      should be unresolved against Phase 3's `Shah2026`/etc. cite_keys.
      `?force=true` passes through with `[unresolved \cite{...}]`
      breadcrumbs in the markdown.

## Commit message

```
dashboard: Phase 5 (fix-sprint) — citation pipeline correctness, single resolver, 422 on unresolved

Closes FIXPLAN Phase 4 (T4.1–T4.6) and dogfood Finding #24 (preview vs
export divergence).

- New src/lib/draft/resolve.ts: resolveCitesAndFigs(input) →
  {resolvedSections, citationOrder, figureOrder, unresolvedCites,
  unresolvedFigs, citationLabel, figureLabel}. Pure function. Lookup
  is cite_key OR paper.id (Phase 3 contract). APA → "(Surname, Year)";
  numeric → "[N]" with multi-cite collapsing to "[1, 2]". Figures
  become `![alt](url)\n\n*Fig. N.* caption`. Unresolved tokens leave
  visible markdown breadcrumbs AND populate the unresolved sets.
- assembleMarkdown now returns {md, unresolvedCites, unresolvedFigs}.
  Default figureUrl is `figures/<fig_id>/<png>` (relative to the
  exported .md so Pandoc/Marp can find PNGs sitting next to the export).
- render.ts (preview HTML) uses firstAuthorSurname from bib.ts —
  single source of truth for surname extraction.
- /api/draft/[slug]/export route returns 422 with
  {unresolved_cites, unresolved_figs} when there are unresolved
  tokens, unless body.force === true (in which case the response
  carries a warnings array). listFigures wired up so figure tokens
  participate in resolution.
- embed-autocomplete inserts paper.cite_key (paper.id fallback for
  pre-Phase-3 papers); library sorted by saved_at recency; sub-line
  surfaces paper.id so the user can still locate the file on disk.

Tests:
- tests/draft-citations.test.mjs (6 tests): pure-fn mirror exercises
  APA/numeric labels, multi-cite, cite_key vs id resolution, unresolved
  breadcrumbs. Source-text scans validate render.ts shape, export
  route 422 + force, autocomplete cite_key handling.

Verification:
- npm test: 49/49 PASS (43 prior + 6 P5)
- npm run typecheck: clean
- npm run build: clean

Out of scope (Phase 6 ≈ FIXPLAN Phase 5): direct-Python stat tests
- 5 s deterministic subprocess (like plots), not a 60 s LLM call;
LLM becomes opt-in "Interpret" button.
```
