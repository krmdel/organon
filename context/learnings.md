# Learnings Journal

> Auto-maintained by Organon skills. Newest entries at the bottom of each section.
> Skills append here after deliverable feedback. Never delete entries.
> Section headings match skill folder names exactly. New skills add their own section when created.
> Skills read only their own section before running. Cross-skill insights go in `general`.

# General
## What works well
- `verify_gate.py` is wired as a **PreToolUse** hook (matcher: Write|Edit|MultiEdit) in settings.json — fires before the write, not after. (Corrects an earlier stale note that called it PostToolUse.)

## What doesn't work well

# Individual Skills

## sci-research-profile

## sci-data-analysis

## sci-hypothesis

## sci-literature-research

## sci-writing

### Anti-phantom citation lessons (April 2026)

**Three real phantom citations found in a live whitepaper during gate development** — each teaches a different failure mode:

1. **Pakter-Levin (2021)** — paper attributed to two authors who did NOT write it. The actual paper was Ono (2021) alone. Lesson: author-list mismatch is the primary phantom signal; title similarity alone is insufficient (the real paper had a related title).

2. **Berthold-Salvagnin (2026)** — fabricated compound surname. arXiv:2601.05943 is actually Berthold, Kamp, Mexi, Pokutta, Pólik (2026). Lesson: compound-surname attributions ("Smith-Jones") that don't match any real author list are a red flag; always verify against the actual author metadata.

3. **Cohn-Triantafillou (2022) DOI** — correct authors, wrong DOI digit (3649 vs 3662). `10.1090/mcom/3649` resolves to an unrelated Gaussian-process paper. Lesson: DOI digit transposition is a real error mode; CrossRef title-check catches it even when author names match.

**What the gate catches vs what a human caught:**
- The Pakter-Levin phantom was caught by a human reading carefully, THEN the gate was built to encode the lesson. The gate did NOT exist when the phantom was written. Frame verification as "codifying a lesson", not "working as designed from day one".

**Dispatcher ordering rationale (arXiv > PubMed > CrossRef):**
- arXiv Atom API: one call, returns title + authors; no key needed; covers physics/math/CS preprints reliably.
- PubMed efetch: one call, returns title + authors + abstract; biomedical journals often absent from CrossRef or return no abstract via CrossRef.
- CrossRef DOI: widest non-biomedical coverage; last resort because it frequently omits abstracts (abstracts are needed for the live-source quote check).

**Live-source quote check is MAJOR not CRITICAL** — abstracts don't contain full-text; the signal is "verify against the PDF", not "definitely fabricated". CRITICAL would create false positives for every paywalled paper.

**NCBI efetch over esummary** — efetch returns title + authors + abstract in one call; esummary would require a second round-trip for the abstract. Always use efetch for the full record.

**Tier 5 thresholds (from empirical calibration):**
- `TITLE_MATCH_THRESHOLD = 0.95` — 0.90 was too loose; the Berthold case scored 0.91 (similar-but-wrong title) and slipped through.
- `FIRST_AUTHOR_MATCH_THRESHOLD = 0.85` — allows for diacritics and LaTeX encoding variants.
- `COAUTHOR_JACCARD_MIN = 0.70` — 0.70 handles truncated lists ("et al.") gracefully; "and others" on either side skips the Jaccard check entirely.

**Tier A hardening (A1–A10, April 2026) — key lessons:**
- A1: "no identifier = CRITICAL" is the right default. Legacy bibs always have hidden no-ID entries; run an inventory before shipping A1 so you don't surprise yourself with 20+ new CRITICALs in CI.
- A2/historical: pre-1950 entries are a real class — `historical = {approved}` opt-in (not silent bypass) keeps the gate load-bearing while not failing Hadamard/Thomson refs.
- A3 URL livecheck: HEAD→GET fallback + 405 handling is essential; many academic sites reject HEAD. Title fuzzy match (SequenceMatcher ratio) at 0.55 floor catches most domain-mismatch cases.
- A5 inline attribution: `<!-- no-cite -->` suppression is important for pure-expertise tutorials; without it, every textbook reference in a blog post triggers MAJOR.
- A8 dual-id conflict: store `dual_id_conflict` + `dual_id_detail` in the verify_citation return dict, not as a side effect — callers need it to distinguish "conflict" from "one ID missing."
- A9 PubMed retraction: check BOTH `PublicationType` list AND `CommentsCorrections[@RefType="RetractionIn"]` — some retractions only appear in one place.
- A10 grammar: false-positive rate for `(Smith, 2023)` is high in method sections that describe statistical tests — need code-fence exclusion (already implemented).

**Tier B receipt forensics — key lessons:**
- B3 env gate (`SCI_OS_VERIFY_RECEIPTS=1`) is essential: without it, every `check-research` call hits CrossRef/arXiv/NCBI, making local dev unusably slow. CI auto-enables via `CI=true`.
- receipt-vs-bib title threshold (0.85) is intentionally lower than the live-API threshold (0.90) — the researcher may have hand-paraphrased the title in the receipt; only full disagreement is CRITICAL.
- B5 (`check_receipt_confidence`) belongs at gate-draft time, not check-research time — the sidecar doesn't exist yet at check-research; wiring B5 into cmd_gate_draft is the right hook.

**Tier C claim-quote alignment — key lessons:**
- Jaccard=0.30 is deliberately loose to handle legitimate paraphrasing. Start MAJOR; promote to CRITICAL after calibrating against 50+ real manuscripts — pre-calibration CRITICAL would produce too many false positives.
- C4 coverage gaps are advisory NOTE, not a blocker — the writer may legitimately have gaps if the claim is expert knowledge; forcing a block here would cause more harm than good.
- "Prefer no citation" (Commandment 6 in sci-writer.md) is the right framing: writers should drop/hedge rather than force a weak citation through.

**Tier E publish gates — key lessons:**
- Ledger on EVERY outcome (refused, bypassed, clean) — full audit trail catches both overrides and clean passes; useful for compliance review.
- `verify_ops` imported dynamically in substack_ops with graceful degradation: warns but allows push if dep is missing. Keeps the publish path unblocked on fresh installs.
- E2 footer (verification status in Substack body) is still deferred; E2 needs injection before ProseMirror conversion.
- E3 Drive bundle is shipped (`gdrive_ops stage-bundle <md>`) — stages `.md` + adjacent `*.bib`, `*.citations.json`, `*-audit.md` into `manuscripts/{stem}_audit/` on Drive. Not auto-wired into Substack push by design; the CLAUDE.md Drive Push Gate prompts separately so the user can choose `stage-bundle` vs plain `stage`.

**Tier H bib-audit cron — key lessons:**
- `bib_sweep.py` treats all entries as "used" (not just cited keys) — appropriate for a CI gate that enforces correctness on the whole file, even unreferenced entries.
- `citation_verify.py` CrossRef bugfix: `work.get("container-title", [""])[0]` fails when CrossRef returns `[]` (not missing key). Fix: `(work.get("container-title") or [""])[0]`.
- Bib-audit cron as a LaunchAgent job: set `active: "false"` until the user explicitly enables it; shipping enabled would run on a stale bib and generate noise.

**LaTeX brace normalization for surnames (April 2026 bib fix-pass):**
- `\`i` and `\`j` (grave-accent dotless i/j) in LaTeX → were leaking into surname comparisons as a backtick. Fix: add `` ` `` and `~^` to `_LATEX_BRACE_RE` AND add a `_LATEX_LETTER_SUB` pre-pass that replaces `\i`→`i`, `\j`→`j` before stripping, so `Dess{\i}` → `Dessì` → `dessi` (not `dess\``).
- Nested-brace parser truncation: `{Dess{\\i}}` in a BibTeX string truncates at the inner brace in some parsers. Use `eprint = {2302.04761}` (separate field) rather than encoding special characters in compound fields to avoid parser truncation.

**Test suite architecture (April 2026):**
- 183 offline tests across 8 test files — all pass with `-m "not network"`. Network tests excluded from CI.
- Test naming: `test_tier_a_hardening.py` / `test_tier_c_prefer_no_cite.py` / etc. — tier labels match PLAN-V2.md sprint tiers, NOT the internal verify_ops phase letters (A–G). Avoid confusion.
- `conftest.py` registers `network` marker so CI doesn't warn; `@pytest.mark.network` marks any test that hits arXiv/CrossRef/NCBI.
- Two-layer test structure: offline unit tests (mock network, fast), network integration tests (live APIs, run manually or in nightly CI).

**Phase 8 Trust Floor (2026-04-26) — five concrete bypass vectors closed:**

After Phase 7 shipped, a code-level audit found five concrete seams that turned the framework's "trustworthy-with-caveats" verdict into "not trustworthy enough" for the user's stated rule (rather no citation than a wrong one). All five closed in one session, ~7h, 24 new offline tests on top of 259 baseline → 283 green:

1. **`unverifiable={approved}` reason+date hardening (`_unverifiable_status` in verify_ops.py).** Bare `unverifiable={approved}` was a free retroactive rubber-stamp. Phase 8 requires `unverifiable_reason` (≥30 chars, not in blocklist of generic templates) AND `unverifiable_date` (ISO YYYY-MM-DD). Bare-tag entries surface "Bib Integrity (A1 — unverifiable incomplete)" CRITICAL. Migration: backfill any existing `unverifiable={approved}` entries with reason+date before next CI run.

2. **Network ConnectionError → CRITICAL fail-closed (verify_ops.py:check_bib_integrity, check_inline_links).** A flaky CrossRef/arXiv/PubMed lookup used to emit MAJOR; since `blocked = critical > 0`, that was a silent pass. Phase 8: ConnectionError → CRITICAL ("network fail-closed"). ValueError (genuinely-missing identifier) stays MAJOR. The save is refused, not delayed — re-run when network returns.

3. **ImportError fail-closed in publish gates (substack_ops.py, export-md.py).** A broken venv used to print WARNING + pass, silently disabling the citation gate on the publish path. Phase 8: refuse the publish/export unless `SCI_OS_ALLOW_UNGATED=1` is set, which logs `outcome: "ungated_bypass"` to the ledger so the audit trail captures the override.

4. **`<!-- no-cite -->` scope tighten + density NOTE (verify_ops.py:check_inline_attributions).** The annotation used to match anywhere in the file and accept any reason text — one annotation buried in the body suppressed A5 for the whole document. Phase 8: must appear within first 20 lines or YAML/HTML frontmatter; reason must be ≥30 chars and not in blocklist. Even when valid, an info-level NOTE counts unanchored factual-claim patterns (percentages, "study found", n=…, p<…, author-year prose) so the writer sees what slipped through.

5. **Scope-mismatch escalation (verify_ops.py:SCOPE_ESCALATIONS, check_scope_escalation).** Hedging-escalation pairs only covered verb-strength shifts ("suggests"→"proves"). Phase 8 adds 25+ scope pairs: animal model→human, in vitro→in vivo, pilot→definitive, observational→causal, single cohort→universal, etc. Fires when the source pattern is in the quote AND the draft pattern is in the manuscript sentence AND the writer dropped the narrow qualifier. MAJOR severity. Suppression logic: if either the quote also has the broader pattern OR the manuscript also retains the narrow qualifier, no finding.

**Audit summary key:** the framework's reliability claim is now "fail-closed on network outages, on ImportError, on retroactive rubber-stamp; surfaces overclaiming where the source-vs-draft scope diverges; ledger-logs every override." This is closer to the user's actual rule than Phase 7 was. Remaining nice-to-haves (NLI contradiction check, ledger HMAC, batch approval counter) deferred — they don't close a fresh-found bypass.

**Phase 7 Trust Floor (April 2026) — summary of what is now programmatically enforced:**
The user's stated rule — "prefer no citation over a false one; every cited statement must direct-link to the original passage" — is now enforced at every publication boundary:
- **Receipt forensics (Tier B):** researcher receipts are cross-referenced against live bib and live APIs; fabricated receipts block `check-research`.
- **Claim-quote alignment (Tier C):** every `[@Key]` sentence must share ≥ 0.30 token Jaccard with the sidecar quote. Writer Commandment 6: drop or hedge rather than force a weak citation.
- **Publish gates (Tier E):** Substack push, Substack edit, and `export-md.py` all gate on CRITICAL before touching the network. Bypass (`--no-verify` / `--force`) is logged to a ledger — full audit trail.
- **Drive audit bundle (Tier E3):** `gdrive_ops stage-bundle` stages the full audit artefact set alongside the manuscript so the Drive copy is self-contained.
- **Weekly bib audit (Tier H):** cron + CI sweep catch drift between sessions.
- **Cross-bib contamination (Tier G):** `check_cross_bib_contamination` + `check_quote_attributable_to_one_source` — MAJOR when a sidecar quote for [@KeyA] verbatim-matches an upstream seed for [@KeyB]. Guard: only fires when quote IS in own seed (Tier 4 owns the missing-seed case; no double-fire). 23 offline tests, all green.
- **Remaining gaps:** Tier D (full-text claim verification via Unpaywall/arXiv PDF/PMC OA), Tier F (per-claim `#:~:text=` deep links), and Tier E2 (verification footer in Substack body) are not yet shipped.

### Phase 9 — Trust Floor Closure (April 2026)

After Phase 8 closed five concrete bypasses, a follow-up audit surfaced eight residual code-level gaps + a fixture regression. Phase 9 closed the ones that mattered and locked the contract via `CLOSURE.md` (repo root). The five epistemic limits (NLI, paywalled full-text, ledger HMAC, reason semantic quality, author particle disambiguation) are documented as the boundary — they will not be patched.

**Audit-driven discovery process:** the Phase 9 work pattern — spawn a code-level audit agent, classify findings as bypasses vs limits, ship the bypasses + document the limits — is repeatable. Each future audit should produce: (a) a list of mechanical gaps that get fixed (each pinned by a regression test), (b) any new epistemic limit candidates that need to be discussed before locking. The contract grows; the limits don't.

**Concrete Phase 9 fixes shipped:**
1. **B7** — `check_research_receipts` now emits CRITICAL when `## Verification receipts` has raw `| N |` data rows but `parse_receipts_table` can't extract structured rows (column-keyword mismatch). Stops silent receipt-forensics no-ops.
2. **DP3** — Substack `_safe_md5` helper; all five bypass `_write_ledger` calls (ungated_bypass / push --no-verify / push refused / edit --no-verify / edit refused) now log `md5` so a forensic audit can correlate any ledger row to manuscript bytes.
3. **WG2** — `auditor_pipeline._BROAD_MARKER_RE` replaces the loose `"[@" in text` substring with verify_ops's regex. Gate precondition and verifier detection agree end-to-end.
4. **B1 NotebookEdit** — added to PreToolUse matcher. `verify_gate.py:_is_watched_notebook` returns True for `.ipynb` under primary watched prefixes or with a sibling `.bib`; the hook refuses NotebookEdit on watched notebooks because rendering arbitrary cell-source insertion into markdown is out of scope.
5. **WG3 fixture regression** — `bib_sweep.find_bib_files` now excludes any path containing both `tests` and `fixtures` parts; the cron + CI sweep no longer fails on intentionally-malformed test inputs.

**What deliberately wasn't shipped (and why):**
- WG1 multi-quote-seeds — `_find_sibling_quotes` returning the first match was the design (single-section workspace shape). Multi-section seeds are rare enough that bumping it to "all quotes.json + accept multiple --quotes" would inflate verify_ops's CLI surface for a corner case. Defer until a real multi-seed workspace surfaces.
- Bash redirect / heredoc gate — the threat is heredoc-into-watched-path bypassing the hook. Detection is brittle (regex over Bash text), high false-positive risk, and the cron + bib-sweep + auditor pipeline catch downstream side effects. Documented as epistemic limit territory: Bash is explicit user-override territory, not gate territory.

**What writing CLOSURE.md proved:** anchoring the contract to a written document moves the conversation from "is fabrication blocked?" (an opinion) to "is row 23 of the contract table still passing its test?" (mechanical). Every contract row maps to a regression. New audits append rows; the five limits don't change. The recurring "is the framework reliable?" question now has a stable answer.

### A6 false-positive fix — `(Author, Year)` link-text exemption (April 2026)

The Phase 8/9 inline-link check (`check_inline_links` in verify_ops.py) compared markdown link-text to the live paper title and emitted CRITICAL on similarity < 0.60. Substack-style drafts use `[Wales and Ulker, 2006](https://doi.org/...)` — a cite-key form that *will always* fail title similarity, producing false-positive CRITICALs that blocked legitimate saves of the Organon whitepaper. The protective check that actually catches DOI digit-transposition (e.g. the Cohn-Triantafillou 3649 vs 3662 incident) is `check_bib_integrity`, which compares *bib title* to *live title* — that is preserved unchanged. The fix exempts link text matching `^[^,\d]{1,80},\s*\d{4}[a-z]?$` AND ≤ 8 words from the title-similarity check at both DOI and publisher-URL sites; everything else (DOI/arXiv resolution, retraction check, network fail-closed, bib integrity) still runs. Why: legitimate cite-format link text is structurally distinct from title-form link text; a single-line regex exemption removes 100% of false positives without weakening the protection that catches real DOI errors. How to apply: when a future audit surfaces a similar "the gate flagged something the user clearly didn't break" case, ask first whether the gate's check is *meaningful for that input shape* before adding bypass envs or no-cite escapes.

## sci-communication

### User-style writing preferences for Organon-promotional pieces (April 2026)

Lessons from the user's review of `whitepaper-substack-v2.md` (the Organon Einstein Arena piece). These are voice + framing rules for any piece *about Organon* by *this user*. Apply on first draft, do not wait for review.

- **American spelling, every time.** "optimization" not "optimisation"; "specialization" not "specialisation"; "organize" not "organise"; "synthesize" not "synthesise"; "behavior" not "behaviour"; "center" not "centre"; "favor" not "favour". Why: explicit user preference. How to apply: spell-check pass before save; this rule overrides any British-trained writing habit.

- **Title is a punch, not a label.** The user prefers a title that *makes the claim* over one that *describes the topic*. "An AI built for X just claimed #1 on a problem that stumped Y" beats "Organon: An Operating System for Z". Why: punchier titles drive Substack click-through; user explicitly endorsed this framing. How to apply: lead with the surprising verifiable claim, defer the system-name to subtitle or first paragraph.

- **Submission status is a single source of truth.** When the user has submission decisions pending, treat ALL stored-best candidates as "submitted and accepted, ranked #1" in the public-facing draft (the user submits offline before publishing). Why: avoids the awkward "stored-best vs live-#1" cross-referencing that confuses readers. How to apply: when status is ambiguous, ask once, then write the draft assuming public-leaderboard outcome and add a single "as observed at the time of writing on the public leaderboard" caveat near the top.

- **Internal file paths are NOT user-facing.** `projects/einstein-arena-X/`, `baseline_opus/`, and other repo-internal directories never appear in the published article. Public-repo paths (`github.com/krmdel/organon`), shared skills (`.claude/skills/...`), and framework files (`CLAUDE.md`, `context/learnings.md`) are fine because they're part of the open-source architecture story. Why: paths leak local layout, age fast, and don't help the reader. How to apply: grep for `projects/` and any non-public directory before save and either remove or replace with a generic phrase like "a completed artifact in the campaign folder".

- **Phantom-citation framing has a specific arc the user wants told.** Mistake → human caught it → system did not have the gate → gate was built from the lesson → discipline now runs by default → here is a *new* phantom this revision caught with the new gate. The "new phantom caught" beat is load-bearing because it shows the gate is real, not aspirational. Honest caveat: the gate is necessary not sufficient; the human-in-the-loop is still load-bearing. Why: the user wants self-evolution to be a verifiable claim, not a marketing line. How to apply: never frame the gate as "always worked"; always show the failure → lesson → mechanism arc with a current-day verification.

- **Human-in-the-loop is a feature, not a deficiency.** Frame autonomy not as "more is better" but as "fusion of human judgment with agentic orchestration yields the higher performance of both, and arguably the more durable shape of agentic scientific discovery." Why: the user explicitly asked for this framing in Claim 5 / §7.2. How to apply: when comparing to AI-Scientist or AlphaEvolve, make the trade explicit (autonomy vs. catchability) rather than apologetic.

- **Citation discipline at first citation.** Every inline `[Author, Year](DOI/arXiv)` link must have a backing entry in the bib file. The Gao-et-al ToolUniverse phantom — cited inline in v2 with no bib entry — was exactly the kind of mistake the gate is supposed to catch. How to apply: before any save, grep the article for `[`...`](https://`...`)` patterns and confirm each link's author/year combo exists in the bib; if missing, add the entry from the live arXiv/DOI metadata.

- **Don't cite specific dates that age fast.** "as of 2026-04-25" anywhere in the body becomes wrong on 2026-04-26. Use "at the time of writing" or "as observed on the public leaderboard at the time of writing" instead. Why: user feedback on time-anchored references and bibliographic-style entries. How to apply: grep for explicit dates in body prose (figure captions and bibliographic entries can keep them).

- **Day-to-day science is the main act, math is the proof.** The Einstein Arena results are a *stress test* for the daily-research loop the system actually serves: literature, data, hypothesis, writing, figures, presentations, pitch decks. When drafting Organon-positioning content, lead with the everyday workflow, then use the arena as evidence the architecture holds up beyond its design domain. Why: user explicitly noted that v2 over-indexed on math and under-told the everyday story. How to apply: every Organon piece should have at least one paragraph (preferably in §1 or §3) that lists the daily-science skills concretely.

## sci-tools

## sci-research-mgmt

## sci-trending-research

## sci-council

## sci-optimization

## sci-optimization-recipes

## viz-presentation

## viz-nano-banana

## viz-diagram-code

## viz-excalidraw-diagram

## meta-skill-creator

## meta-wrap-up

## ops-cron

## ops-ulp-polish

## ops-parallel-tempering-sa

## tool-firecrawl-scraper

## tool-gdrive

## tool-humanizer

## tool-obsidian

## tool-youtube

## tool-paperclip

## tool-substack

## tool-einstein-arena

## tool-arena-runner

## tool-arena-attack-problem
