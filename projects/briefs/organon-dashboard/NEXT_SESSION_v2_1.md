<!-- no-cite reason="Pickup brief documenting v2.1 fix track from 2026-05-08 dogfood walk; the file is plan + testing scaffold, not publishable prose." -->

# Next-Session Pickup — v2.1 fix sprint (TDD-first + browser E2E)

**Last updated:** 2026-05-08, after researcher's hands-on dogfood walk through v2.0 (commits b6cf983 → 0a4e073).
**Branch:** `main`. **Working tree:** clean after v2.0 closeout (commit `0a4e073`).
**Local tags:** v1.0 → v1.6 should be tagged at this point if researcher authorised; v2.0 still pending researcher authorisation per `reference_git_remotes.md`. **v2.1 is a fresh tag at the end of this brief.**
**Push policy:** local-only per `reference_git_remotes.md`.

This brief is **self-contained and TDD-first**. Every issue is mapped to a fix phase with a falsifiable contract. After the fixes ship, a browser E2E pass via `mcp__claude-in-chrome__*` exercises every observed surface.

---

## 1. What's broken (researcher-observed, 2026-05-08)

Five bug fixes (🔴/🟠) + four UX gaps (🟡/🟠) surfaced during the v2.0 dogfood walk. Mapped to phases 55–61.

| Phase | ID | Issue | Severity | Effort | Closes |
|---|---|---|---|---|---|
| **55** | A1 | Paperclip MCP returns HTTP 401; fallback works but banner is noisy | 🟠 | ~1.5h | "paperclip: HTTP 401 — falling back to API tier" |
| **56** | A2 | Relevance scores collapse to 0.00 for many results; high-confidence filter hides everything | 🔴 | ~3h | "all articles seem to have zero confidence score" |
| **57** | A3 | Hypothesis status `supported → refuted` blocked; user must go through synthesized | 🔴 | ~1h | "Invalid status transition: supported → refuted" |
| **58** | B1 | Hypothesis history has no × delete affordance | 🟠 | ~1h | "we should also have some small x icon to delete" |
| **59** | B2+B3 | Claim-form linked-paper picker is flat (no batch grouping); "ALL/SHOW ALL" submits form mid-edit | 🔴 | ~3h | "this hamburger style drop down menu with the research queries" + "when I click show all… it immediately starts the hypothesis generation" |
| **60** | A5 | Propose Title returns "no candidates" when linked hypothesis + papers exist | 🔴 | ~2h | "Why it cannot propose any title" |
| **61** | B4+B5+C1+A4 | Section list density + sources panel help-text + search-query copy icon + stale "succeeded-no-artifact" toast on retry-success | 🟠 | ~3h | "left section seems to be very congested" + "small copy icon" + "does that mean that it can access to all these prior knowledge?" + ghost failure toast |

**Total:** ~14.5h across 7 commits / 7 phases. Test target ~417 → ~445.

---

## 2. Recommended ordering (load-bearing)

| Order | Phase | Effort | Why this slot |
|---|---|---|---|
| 1 | **55** A1 | 1.5h | Paperclip noise pollutes every lit search; fix first so subsequent walks are clean. |
| 2 | **56** A2 | 3h | Relevance scoring is the most visible regression; researcher cannot triage results without it. |
| 3 | **57** A3 | 1h | One-liner state-machine relaxation; unblocks hypothesis triage. |
| 4 | **58** B1 | 1h | Adds the missing UI affordance for an existing DELETE route. |
| 5 | **59** B2+B3 | 3h | Surface bug + UX rework in the claim-form. B3 is a one-line fix piggybacked. |
| 6 | **60** A5 | 2h | Propose Title is broken end-to-end; needs prompt + zero-state debugging. |
| 7 | **61** B4+B5+C1+A4 | 3h | Polish + scroll/clear-on-retry fix. Lands last. |

**Suggested partition:** single ~14.5h session lands all seven. Two-session split is 55–58 (~6h) then 59–61 (~8h). If a session has ≤ 3h, ship Phases 55 + 56 only (literature reliability).

---

## 3. Pre-flight checklist (5 min, mandatory)

```bash
cd /Users/keremdelikoyun/Projects/scientific-os
git log --oneline -8
# Should show v2.0 lineage on top (0a4e073).

cd projects/briefs/organon-dashboard
npm test                              # 417/417 expected
npm run typecheck && npm run build
lsof -i :8769 -sTCP:LISTEN            # if empty: npm run dev (and leave open)
python3 tests/stress-suite.py         # 52/52
```

If anything is not green, **do not start**. Diagnose first.

---

## 4. TDD methodology (unchanged from v1.x–v2.0)

Same source-text-scan + inline behavioural replicas via `readFileSync` + regex; no tsx, no ts-node, no real `claude -p` spawns, no real S2/PubMed/paperclip calls. Browser E2E via `mcp__claude-in-chrome__*` runs AFTER every code phase ships.

---

## 5. Phase 55 — Paperclip auth + better fallback messaging (A1) ~ 1.5h

**Goal:** investigate the 401, fix or document it, and emit a cleaner banner. Two outcomes acceptable:
1. **Auth fix lands** (header, token env var, endpoint update) — banner stays only in genuine outage.
2. **Auth fix not possible in-session** — soft-disable paperclip in `.env` (`PAPERCLIP_DISABLED=1`), suppress the banner when disabled, and log a one-time console note instead.

### 5.1 Investigation steps

```bash
# 1. Hit the endpoint directly to confirm 401 is server-side, not us.
curl -sS -i https://paperclip.gxl.ai/mcp -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{}}' | head -20

# 2. Check .mcp.json — is paperclip configured with auth headers?
grep -A4 '"paperclip"' .mcp.json

# 3. Check whether the wrapper sends the right MCP init handshake.
grep -n "paperclip-search\|jsonrpc\|initialize" src/lib/lit/paperclip-search.ts
```

Likely outcomes:
- **a.** 401 even with curl → server-side auth requirement; need an env var (e.g. `PAPERCLIP_API_KEY`). Service Registry update.
- **b.** 200 with curl but 401 from wrapper → wrapper's missing the MCP `initialize` step before `tools/call`. Add the two-step handshake.
- **c.** 200 with curl after retry → transient endpoint issue. No code fix; document.

### 5.2 Files

| File | Change |
|---|---|
| `src/lib/lit/paperclip-search.ts` | If outcome **b**: add `initialize` handshake + capability negotiation before `tools/call`. If outcome **a**: read `process.env.PAPERCLIP_API_KEY` and stamp `Authorization: Bearer ${key}` header. |
| `src/lib/lit/search.ts` | Soft-error wording change: replace `paperclip: paperclip HTTP 401 — falling back to API tier` with `paperclip: temporarily unavailable (HTTP 401) — using PubMed/arXiv/OpenAlex/S2 instead`. |
| `.env.example` | Add `PAPERCLIP_API_KEY=` (commented) if outcome **a**. Add `PAPERCLIP_DISABLED=` (commented) for opt-out. |
| `CLAUDE.md` Service Registry | New row for paperclip auth (outcome **a**) or note (outcome **c**). |

### 5.3 Tests

NEW `tests/lit-paperclip-fallback.test.mjs` — 4 tests:

```javascript
test("Phase 55 — paperclip wrapper sends initialize handshake before tools/call");
test("Phase 55 — PAPERCLIP_DISABLED=1 short-circuits the wrapper without HTTP call");
test("Phase 55 — soft_errors message reads 'temporarily unavailable', not 'HTTP 401'");
test("Phase 55 — auth header attached when PAPERCLIP_API_KEY is set");
```

### 5.4 Decisions to lock

- **Fail-soft remains the contract.** Any 4xx/5xx from paperclip → soft_errors[] + fall back to API tier. Never bubble red.
- **Banner copy is researcher-readable.** "Temporarily unavailable" is honest about the state without leaking HTTP plumbing.
- **No retries in v2.1.** Paperclip 401 is structural (auth), not transient (rate-limit). Retry would just waste latency.

### 5.5 Commit

```
dashboard: Phase 55 (v2.1) — paperclip MCP auth + cleaner fallback banner (A1)
```

---

## 6. Phase 56 — Relevance scoring fix + IDF corpus expansion (A2) ~ 3h

**Goal:** investigate the 0.00 floor, fix the scorer to emit non-zero for legitimate matches, and expand the IDF corpus from ~190 tokens to ≥ 1500 (still short of the 5000 target documented in NEXT_SESSION_v1_6.md §7.3, but enough for the common biomedical vocabulary).

### 6.1 Investigation

```bash
# 1. Walk the scorer with a real query that returned 0.00 in the dogfood walk.
node -e '
  const { scoreRelevance } = require("./src/lib/lit/relevance.js");
  const paper = { title: "Surviving Sepsis Campaign: International Guidelines for Management of Severe Sepsis and Septic Shock, 2012", abstract: "..." };
  console.log(scoreRelevance("sepsis bacterial infection guidelines", paper));
'
# Expected breakdown: title=non-zero (every word in title), abstract=non-zero (sepsis appears).
# If actual=0.00 → bug; trace through the function.

# 2. Inspect the corpus.
wc -l src/lib/lit/relevance-corpus.json
jq 'keys | length' src/lib/lit/relevance-corpus.json
jq '.sepsis // "missing"' src/lib/lit/relevance-corpus.json
```

Likely root causes (one or more):
- **a.** Corpus is too small; query tokens miss the IDF table → fallback IDF defaults to 0 (not 1) → score collapses.
- **b.** Abstract field is `undefined` on OpenAlex results because the wrapper doesn't read `inverted_abstract` (OpenAlex stores abstracts as `abstract_inverted_index`). Title-only scoring caps at 0.4.
- **c.** Empty-abstract heuristic (Phase 47) only fires on exact-match perfect-title; one-token mismatches break it.
- **d.** Tokenizer is over-aggressive (lowercase + strip punctuation) causing query terms to never match paper text.

### 6.2 Files

| File | Change |
|---|---|
| `src/lib/lit/relevance.ts` | Replace IDF fallback `0` with `1` (every unknown term contributes equally). Add unit test. Soften empty-abstract heuristic: ≥ 80% query-token coverage on title with empty abstract → score 0.7+ (was: 100% match → 0.9). |
| `src/lib/lit/relevance-corpus.json` | Expand from ~190 to ≥ 1500 tokens. Use a simple build script (`scripts/build-relevance-corpus.mjs`) that scrapes the top 1500 nouns from the existing fixtures + a static MeSH-style biomedical word list shipped under `tests/fixtures/biomedical-tokens.txt`. |
| `src/lib/lit/openalex-fetcher.ts` (or wherever OpenAlex results are mapped) | If abstract is empty, decode `abstract_inverted_index` per OpenAlex API docs. Test: fixture with inverted index → resolves to readable abstract. |
| `scripts/build-relevance-corpus.mjs` *(NEW)* | One-shot offline builder; idempotent. Outputs `src/lib/lit/relevance-corpus.json`. |

### 6.3 Tests

Update `tests/lit-relevance-scoring.test.mjs` and add new ones:

```javascript
test("Phase 56 — unknown query token defaults IDF to 1 (not 0), so partial matches score > 0");
test("Phase 56 — OpenAlex inverted-abstract index decodes to readable abstract");
test("Phase 56 — corpus has ≥ 1500 tokens after rebuild");
test("Phase 56 — query 'sepsis bacterial infection' against a sepsis paper scores ≥ 0.6");
test("Phase 56 — empty-abstract heuristic relaxed: 80% query coverage on title → score ≥ 0.7");
```

### 6.4 Decisions to lock

- **IDF fallback = 1 (not 0).** Why: an unknown term should still count as evidence of overlap; collapsing it to 0 starves the score. Embeddings (v2.2+) make this moot but for IDF this is the right default.
- **OpenAlex `abstract_inverted_index` is decoded at fetch time, not at score time.** Why: keeps `scoreRelevance` pure; the wrapper materialises the abstract string once.
- **Corpus is a static asset.** v2.2+ may swap to embeddings; the same `scoreRelevance` interface stays.
- **Threshold stays 0.6** for "high confidence". Empty-abstract relaxation lowers to 0.7 from the 0.9 cap; exact-match still scores ≥ 0.9.

### 6.5 Commit

```
dashboard: Phase 56 (v2.1) — relevance scoring 0.00 fix + corpus expansion (A2)
```

---

## 7. Phase 57 — Hypothesis state-machine relaxation (A3) ~ 1h

**Goal:** allow direct `supported ↔ refuted` and `synthesized ↔ supported|refuted ↔ synthesized` without forcing the user to round-trip through `synthesized`. Today's `isValidTransition`:

```
synthesized → supported: ✅
synthesized → refuted:   ✅
supported  → synthesized: ✅
refuted    → synthesized: ✅
supported  → refuted:    ❌  ← change
refuted    → supported:  ❌  ← change
```

### 7.1 Files

| File | Change |
|---|---|
| `src/lib/hypothesis/store.ts` | Extend `isValidTransition`: also allow user-driven `supported ↔ refuted` directly. Allow `archived → open` (un-archive) for completeness. |
| `tests/hypothesis-status-state-machine.test.mjs` | Existing test pinned the old contract; relax + add coverage for the new edges. |

### 7.2 Tests

```javascript
test("Phase 57 — supported → refuted is a valid user transition");
test("Phase 57 — refuted → supported is a valid user transition");
test("Phase 57 — archived → open lets the user un-archive");
test("Phase 57 — skill-source still cannot do supported → refuted (only user)");
```

### 7.3 Decisions to lock

- **Skill-source remains restrictive.** sci-council can only do `open → synthesized`. User-source unlocks every reasonable transition.
- **No transition log shipped in v2.1.** "When did this flip from supported to refuted?" is a future audit concern; in-place is fine for now.

### 7.4 Commit

```
dashboard: Phase 57 (v2.1) — hypothesis state-machine relaxation (A3)
```

---

## 8. Phase 58 — Hypothesis × delete in history (B1) ~ 1h

**Goal:** add an × delete affordance per row in the history sidebar. The DELETE route already exists at `/api/hypothesis/[hyp_id]` (DELETE method). Just wire the UI.

### 8.1 Files

| File | Change |
|---|---|
| `src/components/hypothesis/hypothesis-history.tsx` | Add an × button per row (visible on hover). `data-hypothesis-delete={hyp_id}` sentinel. `window.confirm("Delete hypothesis '<claim_short>'? This cannot be undone.")` gate. On confirm → DELETE → callback up. |
| `src/components/hypothesis/hypothesis-workspace.tsx` | NEW `handleDeleteHypothesis(id)` → fetch DELETE → `setHypotheses(prev => prev.filter(h => h.id !== id))` → if `activeId === id` → clear activeId. |

### 8.2 Tests

NEW `tests/hypothesis-history-delete.test.mjs` — 4 tests:

```javascript
test("Phase 58 — hypothesis-history renders × button per row with data-hypothesis-delete sentinel");
test("Phase 58 — workspace declares handleDeleteHypothesis + threads it as prop");
test("Phase 58 — handler hits DELETE /api/hypothesis/[hyp_id]");
test("Phase 58 — workspace clears activeId when the deleted hypothesis was active");
```

### 8.3 Decisions to lock

- **Confirm gate via `window.confirm`** — same pattern as Phase 38 batch-delete. No bespoke modal.
- **Delete is hard-delete on disk.** Same as the existing DELETE route. No undo.

### 8.4 Commit

```
dashboard: Phase 58 (v2.1) — hypothesis × delete in history (B1)
```

---

## 9. Phase 59 — Claim-form picker batch grouping + show-all submit fix (B2+B3) ~ 3h

**Goal:** the linked-paper picker on the claim-form should group papers by `search_batch_id` (Phase 38 substrate) like the lit-library panel. Plus fix the "ALL/SHOW ALL" button that submits the form mid-edit.

### 9.1 Investigation (B3 first — five-minute fix)

```bash
grep -n "ALL\|SHOW ALL\|submit\|button" src/components/hypothesis/paper-picker.tsx
# Look for any <button> without explicit type="button" inside a <form>.
```

The picker is mounted inside `<ClaimForm>` which is `<form>`. Any unannotated `<button>` defaults to `type="submit"`.

### 9.2 Files

| File | Change |
|---|---|
| `src/components/hypothesis/paper-picker.tsx` | (B3) Audit every `<button>` inside the picker; ensure `type="button"` on every non-submit button (ALL / NONE / INVERT / SHOW ALL). |
| `src/components/hypothesis/paper-picker.tsx` | (B2) When `papers.search_batch_id` is non-null, group by batch (display the `search_batch_query` as a collapsible header — same hamburger UX as `library-panel.tsx`'s Phase 38 grouping). Default-collapsed batches show count + query; expand-on-click reveals the checkbox list. Ungrouped papers (legacy or via-skill saves) remain under "Ungrouped". |
| `src/components/hypothesis/claim-form.tsx` | Wrap the picker in a region with `aria-label="linked-papers"` so the test can pin it. |

### 9.3 Tests

NEW `tests/hypothesis-paper-picker-batch-grouping.test.mjs` — 6 tests:

```javascript
test("Phase 59 — paper-picker groups library papers by search_batch_id when present");
test("Phase 59 — ungrouped papers (legacy / via-skill) land under 'Ungrouped'");
test("Phase 59 — batch group header shows the search_batch_query");
test("Phase 59 — every non-submit button inside picker has type=\"button\" (B3 fix)");
test("Phase 59 — clicking ALL/NONE/INVERT does not call onSubmit");
test("Phase 59 — expanding a collapsed batch reveals the paper checkboxes");
```

### 9.4 Decisions to lock

- **Default-collapsed for B2.** Many papers across many batches → page is overwhelming if all expanded. Collapsed by default; user expands on demand. Mirror's Phase 38's library-panel.
- **B3 fix is global to the picker** — every button gets `type="button"` audited even if only one was definitely buggy. Cheap, prevents regression.

### 9.5 Commit

```
dashboard: Phase 59 (v2.1) — claim-form picker batch grouping + show-all submit fix (B2+B3)
```

---

## 10. Phase 60 — Propose Title from hypothesis-only state (A5) ~ 2h

**Goal:** when a manuscript has linked hypothesis(es) and a non-empty library but Propose Title still returns no candidates, dig in and fix.

### 10.1 Investigation

```bash
# 1. Read the route + skill prompt for generate-title.
sed -n '1,200p' src/app/api/draft/[slug]/generate-title/route.ts

# 2. Check Phase 49's zero-state fallback gate — is it firing too narrowly?
grep -n "zero_state_fallback\|linkedPapers\|linkedStatResults" src/app/api/draft/[slug]/generate-title/route.ts
```

Likely root causes:
- **a.** Phase 49's gate `if (linkedPapers.length === 0 && linkedStatResults.length === 0)` only fires the fallback when BOTH are empty. The dogfood case has `linkedPapers.length === 14` so the fallback path doesn't fire — but the regular path's prompt may not be threading the linked hypothesis.
- **b.** The skill (sci-writing generate-title mode) emits no `_artifact: title-candidate` JSON line for whatever reason — prompt malformed, hypothesis context too long, `\cite{}` placeholders confusing the skill.
- **c.** The route doesn't include `linked_hypothesis_ids[]` in the prompt at all (Phase 41 wired hypotheses for generate-section but maybe missed generate-title).

### 10.2 Files

| File | Change |
|---|---|
| `src/app/api/draft/[slug]/generate-title/route.ts` | Always thread linked hypotheses into the prompt (not just zero-state). Build a `linked_hypotheses=[{id, claim_short, status, council_confidence}, ...]` block per hypothesis the manuscript links to (Phase 41 substrate). Fall through to `additional_context_papers` shape that sci-writing already understands. |
| `src/app/api/draft/[slug]/generate-title/route.ts` | Add a `parse-debug` SSE event analogous to Phase 35's generate-section diagnostic — when the run succeeds but emits zero candidates, surface the trailing 200 chars of stdout so the next walk can debug without server-log access. |
| Skill prompt (`sci-writing/SKILL.md` Step 7.8) | Audit: does it require linked papers? When only a hypothesis is provided, does it know how to compose a title? If not, expand Step 7.8 to cover "hypothesis-only" + "hypothesis + sparse papers" cases. *(Note: skill changes ship in `.claude/skills/sci-writing/`, not the dashboard tree.)* |

### 10.3 Tests

NEW `tests/draft-propose-title-with-hypothesis.test.mjs` — 5 tests:

```javascript
test("Phase 60 — generate-title route threads linked_hypothesis_ids[] into the prompt");
test("Phase 60 — generate-title route emits parse-debug SSE event when no candidates returned");
test("Phase 60 — Phase 49 zero-state fallback still fires when both linked_papers + stat_results are empty");
test("Phase 60 — when linked hypotheses are present, the route passes claim_short + council_confidence to the skill");
test("Phase 60 — sci-writing's generate-title mode (Step 7.8) handles hypothesis-only context per its updated prompt");
```

### 10.4 Decisions to lock

- **Always thread hypotheses into generate-title.** Phase 49's "zero state" was too narrow. Hypotheses are first-class title evidence.
- **Surface a parse-debug event on success-with-no-candidates.** Honest done-state, same pattern as Phase 35's generate-section.
- **No skill rewrite if Step 7.8 already handles it** — investigation may show the prompt is fine and the dashboard was just under-feeding. In that case, Phase 60 is dashboard-side only.

### 10.5 Commit

```
dashboard: Phase 60 (v2.1) — propose-title threads linked hypotheses + parse-debug (A5)
```

---

## 11. Phase 61 — Section-list density + sources help-text + copy query + retry-clear toast (B4+B5+C1+A4) ~ 3h

**Goal:** four small UX patches bundled because each is < 30 LoC.

### 11.1 Files

| File | Change |
|---|---|
| `src/components/draft/section-list.tsx` | (B4) Move the GENERATE button + DRAFT badge + ⚙ src + ▲▼ controls into a SECOND row beneath the section label. Section labels now have full-width to themselves and read `## Abstract`, `## Introduction`, etc. Drop the `truncate` class on `text-sm` since wrapping is fine in the new layout. |
| `src/components/draft/source-linkage-panel.tsx` | (C1) Replace the cryptic header line with: "These artifacts feed every section's prompt. Empty linkage → use everything in this project. Tighten via the per-section ⚙ src override (Phase 51)." Add a `<details>` block with one paragraph per kind explaining its role at generation time. |
| `src/components/lit/library-panel.tsx` | (B5) Add a small copy icon (📋) next to each batch's query header. Click → `navigator.clipboard.writeText(query)` + a 1.5s "copied" tooltip. |
| `src/components/draft/manuscript-workspace.tsx` | (A4) When `handleGenerateSection` succeeds with a persisted artifact, clear `errors[]` and `setRunFailureMsg(null)` BEFORE the success state lands. Today the "succeeded-no-artifact" toast persists if a previous attempt failed even when a retry succeeds. Also auto-scroll the editor to the freshly-drafted content (Image 34's UX confusion was scroll-related). |

### 11.2 Tests

NEW `tests/draft-section-list-density.test.mjs` — 3 tests:

```javascript
test("Phase 61 — section-list lays out section label on its own row above the action chips");
test("Phase 61 — section labels are not truncated in the new layout");
test("Phase 61 — ⚙ src + GENERATE + DRAFT remain accessible via the same data-* sentinels");
```

NEW `tests/draft-sources-help-text.test.mjs` — 2 tests:

```javascript
test("Phase 61 — source-linkage-panel header includes the 'feed every section's prompt' help line");
test("Phase 61 — panel mounts a <details> block with per-kind explanation");
```

NEW `tests/lit-copy-query-button.test.mjs` — 3 tests:

```javascript
test("Phase 61 — library-panel renders a copy-query button per batch (data-copy-query sentinel)");
test("Phase 61 — clicking the copy button calls navigator.clipboard.writeText with the search_batch_query");
test("Phase 61 — a 'copied' confirmation appears for ≥ 1 second after click");
```

NEW `tests/draft-retry-clears-toast.test.mjs` — 2 tests:

```javascript
test("Phase 61 — successful generate-section retry clears stale failure messages BEFORE rendering success");
test("Phase 61 — workspace scrolls editor to the persisted section after a successful generate");
```

### 11.3 Decisions to lock

- **Two-row section row** — the cleanest fix for B4. Single-row densification (smaller fonts, hidden affordances) was rejected because affordance discoverability is a known pitfall (#11 from earlier briefs).
- **Copy button uses native `navigator.clipboard`** — no library. Falls back to silent failure on insecure contexts; not researcher-visible.
- **Toast clearing on success is the contract** — a retry that succeeds must close the loop. The earlier `succeeded-no-artifact` failure card stays until a new run succeeds; this is correct semantics.

### 11.4 Commit

```
dashboard: Phase 61 (v2.1) — section density + sources help + copy query + retry toast (B4+B5+C1+A4)
```

---

## 12. Cumulative effort + checkpoint protocol

| Phase | Effort | Files | Test files | New tests |
|---|---|---|---|---|
| **55** A1 | 1.5h | 3-4 | 1 | 4 |
| **56** A2 | 3h | 4 + 1 (NEW) | 1 (updated) | 5 |
| **57** A3 | 1h | 1 | 1 (updated) | 4 |
| **58** B1 | 1h | 2 | 1 (NEW) | 4 |
| **59** B2+B3 | 3h | 2 | 1 (NEW) | 6 |
| **60** A5 | 2h | 1 + skill SKILL.md | 1 (NEW) | 5 |
| **61** B4+B5+C1+A4 | 3h | 4 | 4 (NEW) | 10 |
| **TOTAL** | **14.5h** | ~17 files | **+9 test files (~38 tests)** | |

**After all 7 commits land:** `npm test` should be **~445/445** (~417 v2.0 baseline + ~28 net new — accounting for 10 updated assertions in existing test files).

**Checkpoint protocol** — after each commit: `npm test → typecheck → build → stress → memory update`. If any fails, stop.

---

## 13. Pitfalls / patterns carried forward (from Phases 1–54 + new for v2.1)

All 38 pitfalls from `NEXT_SESSION_v1_6.md` §11 carry forward unchanged. v2.1 adds:

- **#39.** **Buttons inside `<form>` elements need `type="button"` explicitly.** HTML default is `submit`. Always audit when adding new buttons inside any form.
- **#40.** **OpenAlex returns `abstract_inverted_index`, not `abstract`.** Decode at fetch time so downstream consumers see a normal string.
- **#41.** **State-machine transitions: skill-source must be more restrictive than user-source.** sci-council can only do `open → synthesized`; users can do anything reasonable.
- **#42.** **Failure cards must clear on a successful retry.** A stale toast that contradicts the current state is worse than no toast.

---

## 14. Test-count tracking (cumulative target)

| After commit | npm test count |
|---|---|
| Pre-v2.1 baseline (after v2.0) | ~417 |
| 55 (A1)             | ~421 |
| 56 (A2)             | ~426 |
| 57 (A3)             | ~430 |
| 58 (B1)             | ~434 |
| 59 (B2+B3)          | ~440 |
| 60 (A5)             | ~444 |
| 61 (B4+B5+C1+A4)    | ~445 |

---

## 15. Browser E2E test plan (`mcp__claude-in-chrome__*`, runs AFTER all 7 phases)

After every code phase ships green, fire this end-to-end browser walk. The dashboard runs at `http://localhost:8769`. Use `arena-agentic-upgrade` as the test project (it has 14 saved papers across 2 batches + 2 hypotheses + 1 manuscript per the dogfood walk artifacts).

**Pre-flight:** confirm dev server is up via `lsof -i :8769 -sTCP:LISTEN`. Open Chrome with `mcp__claude-in-chrome__tabs_create_mcp` to a fresh tab at the dashboard URL.

### Test E2E-1 — Literature surface (Phases 55+56+61)

1. Navigate to `/lit?project=arena-agentic-upgrade`.
2. **Phase 55 check:** banner above results either says "temporarily unavailable" (graceful) or doesn't appear at all (paperclip works). NEVER raw "HTTP 401".
3. **Phase 56 check:** every PaperCard has a non-zero `relevance_score` chip. At least 60% of results score ≥ 0.4.
4. Click "high-confidence only (≥ 0.6)" toggle.
5. **Phase 56 check:** result count drops but is NOT zero (the dogfood walk's 0 of 28 case must not reappear).
6. Open the library panel; locate the "GLP-1 obesity" batch (or any batch with > 1 paper).
7. **Phase 61 (B5) check:** copy icon appears next to the batch query. Click it. "Copied" tooltip surfaces for ≥ 1s.
8. Verify clipboard contents via `mcp__claude-in-chrome__javascript_tool('navigator.clipboard.readText()')`.

### Test E2E-2 — Hypothesis state machine (Phase 57)

1. Navigate to `/hypothesis?project=arena-agentic-upgrade&hyp=hyp-20260507-6f1951` (the supported hypothesis from the walk).
2. Confirm status badge reads "SUPPORTED".
3. Click "MARK REFUTED".
4. **Phase 57 check:** badge updates to "REFUTED" without an "Invalid status transition" error toast.
5. Click "MARK SUPPORTED".
6. **Phase 57 check:** badge flips back. Round-trip works.
7. Click "ARCHIVE".
8. Locate an archived hypothesis in History. Click it.
9. Hover over the active-hypothesis area; find an "un-archive" affordance OR mark it "open" via the status menu.
10. **Phase 57 check:** archived → open transition succeeds.

### Test E2E-3 — Hypothesis history × delete (Phase 58)

1. From `/hypothesis`, locate a stale or test hypothesis in the History sidebar.
2. Hover the row.
3. **Phase 58 check:** an × button appears (data-hypothesis-delete sentinel).
4. Click it.
5. Confirm the `window.confirm` dialog (use `mcp__claude-in-chrome__javascript_tool` to auto-accept).
6. **Phase 58 check:** the row disappears from History without a page reload.
7. Reload the page.
8. **Phase 58 check:** the row stays gone (DELETE persisted to disk).

### Test E2E-4 — Claim-form picker batch grouping + show-all (Phase 59)

1. From `/hypothesis`, click "+ NEW".
2. Type a claim (e.g. "test claim for batch grouping").
3. Locate the linked-papers picker.
4. **Phase 59 (B2) check:** papers are grouped under collapsible batch headers (e.g. "patients with bacterial infec... · 10 papers", "GLP-1 obesity · 4 papers"). Default-collapsed.
5. Click a batch header.
6. **Phase 59 (B2) check:** the batch expands to show paper checkboxes. No form submission.
7. Click the "ALL" button INSIDE the picker.
8. **Phase 59 (B3) check:** all checkboxes flip on, but generation does NOT start. The form stays in edit mode.
9. Click "SHOW ALL" if a different paginate button exists; same expectation.

### Test E2E-5 — Propose Title with hypothesis only (Phase 60)

1. Navigate to `/draft?project=arena-agentic-upgrade`.
2. Click "+ NEW MANUSCRIPT".
3. Title: "Test of v2.1 propose-title fix". Pick the supported hypothesis from the walk.
4. Click "CREATE + OPEN".
5. In the new manuscript, click "+ PROPOSE TITLE".
6. **Phase 60 check:** at least 1 candidate is returned (NOT "No candidates returned"). The candidate references the hypothesis topic.
7. **Phase 60 check (negative):** if the route still fails, the parse-debug SSE event is visible in DevTools network tab — exposing the trailing 200 chars of stdout. (Useful diagnostic; expected in normal-case to NOT fire.)

### Test E2E-6 — Section-list density + sources help (Phase 61 B4+C1)

1. From the manuscript opened in E2E-5, look at the section list.
2. **Phase 61 (B4) check:** section labels read "## Abstract", "## Introduction", etc. without truncation. The GENERATE / DRAFT / ⚙ src / ▲▼ controls live on a separate row beneath each label.
3. Click the source-linkage-panel header.
4. **Phase 61 (C1) check:** help text reads "These artifacts feed every section's prompt..." and a `<details>` block expands to per-kind explanations.

### Test E2E-7 — Generate retry clears toast (Phase 61 A4)

1. From the manuscript in E2E-5, click "GENERATE" on the Abstract section.
2. If the first attempt produces a "succeeded-no-artifact" toast, click Retry.
3. **Phase 61 (A4) check:** when the retry succeeds, the failure toast clears BEFORE the success card renders. No stale "Failed" message lingers.
4. **Phase 61 (A4) check:** the editor scrolls to make the freshly-drafted abstract visible.

### Test E2E-8 — Notebook import (regression check for v2.0 Phase 52)

1. From the same manuscript, click "+ .ipynb" in the section-list header.
2. Pick a `.ipynb` file (any small Jupyter notebook).
3. **Phase 52 regression check:** a new `imported-notebook-1` section appears with markdown cells preserved + code cells in fenced blocks. No errors in console.

### Test E2E-9 — Section override modal (regression check for v2.0 Phase 51)

1. From the same manuscript, hover the Abstract section.
2. Click the "⚙ src" button.
3. **Phase 51 regression check:** modal opens with 4 tabs (Papers / Figures / Hypotheses / Datasets). Pick a different paper subset.
4. Click "Save overrides".
5. **Phase 51 regression check:** modal closes. PATCH to /api/draft/[slug]/sections/[section_id] returns 200 and the section's `override_linked_paper_ids` persists (verify via DevTools network tab).

### Test E2E-10 — Repro check + citation graph (regression checks for v2.0 Phases 53+54)

1. From the manuscript, click "View graph".
2. **Phase 53 regression check:** SVG renders with the manuscript hub + leaves coloured by kind.
3. Click "Hide graph".
4. Click "Repro check".
5. **Phase 54 regression check:** inline 6-row report renders with verdict glyphs (✓/!/✗).

---

## 16. Final checklist before tagging v2.1

After commit 7 (Phase 61) lands:

```bash
cd projects/briefs/organon-dashboard
npm test && npm run typecheck && npm run build
python3 tests/stress-suite.py

# Browser E2E walk
# (Run all 10 E2E tests above via mcp__claude-in-chrome__*)

cd /Users/keremdelikoyun/Projects/scientific-os
git tag -a v2.1 -m "Organon Dashboard v2.1 — researcher-walk fix sprint (A1–A5 + B1–B5 + C1)"
```

Surface push question to the researcher — do NOT push automatically.

---

## 17. After v2.1

After all seven phases land + browser E2E passes, the dashboard ships with every issue surfaced in the 2026-05-08 dogfood walk closed. Possible v2.2 candidates (NOT commitments):

- **Embedding-based relevance** (replace IDF in `scoreRelevance`; the interface is stable from Phase 47).
- **Real-time collaboration** (CRDT-based section sync).
- **Plugin system** for custom skill registries.
- **Mobile / tablet UX**.
- **Citation graph traversal** beyond hub-leaf (paper-to-paper edges via shared cite-keys).

Tag `v2.1` at the final commit. **Do NOT push** without explicit researcher authorisation.

---

**End of v2.1 brief.** This pickup is self-contained and TDD-first. Next session: load this file, run the pre-flight, ship the seven phases in order, then run the 10 browser E2E tests.
