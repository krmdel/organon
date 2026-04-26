---
name: sci-writing
description: >
  Draft manuscript sections, format citations, and get AI peer review. Natural
  language invocation -- describe what you need and the skill routes to drafting,
  citation formatting, or peer review. Reads research profile, data analysis
  outputs, and literature search results for context-aware writing. After
  drafting, offers to generate supporting figures via viz skills.
  Triggers on: "draft introduction", "write methods", "format citations", "APA style",
  "bibliography", "peer review", "review my draft", "write abstract".
  Does NOT trigger for: literature search (use sci-literature-research),
  data analysis (use sci-data-analysis), image generation (use viz-nano-banana),
  repurpose/blog/lay summary (use sci-communication).
---

# Scientific Writing

> **Guardrails v3:** Draft and review modes are gated by a PreToolUse hook (`verify_gate.py`) that blocks any `Write`/`Edit` on `projects/sci-writing/**/*.md` with a CRITICAL finding. Not advisory — it cancels. Both modes require a pre-generated `{slug}.quotes.json` from `sci-literature-research` cite mode. Title matching uses a ≥ 0.95 similarity threshold (`TITLE_MATCH_THRESHOLD`); author validation (Tier 5) additionally checks first-author surname (≥ 0.85) and co-author Jaccard (≥ 0.70). Bib entries may use `doi`, `eprint` (arXiv), or `pmid` (PubMed) — dispatch order is arXiv > PubMed > CrossRef. See `references/verification-rules.md`, `references/paper-pipeline.md`, and `references/auditor-pipeline.md` for the full contract.

## Outcome

Draft manuscript sections, format citations for journal styles, and get structured peer review. Outputs go to `projects/sci-writing/<slug>/` with date-stamped filenames.

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `research_context/research-profile.md` | full | Field, preferences, writing style |
| `context/learnings.md` | `## sci-writing` section | Previous feedback |
| `projects/sci-data-analysis/` | latest report | Data for Results section |
| `projects/sci-literature-research/` | latest .bib + summaries | Citations for drafting |

## Dependencies

| Skill | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| `sci-literature-research` | Optional | .bib files | Ask user to provide .bib path |
| `viz-nano-banana` | Optional | Scientific illustrations | Placeholder figure references |
| `viz-excalidraw-diagram` | Optional | Hand-drawn diagrams | Placeholder figure references |
| `viz-diagram-code` | Optional | Mermaid diagrams | Placeholder figure references |
| `sci-data-analysis` | Optional | Data plots | Placeholder figure references |

Requires: Python venv. Run `.claude/skills/sci-writing/scripts/setup.sh` if issues.

## Step 0: Detect Intent — MANDATORY BRANCH

Parse user request into one of three modes and route immediately:

| Mode | Trigger phrases | Route to |
|------|-----------------|----------|
| **draft** | "write", "draft", "compose", "introduction", "methods", "results", "discussion", "abstract" | Step 1 |
| **format-citations** | "format citations", "bibliography", "APA", "Nature", "IEEE", "Vancouver", ".bib" | Step 2 |
| **review** | "review", "peer review", "check my draft", "critique", "feedback on", "audit my paper" | Step 3 |

If the request contains review phrases AND refers to an existing file ("my draft", a `.md` path), route **directly to Step 3** — do not run the paper pipeline on an existing draft; routing an existing manuscript through the draft cascade burns the retry budget with no valid output.

Repurpose / blog / lay summary requests → redirect to `sci-communication`.

## Step 1: Draft Mode — Paper Pipeline

Full design in `references/paper-pipeline.md`. Agents: `.claude/agents/sci-*.md`. Orchestrator: `scripts/paper_pipeline.py`. **Always use this pipeline; never hand-draft in parent context.**

1. Identify section + pick a kebab-case slug.
2. `python3 .claude/skills/sci-writing/scripts/paper_pipeline.py init <slug> --topic "<topic>" --section <section>`
3. Spawn `sci-researcher` (writes `research.md`, `<slug>.bib`, `<slug>.quotes.json`).
4. `paper_pipeline.py check-research <slug>` — re-spawn if `incomplete`.
5. Spawn `sci-writer` (writes `<slug>-draft.md` + citations sidecar).
6. `paper_pipeline.py gate-draft <slug>` — re-spawn writer on `blocked`; stop on `refused`.
7. Spawn `sci-verifier` → `<slug>-verification.md`.
8. `paper_pipeline.py collect-verification <slug>`
9. Spawn `sci-reviewer` → `<slug>-review.md`.
10. `paper_pipeline.py collect-review <slug>`
11. `paper_pipeline.py retry-check <slug>` — on `revise` surface MAJORs; on `retry` re-spawn writer (one cascade retry allowed); on `refused` stop.
12. `paper_pipeline.py finalize <slug>` — on `ok` all artifacts are persisted.
13. Log via `repro_logger`.

**`refused` is terminal within a nonce.** Recover only via `paper_pipeline.py init <slug> --force` (rotates nonce, resets retry count).

## Step 2: Format Citations Mode

Run `.claude/skills/sci-writing/scripts/writing_ops.py`:

1. Get .bib file path (or find latest in `projects/sci-literature-research/`).
2. Get target style (apa/nature/ieee/vancouver — default APA).
3. If draft provided: run `replace_citation_markers` to replace `[@key]` markers.
4. Generate bibliography with `format_bibliography`.
5. Save to `projects/sci-writing/{YYYY-MM-DD}_{name}_formatted.md`.
6. Report any unmatched citation warnings.

## Step 3: Review Mode — Auditor Pipeline

Full design in `references/auditor-pipeline.md`. Agent: `.claude/agents/sci-auditor.md`.

1. Get manuscript path + `.bib` path. No `.bib` → tell user to run `sci-literature-research` cite mode first.
2. Pick a kebab-case slug.
3. `python3 .claude/skills/sci-writing/scripts/auditor_pipeline.py init sci-writing <slug>`
4. Copy manuscript, bib, citations sidecar into `projects/sci-writing/<slug>/`.
5. `auditor_pipeline.py gate sci-writing <slug>` — stop on exit 2 (blocked) or 3 (refused).
6. Spawn `sci-auditor` → `<slug>-audit.md`.
7. `auditor_pipeline.py retry-check sci-writing <slug>` — on `retry` revise + re-gate + re-spawn (one retry); on `refused` stop.
8. `auditor_pipeline.py finalize sci-writing <slug>`.
9. Present findings + verdict. Review mode does not rewrite the user's manuscript.
10. Log via `repro_logger`.

## Step 4: Figure Proposal Gate

After each drafted section passes the accuracy gate, scan for claims a visual would strengthen. Make **one** offer per qualifying section:

```
This [section] mentions [X]. Add a figure?
- plot from data     → sci-data-analysis
- diagram/workflow   → viz-diagram-code
- illustration       → viz-nano-banana  (confirm style per its Step 3)
- hand-drawn sketch  → viz-excalidraw-diagram
- skip this / skip rest
```

Save figures to `projects/sci-writing/<slug>/figures/` and embed with relative path. Re-save after inserting so IDE preview updates. `skip rest` opts out for the full draft.

## Step 5: Accuracy Verification Gate

**MANDATORY. No `.bib` file → script exits code 3 (REFUSED). CRITICAL findings block save — no overrides.**

Write citations sidecar at `{manuscript_path}.citations.json` incrementally while drafting:

```json
{
  "version": 1,
  "claims": [
    {
      "key": "Smith2023",
      "quote": "verbatim passage (≥80 chars) copied directly from the source",
      "source_anchor": "10.1038/s41586-024-00001-0",
      "source_type": "doi"
    }
  ]
}
```

`source_type` is one of: `doi`, `paperclip`, `url`. For `paperclip`, anchor MUST be `https://citations.gxl.ai/papers/<doc_id>#L<n>[-L<m>]`. Quote `< 80 chars` → MAJOR. Non-matching quote → CRITICAL.

Run the gate:
```bash
python .claude/skills/sci-writing/scripts/verify_ops.py <manuscript.md> \
    --bib <refs.bib> [--source <source.md>]
```

Exit codes: `0` pass, `2` CRITICAL blocked, `3` refused. Display all findings with severity. If BLOCKED, revise and re-run — never save a blocked manuscript.

See `references/verification-rules.md` for the full phase table (A–H, including Tier A–H sprint hardening rules).

## Step 6: Humanizer Gate — ASK USER FIRST

After completing the draft, ask:

> "Your [section] is ready. Run it through the humanizer? (For formal academic writing, I'd recommend skipping — your call.)"

- Yes → run `tool-humanizer` in pipeline mode.
- No → save as-is (recommended for academic manuscripts).

## Step 7: Export to DOCX + PDF

```bash
python3 scripts/export-md.py projects/sci-writing/<slug>/<slug>-draft.md
```

Produces `.docx` (pandoc) and `.pdf` (weasyprint → Chromium → tectonic fallback). Copy binaries to `~/Downloads/`.

**Pre-export gate (Tier E4):** `export-md.py` runs `verify_ops.py` before Pandoc/WeasyPrint. CRITICAL findings block export and exit 1. Use `--force` to bypass; bypass is logged to `projects/sci-writing/.export-ledger.jsonl`.

**Substack publish gate (Tier E1, in `tool-substack`):** `substack_ops.py push/edit` also gates on CRITICAL before the network call. Use `--no-verify` to bypass; bypass is logged to `projects/sci-writing/.publish-ledger.jsonl`. Both ledgers record every outcome (refused, bypassed, clean) for audit.

**Drive audit bundle (Tier E3):** after staging to Drive, use `stage-bundle` (not `stage`) to include the full audit artefact set:
```bash
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py stage-bundle <manuscript.md>
```

## Step 8: Feedback

After any operation: "How does this look? Want to adjust tone, hedging level, or format?"
Log feedback to `context/learnings.md` under `## sci-writing`.

## Rules

*Updated when the user flags issues. Read before every run.*

---

## Self-Update

If the user flags an issue, update the `## Rules` section with the correction and today's date.
