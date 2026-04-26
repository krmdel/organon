---
name: sci-communication
description: >
  Create science outreach content -- blog posts, tutorials, concept explainers,
  lay summaries, newsletters, social threads, and press releases from any source.
  Accepts papers, concepts, URLs, datasets, or personal expertise as input.
  Includes visual generation for inline diagrams and illustrations.
  Triggers on: "blog post", "tutorial", "explain this concept", "lay summary",
  "science blog", "write a tutorial about", "newsletter", "social thread",
  "press release", "explain for non-scientists", "teach this", "gentle introduction",
  "explainer", "educational content", "science communication", "scicomm".
  Does NOT trigger for: manuscript drafting (use sci-writing), literature search
  (use sci-literature-research), data analysis (use sci-data-analysis).
---

# Science Communication

> **Guardrails v3 (load-bearing):** Every sci-communication artifact under `projects/sci-communication/**/*.md` is gated by the same PreToolUse hook (`.claude/hooks_info/verify_gate.py`) that protects sci-writing — the hook simulates the proposed Write/Edit and **blocks** the tool call on any CRITICAL finding. Drafts must carry a `{slug}.bib`, a `{slug}.md.citations.json` sidecar with `source_confidence: full-text` quotes, and (for cited claims) a pre-generated `{slug}.quotes.json` from `sci-literature-research` cite mode. The auditor pipeline auto-passes `--quotes` to verify_ops so every sidecar claim must trace to an upstream candidate. **Humanizer workflow:** after the auditor accepts the draft and the pipeline reaches `phase=finalized`, if you invoke `tool-humanizer` on the draft you MUST follow it with `python3 .claude/skills/sci-writing/scripts/auditor_pipeline.py post-humanize sci-communication <slug>`. Any non-zero exit flips the pipeline to terminal `refused` and the humanized draft must be rolled back. See `../sci-writing/references/auditor-pipeline.md` for the full contract.

## Outcome

Accessible science content saved to `projects/sci-communication/` with date-stamped filenames. Each piece is accurate, engaging, and includes visuals where appropriate. Supports seven formats from a single skill, with flexible source inputs -- not limited to papers.

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `research_context/research-profile.md` | full | Field expertise, writing preferences |
| `context/learnings.md` | `## sci-communication` section | Previous feedback |
| `projects/sci-writing/` | latest drafts | If repurposing from a manuscript |
| `projects/sci-literature-research/` | latest summaries | For citation context |

## Dependencies

| Skill | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| `tool-humanizer` | Optional | De-AI for blog/social content | Save without humanizer pass |
| `viz-nano-banana` | Optional | Scientific illustrations, concept diagrams | Text-only output |
| `viz-excalidraw-diagram` | Optional | Hand-drawn style flow diagrams | Text-only output |
| `viz-diagram-code` | Optional | Polished Mermaid diagrams (flowcharts, architecture, mind maps) | Text-only output |
| `sci-data-analysis` | Optional | Data plots for evidence-based content | Reference data without plots |
| `sci-literature-research` | Optional | Routes to paperclip or federated search for cite mode; produces the upstream `.quotes.json` seed | Ask user for citations |
| `tool-paperclip` | Optional (biomedical topics) | Full-text line-anchored quotes via `citations.gxl.ai` URLs — stronger auditor verification | Abstract-only citations via federated search |

## Step 0: Detect Intent

Parse user request into one of these modes:

- **blog** -- "blog post", "blog about", "write about X for a general audience"
- **tutorial** -- "tutorial", "how-to", "teach", "explain how to", "gentle introduction", "step by step"
- **explainer** -- "explain this concept", "what is X", "ELI5", "for non-scientists"
- **social** -- "thread", "LinkedIn", "Twitter", "social media"
- **newsletter** -- "newsletter", "digest", "roundup", "weekly update"
- **press-release** -- "press release", "institutional communication"
- **lay-summary** -- "lay summary", "patient-friendly", "plain language"

If ambiguous, ask: "Which format works best? I can do: blog post, tutorial, explainer, social thread, newsletter, press release, or lay summary."

## Step 1: Get Source Material

Accept flexible inputs -- NOT just papers:

| Source type | How to handle |
|-------------|--------------|
| Paper/manuscript file | Read and extract key findings, methods, implications |
| Concept/topic (no file) | Use researcher's expertise + literature search if available |
| URL(s) | Fetch via WebFetch/Firecrawl, extract content |
| Pasted text | Use directly |
| Dataset + findings | Load context from sci-data-analysis outputs |
| Multiple sources | Synthesize across all provided materials |

If the user just names a topic without providing a source, that is valid -- generate from expertise and offer to enrich with literature search.

**⚠️ Citation mode decision point (H3).** If the draft will carry ANY
`[@Key]` citation markers — true for almost every blog/tutorial/
newsletter that references studies, findings, or papers — you MUST run
`sci-literature-research` **cite mode** on the source material FIRST,
before drafting. Cite mode produces `{slug}.quotes.json`, the upstream
seed that Phase H (provenance trace) uses to prove the sidecar quotes
are not fabricated.

Without the upstream seed, the Step 5 auditor pipeline will **refuse
the draft at the gate step** with a targeted error pointing back here.
Don't be surprised later — resolve citation sourcing NOW:

- **Cited piece** → run sci-literature-research cite mode, save
  `{slug}.quotes.json` alongside `{slug}.md` and `{slug}.bib`. Then
  draft.
- **Pure-expertise piece** (lay explainer, opinion, personal story with
  no factual citations) → do not use `[@Key]` markers at all. The
  auditor will skip Phase H gracefully when no markers are present.

**Paperclip routing for fact sourcing (updated 2026-04-14):** When the
topic is biomedical (genes, drugs, diseases, clinical research, life
sciences), sci-literature-research will route cite mode through
`tool-paperclip` per its Step 0.5 rules. This gives the quotes sidecar
real full-text line anchors (`citations.gxl.ai/papers/<doc_id>#L<n>`)
instead of abstract-only snippets — the auditor's semantic pass is
significantly stronger when it can verify against full text. You do
not need to invoke paperclip manually; just make sure the upstream
cite mode runs before drafting. For explicitly non-biomedical topics
(ML, physics, CS), federated search is still the right path.

## Step 2: Generate Content

Read the appropriate reference file for the target format:
- blog -> `references/blog-format.md`
- tutorial, explainer -> `references/tutorial-format.md`
- social -> `references/social-formats.md`
- newsletter, press-release, lay-summary -> `references/other-formats.md`

Apply these gates to ALL formats:
1. **Accuracy preservation** -- never overstate findings. Run the verification checklist from the reference file.
2. **Appropriate hedging** -- less formal than papers, but honest about uncertainty. Never upgrade "suggests" to "proves".
3. **Audience-appropriate language** -- reading level varies by format (grade 8 for lay summary, college-educated for blog, technical-but-accessible for tutorial).
4. **Research profile context** -- if loaded, write from the scientist's perspective and match their voice preferences.

## Step 3: Figure Proposal Gate (per CLAUDE.md)

Walk the draft section-by-section (intro, each body section, conclusion). For each section, scan for claims a visual would strengthen — mechanisms, comparisons, workflows, data trends, experimental designs, concept maps — and make **one** routed offer per qualifying section. Don't batch the whole piece; don't interrupt mid-paragraph.

For each candidate, ask:

```
This [section] mentions [X]. Add a figure?
- plot from data     → sci-data-analysis
- diagram/workflow   → viz-diagram-code
- illustration       → viz-nano-banana  (confirm style per its Step 3)
- hand-drawn sketch  → viz-excalidraw-diagram
- skip this / skip rest
```

**Style defaults by format** (use as the "recommended" hint, not a lock-in):
- **blog / substack / social / newsletter** → lean `viz-nano-banana` `color` style for editorial warmth.
- **tutorial / explainer** → `viz-diagram-code` when text precision matters, `viz-nano-banana` `notebook` when teaching a concept.
- **press-release / lay-summary** → `viz-nano-banana` `scientific` for credibility.
- **data-driven claims in any format** → `sci-data-analysis` plot.

**Strong-signal override:** if the user explicitly says "casual", "friendly", "warm", "not overly scientific", "self-explanatory" — pick `viz-nano-banana` `color`, never Mermaid.

On `skip rest`, stop offering for the remainder of the draft. Save generated figures to `projects/sci-communication/<slug>/figures/` and embed with a relative path. After inserting, re-save so the IDE auto-preview (CLAUDE.md § Output Standards) picks up both the markdown and the new asset.

If no viz skills are installed, produce text-only output and note where visuals would strengthen the piece.

## Step 4: Citation & Reference Generation

**After drafting, ensure all claims are properly attributed with references.**

1. **Extract cited works from source material.** If the source is a paper/PDF, extract its reference list. If the source is a concept or multiple papers, collect all referenced works.
2. **Check existing literature data.** Scan `projects/sci-literature-research/` for `.bib` files and paper summaries that are relevant to the topic.
3. **Draft with `[@Key]` markers tied to the .bib.** Use `[@AuthorYear]` markers for every factual claim — the formatter will rewrite them to natural-language citations only AFTER the verification gate passes. **Do not write claims without a citation marker.** If a claim lacks a real source, either find one or delete the claim.
4. **Generate a BibTeX file** alongside the output: save to `projects/sci-communication/{YYYY-MM-DD}_{slug}_references.bib` containing all cited works. This is REQUIRED by the Step 5 gate — not optional.
5. **Write the citations sidecar** at `{output_path}.citations.json` (same schema as sci-writing Step 5a). Every `[@Key]` marker must have a `claims[]` entry with a verbatim quote, source_anchor, and source_type. Populate this as you draft, not after.

**Do not write "studies show" or "research suggests" without specifying which studies/research.** Every attribution must be traceable. A blog post without a .bib and sidecar is blocked by Step 5.

## Step 5: Auditor Pipeline — MANDATORY

**Hard contract:** Every sci-communication output goes through the auditor pipeline before save. Fabricated citations in a blog post are just as damaging as in a paper — more so, because lay readers can't tell.

The auditor pipeline wraps the mechanical `verify_ops.py` gate AND a single `sci-auditor` subagent (defined in `.claude/agents/sci-auditor.md`). Design is in `.claude/skills/sci-writing/references/auditor-pipeline.md`. Follow the steps literally — Python is the state manager, Claude is the conductor.

**Step 5.1 — Announce workspace + confirm location.** Before running any pipeline command, tell the user where the artifacts will land and offer an override:

```
Workspace: projects/sci-communication/<slug>/
All artifacts (draft .md, .bib, sidecar, figures/, -audit.md, .docx, .pdf, preview.html)
will live here. Save to this path, or somewhere else?
```

Default is `projects/sci-communication/<slug>/`. If the user supplies a different directory (e.g. `docs/` for framework documentation, `papers/2026/<slug>/` for curated submissions), honour it — the pipeline accepts any path. Do NOT silently relocate artifacts; the workspace is the single source of truth for that project.

**A4 — verification gate coverage:** The `verify_gate.py` PreToolUse hook now watches ANY `.md` file that has a sibling `.bib` in the same directory, regardless of the parent path. Custom directories are automatically gated as long as the `.bib` is co-located. To gate manually: `python3 .claude/skills/sci-writing/scripts/verify_ops.py <md_path> --bib <bib_path>`.

**Step 5.2 — Initialize the workspace.** Pick a slug (kebab-case, derived from topic + format). Run:

```bash
python3 .claude/skills/sci-writing/scripts/auditor_pipeline.py init sci-communication <slug>
```

This creates `projects/sci-communication/<slug>/` and `.pipeline_state.json`. From now on, save the draft markdown as `<slug>.md` and the bib as `<slug>.bib` inside that directory so the pipeline finds them.

**Step 5.2 — Move the Step 4 draft into the workspace.** Save `<slug>.md`, `<slug>.bib`, and `<slug>.md.citations.json` under `projects/sci-communication/<slug>/`. If cite mode produced a `<slug>.quotes.json` upstream, place it here too.

**Step 5.3 — Run the mechanical gate.**

```bash
python3 .claude/skills/sci-writing/scripts/auditor_pipeline.py gate sci-communication <slug>
```

Exit codes: `0` passed, `2` blocked (CRITICAL findings, revise and re-run), `3` refused (contract failure — no bib, empty bib, or sidecar missing; fix and re-run). Do NOT proceed to Step 5.4 until gate returns passed.

**Step 5.4 — Spawn the `sci-auditor` subagent via the Agent tool.** Pass the slug + category so it reads `projects/sci-communication/<slug>/` and writes `<slug>-audit.md`. The auditor runs verify_ops.py again, does a semantic (claim, quote) pass, and produces FATAL/MAJOR/MINOR findings with a final verdict.

**Step 5.5 — Retry-check.**

```bash
python3 .claude/skills/sci-writing/scripts/auditor_pipeline.py retry-check sci-communication <slug>
```

- `status: ok` → no FATAL, proceed to Step 5.6.
- `status: retry` → at least one FATAL, pipeline grants ONE retry. Apply the audit's revision plan to `<slug>.md`, re-run Step 5.3, then re-spawn sci-auditor, then re-run this step.
- `status: refused` → FATAL persists after retry budget exhausted. STOP. Surface `<slug>-audit.md` to the user. Do NOT save.

**Step 5.6 — Finalize.**

```bash
python3 .claude/skills/sci-writing/scripts/auditor_pipeline.py finalize sci-communication <slug>
```

If `status: ok`, the save is cleared. Proceed to Step 5.7. If `status: refused`, STOP — something flipped between retry-check and finalize (should be rare), inspect state and halt.

**Step 5.7 — Format rewrite.** Rewrite `[@Key]` markers in `<slug>.md` to natural-language citations per `references/blog-format.md` (blog/substack/newsletter), inline links (tutorial/explainer), or institution-journal phrasing (lay summary/press release). Append a "References & Further Reading" section. Keep `<slug>.bib`, `<slug>.md.citations.json`, and `<slug>-audit.md` alongside for auditability.

**Never save content that the pipeline refused. If the user insists, refuse and explain exactly which findings blocked.**

## Step 6: Humanizer Gate — ASK USER FIRST

**MANDATORY: Ask the user before running the humanizer.** Never auto-apply.

After the draft is complete, present the option:

> "Your [blog post / social thread / newsletter] is ready. Would you like me to run it through the humanizer to polish the voice and remove AI writing patterns? (Recommended for blog/social content — removes cliches, hedging, and promotional language.)"

- **User says yes** → run `tool-humanizer` in pipeline mode. Use `deep` mode if `research_context/research-profile.md` exists, `standard` otherwise.
- **User says no** → save as-is, skip humanizer entirely.
- For **press-release**, **lay-summary**, **explainer**, and **tutorial** formats: suggest skipping ("These formats have their own voice conventions — I'd recommend skipping the humanizer. Your call.").

## Step 7: Export to DOCX + PDF

Every saved markdown deliverable ships alongside a `.docx` (always) and a `.pdf` (when a PDF engine is available). This is mandatory — users share blog posts, whitepapers, and press releases in formats other than raw markdown, so the skill produces all three automatically.

```bash
python3 scripts/export-md.py projects/sci-communication/<slug>/<slug>.md
```

What the utility does:
- Pre-renders every ```mermaid fence to a PNG under `<workspace>/figures/`
- Produces `<slug>.docx` via pandoc (no extra engine required)
- Produces `<slug>.pdf` via (in order): pandoc+weasyprint → headless Chromium → pandoc+tectonic. Gracefully skips PDF with install instructions if none available.
- Reports absolute paths for every artifact

Announce the produced file paths to the user. Copy binary outputs to `~/Downloads/` per CLAUDE.md § Output Standards.

## Step 8: Save, Preview, Feedback

Show the full absolute paths so the user can click them directly:
- `projects/sci-communication/<slug>/<slug>.md` (source)
- `projects/sci-communication/<slug>/<slug>.docx` (shareable)
- `projects/sci-communication/<slug>/<slug>.pdf` (if engine available)
- `projects/sci-communication/<slug>/figures/` (rendered Mermaid + any viz-* assets)

Open the markdown in the IDE per CLAUDE.md § Output Standards (auto-open rule). For rich preview (Mermaid rendering, embedded figures), offer: `python3 scripts/preview-md.py <path>` — this previews in the IDE's built-in markdown view when available, browser otherwise.

**Pre-publish gate (automatic).** Both publish paths run citation verification before accepting the file:

- **Substack push/edit** — `tool-substack push <md>` and `tool-substack edit <id> <md>` automatically run the citation gate when a sibling `.bib` exists or the file contains `[@Key]` markers. A CRITICAL finding blocks the push and prints the exact `--no-verify` bypass command. Bypass is logged to `~/.scientific-os/substack-publish-ledger.jsonl`.

- **Export to DOCX/PDF** — `scripts/export-md.py <md>` runs the same gate. A CRITICAL finding blocks export unless `--force` is passed. Bypass is logged to `~/.scientific-os/export-ledger.jsonl`.

Pure-expertise drafts with no `.bib` and no `[@Key]` markers pass the gate automatically — no action needed.

Ask: "How does this read? Want to adjust the depth, tone, or add more visuals?"

Log feedback to `context/learnings.md` under `## sci-communication`.

## Rules

<!-- Populated by user feedback via the learnings loop -->
