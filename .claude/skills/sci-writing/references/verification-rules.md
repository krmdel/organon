# Verification Rules

This document defines the thresholds, patterns, and classifications used by `scripts/verify_ops.py`. Update this file when adding new rules — it's the source of truth for what gets auto-fixed vs flagged.

## Where the gate fires

Fabrication guardrails v3 runs the gate in **two places**:

1. **PreToolUse hook** (`.claude/hooks_info/verify_gate.py`). Fires *before* `Write` / `Edit` / `MultiEdit` on any file under `projects/sci-writing/**` or `projects/sci-communication/**`. The hook simulates the proposed post-write content in a sibling tempfile, runs `verify_ops.py` on it, and returns exit 2 to **block** the tool call on any CRITICAL finding or contract refusal. The real file on disk is never touched. Fail-closed: any simulation error, subprocess crash, timeout, or missing dependency blocks the save.
2. **Pipeline gates** (`paper_pipeline.py gate-draft`, `auditor_pipeline.py gate`, `auditor_pipeline.py post-humanize`). These invoke `verify_ops.py` directly with a `--quotes` flag pointing at the upstream `quotes.json` seed so the provenance check runs.

Both paths share the same `verify_ops.py` entrypoint and the same rules — they differ only in what blocks what.

## Hard Contract

The gate **refuses to run** (exit code 3, `VerificationError`) if any of these are true:

- `--bib` not provided
- Bib file does not exist
- Manuscript contains `[@Key]` markers but the bib parses to zero entries
- Upstream `quotes.json` is referenced (`--quotes`) but is missing or not valid JSON

This is non-negotiable. There is no flag to bypass it. If the user has no bib file, they must run `sci-literature-research` first — fabricated citations cannot be audited, so the skill will not produce unaudited content.

## Auto-Fix vs Flag

| Category | Action | Reason |
|----------|--------|--------|
| Citation marker syntax (`@key]`, spaces in brackets) | **Auto-fix** | Mechanical, no semantic risk |
| Unmatched [@Key] (no .bib entry) | **Flag (major)** | Could be typo OR missing reference — needs human judgment |
| Used bib entry has no DOI | **Flag (major)** | Un-verifiable = fabrication risk |
| DOI 404 at CrossRef | **Flag (major)** | Could be typo or unindexed preprint |
| **CrossRef ConnectionError** | **Flag (major)** | Fail-closed: unreachable API cannot silently pass a possibly-retracted citation |
| Retracted DOI | **Flag (critical)** | Must be removed — blocks save |
| **CrossRef title mismatch** (ratio < 0.90) | **Flag (critical)** | Char-level + token-set Jaccard, min of the two. Near-match titles can no longer launder through |
| Gray-lit / preprint entry (`@unpublished`, `@techreport`, `@misc`, arXiv `eprint`) | **Flag (major)** | Preprints flagged by default; opt in with `gray_lit = {approved}` |
| Citation density below threshold | **Flag (minor)** | May be intentional (transition paragraph) |
| Figure reference gaps | **Flag (minor)** | Could be intentional reordering |
| Undefined abbreviations | **Flag (minor)** | Some are domain-standard and don't need definition |
| Hedging escalation | **Flag (major)** | Requires reading both source and draft |
| P-value without test statistic | **Flag (major)** | Mechanical detection but human must add the missing stats |
| "Significant" without p-value | **Flag (minor)** | Could be intentional plain-English use |
| Missing citations sidecar when manuscript has `[@Key]` | **Flag (critical)** | Quote-or-cite guarantee broken |
| Sidecar claim missing quote / short quote (< 80 chars) | **Flag (critical/major)** | Token stuffing or no provenance |
| Sidecar `source_confidence == "abstract"` | **Flag (major)** | Abstracts are press-release prose, not verbatim paper text |
| Sidecar `source_confidence == "title"` | **Flag (critical)** | Title fallback is dead — legacy sidecar must be rebuilt |
| Sidecar quote not found in `--source` (when provided) | **Flag (critical)** | Fabricated quote (NFKC + smart-quote/em-dash fold, punctuation preserved) |
| Sidecar quote does not trace to any candidate in upstream `quotes.json` | **Flag (critical)** | Writer invented beyond the researcher's seed |
| Used key missing from upstream `quotes.json` | **Flag (critical)** | Writer cited a paper the researcher never surfaced |
| Paperclip source_anchor not matching `citations.gxl.ai/papers/<id>#L<n>` | **Flag (critical)** | Corrupt anchor cannot be resolved |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All findings non-critical. Safe to save. |
| `2` | Blocked — at least one CRITICAL finding. Do not save. |
| `3` | Refused — contract failure (no bib, empty bib, invalid sidecar JSON). |

## Citations Sidecar Schema

Location: `{manuscript_path}.citations.json` (same directory, same stem, `.citations.json` suffix).

```json
{
  "version": 1,
  "claims": [
    {
      "key": "Smith2023",
      "quote": "verbatim passage >= 80 chars, preserving punctuation",
      "source_anchor": "10.1038/s41586-024-00001-0",
      "source_type": "doi",
      "source_confidence": "full-text"
    }
  ]
}
```

- `key` — matches a `[@Key]` marker in the manuscript AND an entry in the `.bib`.
- `quote` — verbatim passage from the source, **minimum 80 characters**. NFKC-normalized with smart-quote/em-dash/NBSP folded to ASCII; punctuation is preserved during comparison. A quote that only matches after stripping punctuation no longer passes.
- `source_anchor` — DOI, `https://citations.gxl.ai/papers/<doc_id>#L<n>[-L<m>][,L<n>…]`, or resolvable URL.
- `source_type` — `doi` | `paperclip` | `url`. Paperclip entries are additionally validated against the anchor regex.
- `source_confidence` — `full-text` | `abstract` | ~~`title`~~ (retired). Tracks which provenance tier the upstream researcher recorded. Full-text passes; `abstract` is MAJOR; `title` is CRITICAL (the upstream builder no longer emits it — its presence means a legacy sidecar that must be rebuilt).

Missing sidecar with any `[@Key]` marker → CRITICAL (blocks save). Sidecar is written incrementally during drafting, not after.

### Upstream provenance trace

When `--quotes <path>` is passed to `verify_ops.py`, every draft sidecar claim is additionally required to **substring-match a candidate in the upstream `quotes.json`** for the same key. This catches writer invention that happens to quote text the writer pulled from memory rather than from a pre-generated researcher seed. The paper pipeline and auditor pipeline both auto-discover `{slug}.quotes.json` next to the draft and pass it automatically — you rarely need to think about this flag directly.

## Title-Match Threshold

Normalized ratio on titles that preserves whitespace and punctuation (NFKC-folded, smart-quote / em-dash / NBSP folded to ASCII, lowercased). The score returned is `min(char_level_SequenceMatcher, token_set_Jaccard)` — a failure on either dimension drags the score below the threshold, so "The Role of A in B" vs "The Role of A in B and C" no longer laundered through.

Threshold: `TITLE_MATCH_THRESHOLD = 0.95`. Raised from 0.90 in Phase 2 (Tier 5). Edit `verify_ops.py` to retune if false positives appear, but loosening it will re-open the cite-laundering path this version deliberately closed.

## Author Validation — Tier 5 (Bib Integrity)

Added in Phase 2. Fires after a title match passes the threshold. Criterion name in reports: **"Bib Integrity (Tier 5)"**.

Two checks run sequentially:

1. **First-author match** — normalized surnames compared with `SequenceMatcher`. Threshold: `FIRST_AUTHOR_MATCH_THRESHOLD = 0.85`. Diacritics stripped, LaTeX braces (`{\'e}`) resolved before comparison. "and others" / "et al." truncation in either list is treated as a pass on the Jaccard check.

2. **Co-author Jaccard** — set of all bib surnames vs set of all live surnames. Threshold: `COAUTHOR_JACCARD_MIN = 0.70`. Only runs when enough authors are present on both sides and neither list is truncated.

Failure on either check → CRITICAL. When both title and authors are wrong, only the title finding fires (early-continue) — still CRITICAL.

**Normalization rules applied to both sides:**
- `_strip_diacritics` — Unicode NFD decompose, strip combining marks
- LaTeX brace folding — `{AI}` protected-case sequences extracted
- LaTeX accent commands — `{\'e}` → `e`, `{\o}` → `o`, etc.
- Name particles — "van", "de", "von" are included in the surname token

## Identifier Dispatch — arXiv > PubMed > CrossRef

`check_bib_integrity` routes each bib entry to a verification backend based on available identifiers. Order of preference:

| Priority | Identifier | Backend | Why |
|----------|-----------|---------|-----|
| 1 | `eprint` (arXiv) | `verify_arxiv` via Atom API | Returns author list + abstract in one call; direct DOI-free lookup |
| 2 | `pmid` (PubMed ID) | `verify_pubmed` via NCBI efetch | Biomedical journals often absent from CrossRef; efetch returns title + authors + abstract in one call |
| 3 | `doi` | `verify_doi` via CrossRef REST | Widest coverage for non-biomedical journals |

If none of the three identifiers is present, the entry is flagged MAJOR ("No DOI, arXiv id, or PMID"). This replaces the old "No DOI" rule.

Cache key: `(doi.lower(), eprint.lower(), pmid.lower())` — deduplicates across identifiers for the same paper.

## PMID Support (Phase 4a)

Bib entries can now carry a `pmid` field:

```bibtex
@article{Ono2021,
  author  = {Ono, Y. and ...},
  title   = {...},
  year    = {2021},
  journal = {Physical Review B},
  pmid    = {34237939}
}
```

- `normalize_pmid` strips whitespace and leading zeros; accepts plain integers.
- `verify_pubmed` calls NCBI efetch XML (`db=pubmed&rettype=abstract&retmode=xml`). Reads `NCBI_API_KEY` from env for higher rate limits (10 req/s vs 3 req/s). Absent key → unauthenticated call (rate-limited but functional).
- Returned record: `{title, authors, abstract, source: "pubmed", pmid}`. Same shape as `verify_arxiv` and `verify_doi`.
- PubMed is placed before CrossRef in the dispatcher because PubMed reliably returns abstracts for biomedical journals that CrossRef omits.

---

## Tier A Hardening Rules (A1–A10)

Sprint labels from `PLAN-V2.md` that map onto `verify_ops.py` enhancements added in April 2026.
Distinct from the internal phase letters A–G in the verify_ops docstring.

| ID | Rule | Severity | Opt-out |
|----|------|----------|---------|
| A1 | Bib entry has no doi, eprint, or pmid | **CRITICAL** | `unverifiable = {approved}` → MAJOR; `historical = {approved}` on pre-1950 entry → MAJOR |
| A2 | Pre-1950 entry with `historical = {approved}` | **MAJOR** | No further opt-out |
| A3 | URL-only `@misc` entry: broken URL (4xx/5xx) | **CRITICAL** | — |
| A3 | URL-only `@misc` entry: title match ratio < 0.55 | **CRITICAL** | — |
| A3 | URL-only `@misc` entry: accessible + title match | **MAJOR** | — |
| A4 | `verify_gate.py` extends sibling-bib watch to any `.md` with a `*.bib` next to it | Gate behaviour | — |
| A5 | Inline `Author et al. (Year)` in pure-expertise mode (no `[@Key]` markers) | **MAJOR** | `<!-- no-cite: <reason> -->` annotation at top of file suppresses |
| A6 | Inline `[text](https://doi.org/...)` link: retracted | **CRITICAL** | — |
| A6 | Inline `[text](https://doi.org/...)` link: title mismatch | **CRITICAL** | — |
| A7 | Live backend returns empty author list (corporate/collection) | **MAJOR** | — |
| A8 | Both `eprint` and `doi` present and resolve to different titles | **CRITICAL** | — |
| A9 | PubMed `PublicationType` = "Retracted Publication" or CommentsCorrectionsList `RetractionIn` | **CRITICAL** | — |
| A10 | LaTeX `\cite{key}` grammar in a markdown manuscript | **MAJOR** | — |
| A10 | Parenthetical author-year `(Smith et al., 2023)` grammar | **MAJOR** | — |
| A10 | Numeric `[1]` / `[2,3]` reference grammar | **MAJOR** | — |

**A1 opt-out fields** (add to the `.bib` entry):
```bibtex
unverifiable = {approved}   % item cannot be fetched by any API; human-verified
historical   = {approved}   % pre-1950 reference; no digital ID exists
```
Both downgrade from CRITICAL → MAJOR. `historical = {approved}` only applies if `year < 1950`.

**A5 suppression** — place at the very top of the manuscript:
```markdown
<!-- no-cite: tutorial with no primary sources, pure expertise -->
```

**A8 cache key** — `(doi.lower(), eprint.lower(), pmid.lower())`; both IDs are verified and compared.

---

## Tier B: Receipt Forensics (`researcher_ops.py`)

Validates `## Verification receipts` in `research.md`. Implemented in `scripts/researcher_ops.py`;
wired into `paper_pipeline.py cmd_check_research`.

| ID | Rule | Severity | Threshold |
|----|------|----------|-----------|
| B1 | `parse_receipts_table` extracts structured rows from `research.md` | — | — |
| B2 | Receipt title vs bib title mismatch | **CRITICAL** | `TITLE_CROSS_THRESHOLD = 0.85` |
| B2 | Receipt first-author vs bib first-author mismatch | **CRITICAL** | `AUTHOR_THRESHOLD = 0.80` |
| B2 | Receipt identifier not found in any bib entry | **MAJOR** | — |
| B3 | Re-call live API; receipt title vs live title mismatch | **CRITICAL** | `TITLE_API_THRESHOLD = 0.90` |
| B3 | Re-call live API; receipt first-author vs live mismatch | **CRITICAL** | `AUTHOR_THRESHOLD = 0.80` |
| B5 | Sidecar `source_confidence` > seed `confidence` level | **MAJOR** | hierarchy: full-text > partial > abstract > title |

**B3 activation** — network-call only when env flag is set:
```
SCI_OS_VERIFY_RECEIPTS=1   # or CI=true
```
Local dev skips B3 by default to avoid network cost.

**Missing receipts section** — when `research.md` has no `## Verification receipts` heading
the gate returns CRITICAL with criterion `"Researcher Integrity (Phase 3)"`.

**Confidence hierarchy** (B5):
```
full-text > partial > abstract > title (retired)
```
A sidecar claiming `full-text` when the upstream seed was `abstract` → MAJOR.

---

## Tier C: Claim-Quote Alignment + Coverage Gaps

| ID | Rule | Severity | Threshold |
|----|------|----------|-----------|
| C3 | Token Jaccard between manuscript sentence and sidecar quote < 0.30 | **MAJOR** | `_CLAIM_QUOTE_JACCARD_MIN = 0.30` |
| C4 | Coverage gaps ("Unresolved / gaps:" in `## Coverage status`) | NOTE (advisory) | — |

**C3** fires on every sentence containing `[@Key]` against that key's sidecar quote. Skipped when:
- `quotes_path` is None or missing (already flagged upstream)
- The sidecar is absent (already flagged by `check_quote_sidecar`)
- Quote is shorter than `MIN_QUOTE_CHARS = 80` chars

**C4** parses `research.md` for gaps listed under `## Coverage status → Unresolved / gaps:`.
These surface in `cmd_check_research` as advisory notes but do not block the pipeline.

The "prefer no citation" rule (Commandment 6 in `sci-writer.md`): a writer must prefer dropping
or hedging a claim over using a citation whose quote doesn't support that specific claim.

---

## Tier D: Full-Text Claim Verification

**Files:** `repro/fulltext_fetch.py` + `verify_ops.py` (`check_quotes_against_live_source`)

**Purpose:** escalate abstract-level MAJOR findings to CRITICAL when an open-access full text is available and the sidecar quote is demonstrably absent.

### How it fires

Tier D runs inside `check_quotes_against_live_source`, after the paperclip anchor check and before the abstract fallback. It is gated on `_FULLTEXT_FETCH_AVAILABLE` — if `pdfminer.six` (or `pdfminer3`) is missing the check is silently skipped and the run falls back to the existing abstract-level check.

| Step | What happens |
|------|-------------|
| 1 | `_fetch_full_text(doi, arxiv_id, pmid)` tries to obtain an OA PDF |
| 2 | If full text fetched AND `_quote_in_full_text(quote, full_text)` → **pass** |
| 3 | If full text fetched AND quote absent → **CRITICAL "Full-Text Quote (Tier D)"** |
| 4 | If no OA path available → falls through to abstract check → **MAJOR "Live-Source Quote"** |

Tier D and the abstract check are mutually exclusive: once full text has been checked the loop `continue`s, avoiding double-firing.

### Fetch cascade (`fetch_open_access_pdf`)

```
1. arXiv PDF   — https://arxiv.org/pdf/{arxiv_id}
2. Unpaywall   — GET https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}
                  → best_oa_location.url_for_pdf
3. PMC OA      — https://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}/pdf/
```

Cache: `~/.cache/scientific-os/fulltext/{url_hash}.txt` — 30-day TTL. On cache miss the PDF is fetched, decoded with `pdfminer.six`, ligature-normalized (ﬁ → fi, ﬀ → ff, etc.), and cached as plain text.

**`UNPAYWALL_EMAIL` is required for the Unpaywall path** (polite-pool identifier). If absent the cascade skips step 2. Any valid email works — it is passed as the `email=` query parameter.

### Quote match logic (`quote_in_full_text`)

1. NFKC + lower-case + whitespace-collapse both the quote and the full text.
2. Exact normalized substring → pass.
3. Fallback: match the first 60 % of the normalized quote (handles page-boundary splits). Still CRITICAL if the head matches but the tail does not.

### Finding format

```
criterion: "Full-Text Quote (Tier D)"
severity:  "critical"
section:   "Citations"
finding:   "Sidecar quote for '[@Key]' was NOT found in the fetched
            open-access full text for '{doi|arxiv|pmid}'. Full-text
            mismatch is authoritative: the paper does not contain this
            passage, or the quoted text has been substantially
            paraphrased beyond recognition."
suggestion: "Open the PDF and locate the actual passage. Either update
             the sidecar quote to match the verbatim text, or remove
             the citation if the paper does not support the claim."
```

When Tier D fires, the abstract fallback is skipped (no double-fire). When no OA path is available, the MAJOR "Live-Source Quote" finding carries the hint:

```
"(No open-access full text was available to perform a stronger CRITICAL
check — see Tier D in verification-rules.md.)"
"Set UNPAYWALL_EMAIL in .env to enable automatic full-text retrieval."
```

### Dependencies

| Package | Role | Fallback |
|---------|------|---------|
| `pdfminer.six` or `pdfminer3` | PDF text extraction | Gate skips Tier D; abstract check runs instead |
| `requests` | HTTP fetches | Already required by verify_ops |
| `UNPAYWALL_EMAIL` in `.env` | Unpaywall polite-pool identifier | Unpaywall step skipped; arXiv + PMC paths still work |

Install: `pip install pdfminer.six requests`

---

## Tier E: Publish Gates

Verification gate wired into external publication paths.

### E1 — Substack pre-publish gate (`substack_ops.py`)

`cmd_push` and `cmd_edit` call `_run_verify_gate(md_path)` before any network call:

| Outcome | Action |
|---------|--------|
| No `[@Key]` markers in draft | Gate returns `(False, "")` — passes immediately |
| `[@Key]` markers but no `.bib` | Gate raises `VerificationError` → `blocked=True` |
| CRITICAL findings | Returns `(True, "CRITICAL=N …")` → `cmd_push` exits 1 |
| `--no-verify` flag set | Bypasses gate; logs `{"override": "--no-verify"}` to ledger |

Ledger path: `projects/sci-writing/.publish-ledger.jsonl`
Every push/edit outcome is appended (refused, bypassed, or clean).

### E2 — Verification footer in Substack draft body (`substack_ops.py`)

After a successful ProseMirror conversion, a verification footer is appended to the draft body before the POST/PUT to Substack. The footer is a ProseMirror `horizontal_rule` + `paragraph` node pair rendered as italic text:

```
─────────────────────────────────────────────────────────────
Verified by Scientific-OS citation gate · SHA: <sha1> · <audit_file> · CRITICAL=0 MAJOR=2 INFO=0
```

**SHA computation (`_audit_bundle_sha1`):** SHA1 over all adjacent `*.bib`, `*.citations.json`, and `*-audit.md` files (sorted, bytes-level). Falls back to the `.md` file itself when no audit artefacts exist. Returns the first 12 hex chars — long enough to be meaningful, short enough to read.

**Audit file reference:** the first `*-audit.md` found in the same directory, or `{stem}-audit.md` as a placeholder when absent.

**Gate summary line:** when citations are present the footer includes the `CRITICAL=N MAJOR=N INFO=N` summary from E1; when no `[@Key]` markers are present the status suffix is omitted.

**Opt-out:** `--no-footer` skips footer injection for both `push` and `edit`. No ledger entry is written for footer suppression — it is not a security bypass.

```bash
python3 substack_ops.py push --no-footer <markdown>
python3 substack_ops.py edit --no-footer <id> <markdown>
```

**Placement:** the footer is appended AFTER `conv.convert(body)` returns, directly to `doc["content"]`. This means the footer is outside the scope of the ProseMirror conversion and is not subject to citation-gate re-checking.

---

### E3 — Drive audit bundle staging (`tool-gdrive/scripts/gdrive_ops.py`)

When staging a verified manuscript to Google Drive, the full audit bundle is staged alongside it so the Drive copy is self-contained and auditable without the local repo.

**CLI:**
```bash
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py stage-bundle <manuscript.md>
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py stage-bundle <manuscript.md> --json
```

**What gets staged:**

| File pattern | What it is |
|---|---|
| `<manuscript>.md` | The manuscript itself |
| `*.bib` (same directory) | Bibliography — all citable keys |
| `*.citations.json` (same directory) | Citation sidecar — per-claim quotes and provenance anchors |
| `*-audit.md` (same directory) | Audit or review report from `auditor_pipeline.py` |

**Destination:** `<Drive staging root>/manuscripts/<stem>_audit/`

The bundle lands in a dedicated `{stem}_audit/` subfolder under the `manuscripts/` Drive category. This keeps the audit artefacts visually grouped and separate from plain `.md` drafts staged via `stage()`.

**Collision handling:** if a file already exists at the destination, a Unix timestamp suffix is appended to the filename before copying (same pattern as the main `stage()` function).

**Return value (`--json`):**
```json
{
  "bundle_dir": "/abs/path/to/manuscripts/slug_audit/",
  "staged":  [{"src": "...", "dest": "...", "size_bytes": 12345}, ...],
  "skipped": []
}
```
`skipped` lists any source paths that could not be read (e.g., permissions error). The bundle operation continues past skipped files rather than failing.

**Integration with Drive Push Gate:** E3 is not auto-invoked on Substack push. The CLAUDE.md Drive Push Gate already prompts "Push to Google Drive?" after a successful push — answer "Yes" and then use `stage-bundle` (not `stage`) to include the audit artefacts. Auto-staging on every Substack push was intentionally omitted to avoid double side-effects.

**Helper — `_find_audit_artifacts(md_path)`:** returns a sorted, deduplicated list of all adjacent `*.bib`, `*.citations.json`, and `*-audit.md` files. Does NOT include the `.md` file itself. Safe to call with no adjacent artefacts (returns `[]`).

---

### E4 — export-md pre-export gate (`scripts/export-md.py`)

`main()` calls `_run_export_gate(md_path)` before Pandoc/WeasyPrint:

| Outcome | Action |
|---------|--------|
| CRITICAL findings | Exits 1; logs `{"override": "refused"}` to export ledger |
| `--force` flag | Bypasses and exports; logs `{"override": "--force"}` |
| Clean | Exports normally; no ledger entry |

Export ledger: `projects/sci-writing/.export-ledger.jsonl`

---

## Tier F: Per-Claim Deep Links (`writing_ops.py`)

**Purpose:** every cited entry in the rendered bibliography should carry a URL that lands the reader on the specific passage (not just the paper root), so claims are one click from their source.

### `resolve_deep_link_url(entry, quote, source_anchor)`

Returns the best URL for a bib entry using a four-level priority cascade:

| Priority | URL form | When used |
|----------|----------|-----------|
| 1 | `citations.gxl.ai/papers/<id>#L<n>` | `source_anchor` is already a paperclip anchor — most precise, line-level |
| 2 | `https://doi.org/{doi}#:~:text={snippet}` | DOI present and quote available |
| 3 | `https://arxiv.org/abs/{eprint}#:~:text={snippet}` | arXiv eprint present and quote available |
| 4 | plain `https://doi.org/{doi}` or `https://arxiv.org/abs/{eprint}` | No quote available, or last resort |

**Text fragment snippet:** first ~100 chars of the sidecar quote, clipped at the last word boundary after 20 chars, percent-encoded. Spec: WICG Scroll-to-Text-Fragment. Chromium/Edge support it; Firefox and Safari do not (degrade gracefully to base URL). PDF links do not honour `#:~:text=` — documented limitation.

### `format_bibliography_with_deep_links(entries, style, sidecar)`

Drop-in replacement for `format_bibliography`. Wraps every formatted citation in a markdown hyperlink: `[{citation_text}]({deep_url})`. Supports all four styles (`apa`, `nature`, `ieee`, `vancouver`). Falls back to plain text for entries with no URL. Pass the sidecar dict to get fragment URLs; omit to get plain DOI/arXiv links.

```python
bib = format_bibliography_with_deep_links(entries, style="nature", sidecar=sidecar_dict)
```

### `check_per_claim_links_present(rendered_bibliography, used_keys, sidecar)`

**Criterion name:** `"Per-Claim Deep Link (Tier F)"` — **MAJOR**

Counts deep links in the rendered bibliography string using `_DEEP_LINK_RE`:
```
citations.gxl.ai/papers/[^\s)>\"']+        ← paperclip anchor
https?://[^\s)>\"']+#:~:text=[^\s)>\"']*   ← text-fragment URL
```

Fires when `deep_link_count < keys_with_quotes` (number of cited keys that have a non-empty sidecar quote). Reports the gap count and suggests switching to `format_bibliography_with_deep_links`.

**Guard conditions (check skips silently when):**
- `used_keys` is empty
- `rendered_bibliography` is empty or falsy
- `sidecar` is None or missing (no quotes to link)
- No cited key has a non-empty sidecar quote (`keys_with_quotes == 0`)

**Severity:** MAJOR (not CRITICAL) because a missing deep link is a usability deficit, not a fabrication signal — the citation may still be correct; the reader just lands on the paper root instead of the passage.

### Finding format

```
criterion: "Per-Claim Deep Link (Tier F)"
severity:  "major"
section:   "References"
finding:   "N of M cited entries with sidecar quotes lack a per-claim
            deep link in the rendered bibliography."
suggestion: "Use format_bibliography_with_deep_links(entries, style,
             sidecar) from writing_ops.py instead of format_bibliography
             to generate per-claim URLs automatically."
```

### Tests

`tests/test_per_claim_links.py` — 21 offline tests covering: plain URL detection, paperclip anchor detection, fragment URL detection, mixed present/absent, empty sidecar, no used keys, zero keys-with-quotes guard, and resolve_deep_link_url priority cascade.

---

## Tier G: Cross-Bib Contamination

**File:** `verify_ops.py` — `check_cross_bib_contamination` (G1) + `check_quote_attributable_to_one_source` (G2)

**Fired as:** Phase N in `run_verification`, after Phase M (Tier C3 claim-quote alignment).

### What it catches

The case where a writer pulls a real quote from Paper A but writes Paper B's DOI in `source_anchor`. Because the passage appears verbatim in _both_ papers' upstream seeds, the Tier 4 upstream-provenance check passes either way. Tier G detects the collision.

```
[@KeyA] sidecar quote: "the algorithm converges in O(n log n) time"
KeyA upstream seed:    "…the algorithm converges in O(n log n) time…"  ✓ (Tier 4 passes)
KeyB upstream seed:    "…the algorithm converges in O(n log n) time…"  ← contamination
→ MAJOR: ambiguous attribution — which paper actually said this?
```

### Severity

**MAJOR.** The same passage may legitimately recur across papers (a formula reproduced in a review). Surfacing it lets the human verify. Promote to CRITICAL only after confirming a negligible false-positive rate across 50+ real manuscripts.

### Guard conditions (check skips silently when)

- `quotes_path` is `None` or the file does not exist (Tier 4 already flagged)
- the sidecar is missing (`check_quote_sidecar` already flagged)
- `used_keys` is empty
- the quote is absent from the attributed key's own upstream seed (Tier 4 fires CRITICAL; no double-fire from Tier G)
- the sidecar quote is empty

### G2 helper: `check_quote_attributable_to_one_source`

```python
check_quote_attributable_to_one_source(quote_norm, all_seeds, own_key) -> bool
```

Returns `True` iff `quote_norm` appears **only** in `own_key`'s seed pool. An empty `quote_norm` is vacuously `True`. Used by `check_cross_bib_contamination` and exported for Tier F (`format_citation`) to verify that a rendered URL points to the right paper.

### Finding format

```
criterion: "Cross-Bib Contamination (Tier G)"
severity:  "major"
section:   "Citations"
finding:   "Quote for '[@keya]' also appears verbatim in the upstream seed for
            [@keyb], [@keyc]. Ambiguous attribution: the same passage appears
            in multiple papers' upstream seeds — the source_anchor may point
            to the wrong paper."
suggestion: "Verify which paper contains this exact passage and update the
             '[@keya]' sidecar's source_anchor accordingly. If both papers
             genuinely reproduce the passage (e.g. a formula in a review that
             copies the original), cite the primary source and mention the
             review in prose."
```

### Tests

`tests/test_cross_bib_contamination.py` — 23 offline tests:
- G2 unit: empty quote, unique seed, shared seed, substring match, edge cases (8 tests)
- G1 integration: clean passage, shared passage, both keys flagged, own-seed skip guard,
  None/missing path, empty keys, no sidecar, 3-key partial, all-others named, suggestion
  text, case-insensitive key, substring sub-span (15 tests)

---

## Tier H: Weekly Bib-Audit Cron

`cron/jobs/sci-writing-bib-audit.md` — runs every Monday at 09:00 (when activated).

- Finds all `.bib` files under `projects/` and `clients/*/projects/` (excluding `_processed/`).
- Calls `check_bib_integrity` on each; writes `projects/sci-writing/bib-audit_{YYYY-MM-DD}.md`.
- Report contains a summary table (Files | Entries | CRITICAL | MAJOR) plus per-finding detail.
- If any CRITICAL findings exist, stderr is non-empty → cron dispatcher marks the job for attention.
- `bib-audit banner` in `/lets-go` heartbeat reads `cron/status/sci-writing-bib-audit.json`
  and the latest `bib-audit_*.md`; surfaces CRITICAL/MAJOR counts if non-zero.
- CI bib-sweep job (`scripts/bib_sweep.py`) runs on every push; exits 1 on any CRITICAL finding.
  Treats all bib entries as "used" (audit everything, not just cited keys).

**Activating the cron:**
```yaml
# cron/jobs/sci-writing-bib-audit.md frontmatter
active: "true"   # change from "false" to enable
```

---

## Citation Density Thresholds

Minimum citations per non-trivial paragraph (>50 chars):

| Section | Min citations/paragraph |
|---------|------------------------|
| Introduction / Background | 2 |
| Discussion / Conclusion | 1 |
| Methods | 1 |
| Results | 0 (typically self-contained) |
| Abstract | 0 |

Paragraphs shorter than 50 characters are skipped.

## Hedging Escalation Pairs

Each pair is checked: if the source uses the weak form AND the draft uses the strong form (and the source does NOT also use the strong form), flag as escalation.

| Source language (weak) | Draft language (strong) |
|------------------------|--------------------------|
| suggests | proves |
| suggests | demonstrates |
| suggests | establishes |
| may / might / could | does |
| associated with | caused by |
| correlates with | causes |
| preliminary | definitive |
| appears | is |
| supports | proves |
| likely | certainly |
| possibly | definitely |

## Always-Flagged Overclaiming Patterns

These are flagged even without source comparison:

- `proves that X causes Y` — causal claims need explicit RCT or formal proof
- `definitively shows` — rarely justified
- `always results/leads/causes` — universal claims
- `never fails/results` — universal negation

## Statistical Reporting Standards

- **P-values must be accompanied by test statistics** within ±200 chars: `t(df)`, `F(df1, df2)`, `χ²(df)`, `z`, `U`, `H`, `r`, `R²`
- **"Significant" without p-value within ±200 chars** is flagged
- **2+ p-values with 0 effect sizes** in the document: flag for missing effect sizes (Cohen's d, η², R², odds ratio, hazard ratio, 95% CI)

## Well-Known Abbreviations (Skip Definition Check)

These don't need explicit definition: DNA, RNA, PCR, CT, MRI, USA, UK, EU, WHO, FDA, NIH, NSF, PI, MD, PhD, MSc, BSc, AI, ML, API, HTTP, URL, PDF, CSV, JSON, XML, SQL, UV, IR.

Add domain-specific well-known abbreviations to `WELL_KNOWN_ABBREVS` in `verify_ops.py` if false positives are common in your field.

## Phase 8 — Trust Floor (2026-04-26)

Phase 8 closed five concrete bypass vectors found by a code-level audit. Every change is regression-tested in `tests/test_phase8_trust_floor.py` plus updates in `tests/test_tier_a_hardening.py` and `tests/test_publish_gates.py`.

### 1. `unverifiable = {approved}` reason+date contract

A bare `unverifiable = {approved}` tag is no longer enough to downgrade an A1 (no-identifier) finding from CRITICAL to MAJOR. The bib entry MUST also carry both:

- `unverifiable_reason = {...}` — at least 30 characters, describing the *specific* reason this source cannot be programmatically verified. Generic templates (`approved`, `tutorial`, `pure expertise`, `tutorial with no primary sources`, `no doi`, `n/a`, …) are rejected.
- `unverifiable_date = {YYYY-MM-DD}` — ISO date the approval was granted; enables future staleness audits.

Any of: missing reason, short reason, blocklisted reason, missing date, malformed date → CRITICAL ("Bib Integrity (A1 — unverifiable incomplete)"). The legacy `unverifiable={approved}` form is treated as incomplete.

Parsed by `_unverifiable_status(entry)` in `verify_ops.py`; surfaced by `check_bib_integrity`.

### 2. Network ConnectionError → CRITICAL

`check_bib_integrity` and `check_inline_links` used to flag a CrossRef / arXiv / PubMed `ConnectionError` as MAJOR. Because `blocked = critical > 0`, that turned a flaky network into a silent pass for unverified citations.

Phase 8: `ConnectionError` raises CRITICAL ("Bib Integrity (network fail-closed)" / "Inline Link (A6 — DOI, network fail-closed)" / "Inline Link (A6 — arXiv, network fail-closed)"). The save is refused until the lookup succeeds or the entry is explicitly removed.

`ValueError` from a backend (DOI/arXiv id genuinely not found) remains MAJOR — the network worked but the identifier is wrong, which is a different failure class.

### 3. Publish-gate ImportError → fail-closed

`tool-substack/scripts/substack_ops.py:_run_verify_gate` and `scripts/export-md.py:_run_export_gate` used to print a stderr WARNING and return `(False, "")` if `verify_ops` couldn't be imported. Phase 8: the gate refuses to run unless `SCI_OS_ALLOW_UNGATED=1` is set in the environment.

When the env override is used, the bypass is logged to the publish/export ledger as `outcome: "ungated_bypass"` so the audit trail captures the override even though the gate did not.

### 4. `<!-- no-cite -->` scope tighten + density NOTE

The annotation that suppresses A5 (inline-attribution) used to match anywhere in the file with no reason validation. Phase 8 contract:

- The annotation must appear within the first 20 lines OR inside a YAML/HTML-comment frontmatter block.
- The reason must be ≥30 characters and not match the blocklist (`approved`, `tutorial`, `pure expertise`, `no citations`, …).
- An out-of-scope annotation produces "Inline Attribution (A5 — no-cite scope)" MAJOR.
- An invalid reason produces "Inline Attribution (A5 — no-cite reason)" MAJOR.
- A valid annotation suppresses the main A5 finding but emits "Inline Attribution (A5 — no-cite density)" INFO listing the count of unanchored factual-claim patterns (percentages, "study found", "researchers reported", `n=`, p-values, author-year prose) that survived suppression. Informational only — does not block the save.

### 5. Scope-mismatch escalation (`SCOPE_ESCALATIONS`)

Hedging-escalation pairs catch verb-strength shifts ("suggests" → "proves"). Phase 8 adds `SCOPE_ESCALATIONS` covering the dominant biomedical/clinical overclaim shape: the source studies one population and the draft generalizes to a broader one.

Pairs (source-pattern → draft-pattern), all checked between sidecar quote and the manuscript sentence containing `[@Key]`:

| Source scope          | Draft scope                                |
|-----------------------|--------------------------------------------|
| in mice / rats / rodents / non-human primates / animal model / preclinical | in patients / humans / clinical |
| in vitro / cell line / ex vivo | in vivo / in patients / clinical |
| in silico / simulation / computational | empirical / experimental / observed |
| pilot study / preliminary / case report / case series | established / proven / definitive / population / broadly |
| in our cohort / our study | universally / always / in general |
| in adults / elderly / children / pediatric | all ages / general population / broadly |
| observational / cross-sectional | causal / causation / caused by |
| at high/low/specific dose | at any/all doses / regardless of dose |

Fires when the source pattern is in the quote AND the draft pattern is in the manuscript sentence AND the draft pattern is NOT in the quote AND the source pattern is NOT in the manuscript sentence (writer kept the qualifier). MAJOR severity: "Scope Escalation (Phase 8)". Implemented by `check_scope_escalation`, wired into `run_verification` after `check_cross_bib_contamination`.

### Severity counts: `info` channel

`run_verification`'s summary dict now tracks `info` alongside `critical / major / minor / pass`. `severity == "note"` is folded into `info`. `info` findings are non-blocking (`blocked = critical > 0`) but visible to downstream consumers (Substack push, export-md) so the user sees what slipped through unverified.

## Phase 9 — Trust Floor Closure (2026-04-27)

Phase 9 closes the residual bypass set surfaced by the post-Phase-8 audit and locks the framework against the five epistemic limits documented in `CLOSURE.md` (repo root). Every change is regression-tested in `tests/test_phase9_closure.py`.

### B7. Receipts table parse-failure → CRITICAL

`researcher_ops.parse_receipts_table` used to silently return `[]` when the column headers in `## Verification receipts` did not match any known keyword (entry / API / title / author / DOI). Downstream `cross_reference_receipts` then became a no-op — every receipt escaped the title/author cross-check against the bib.

Phase 9: `check_research_receipts` now calls `parse_receipts_table` and emits CRITICAL "Researcher Integrity (Phase 3)" when `_TABLE_ROW_PATTERN` finds raw `| N |` data rows but the parser extracts zero structured rows. The writer must use header keywords the parser recognises.

### DP3. Substack bypass ledger entries carry manuscript md5

Pre-Phase-9 only the clean push/edit ledger writes carried `md5`. The five bypass writes (`_run_verify_gate` ungated_bypass on ImportError, `cmd_push --no-verify`, `cmd_push refused`, `cmd_edit --no-verify`, `cmd_edit refused`) did not. A forensic audit could not correlate a bypass row to the manuscript bytes at the time of the override.

Phase 9: `_safe_md5(path)` helper computes the hex digest fail-safe (returns `""` on OSError so a transient read failure cannot block the ledger write). Every bypass `_write_ledger` call now includes `md5`. Verified by static-grep regression.

### WG2. Auditor pipeline marker precondition aligned with verify_ops

`auditor_pipeline.cmd_gate` used `"[@" in draft_text` to decide whether a sci-communication draft without an upstream `quotes.json` should be refused. That substring fired on literal `[@` in code blocks (`arr[@i]`, `M[@:].sum()`) that `verify_ops.BROAD_MARKER_RE` would not flag. Same draft could pass verify_ops but be refused by the auditor pipeline, or vice versa.

Phase 9: `auditor_pipeline._BROAD_MARKER_RE = re.compile(r"\[@[A-Za-z][A-Za-z0-9_-]*")` — identical to `verify_ops.BROAD_MARKER_RE`. Detection agrees end-to-end.

### B1. NotebookEdit gate

Pre-Phase-9 the PreToolUse matcher was `Write|Edit|MultiEdit`; NotebookEdit was unmatched, so a writer could circumvent the citation gate by burying claims in a notebook cell within a watched workspace.

Phase 9: matcher is now `Write|Edit|MultiEdit|NotebookEdit`. `verify_gate.py:_is_watched_notebook(path)` returns True for `.ipynb` files under primary watched prefixes (`projects/sci-writing/`, `projects/sci-communication/`, `projects/briefs/`) or anywhere with a sibling `.bib`. When the hook sees a NotebookEdit on a watched notebook it refuses with a clear message: export the cell content to a sibling `.md` and edit through Write/Edit, or move the notebook outside the watched workspace if it isn't part of the citable manuscript. Simulating arbitrary cell-source insertion into rendered markdown is out of scope for the gate — refusing is the conservative default.

### WG3 fixture regression. bib_sweep skips test fixtures

Phase 9 broadened `bib_sweep.find_bib_files` to walk the entire repo (was `projects/**` only), aligning the cron + CI sweep with the hook's actual watched scope. A regression surfaced because `tests/fixtures/*.bib` are intentionally malformed inputs that always trip A1 CRITICAL — the cron started failing on a clean checkout.

`find_bib_files` now also excludes any path with both `tests` and `fixtures` in its parts. Verified by `test_phase9_closure.TestBibSweepFixtureExclusion`.

### Phase 9 — what the contract now guarantees

Combined with Phase 8, after Phase 9 the answer to "is fabrication mechanically blocked?" has a written contract rather than an opinion. See `CLOSURE.md` at the repo root for the full table (every contract row pinned by ≥1 regression test) plus the five irreducible epistemic limits that will not be patched (NLI, paywalled full-text, ledger HMAC, reason semantic quality, author particle disambiguation). New audits that find new mechanical bypasses get new commits; the five limits do not.

## How to Add a New Rule

1. Add a checker function to `verify_ops.py` returning `list[dict]` with the standard finding format: `{criterion, severity, section, finding, suggestion}`
2. Call it from `run_verification()`
3. Document the threshold/pattern in this file
4. If it's a new auto-fix, add it to the Auto-Fix vs Flag table above

## Finding Format

All findings follow this dict structure (compatible with `review_ops.generate_review_report`):

```python
{
    "criterion": "Citation Mechanics",  # category name
    "severity": "major",  # critical | major | minor | pass
    "section": "Citations",  # which manuscript section
    "finding": "Specific issue description",
    "suggestion": "How to fix it",
}
```
