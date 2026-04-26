---
name: sci-hypothesis
description: >
  Generate testable hypotheses from data patterns and literature, design experiments
  with power analysis and sample size calculations, and validate hypotheses with
  statistical tests on an evidence spectrum. Natural language invocation -- describe
  your research question and the skill routes to generate, design, or validate mode.
  Reads research profile for field personalization.
  Triggers on: "hypothesis", "generate hypothesis", "what could explain", "experiment
  design", "design experiment", "protocol", "sample size", "power analysis", "validate
  hypothesis", "test hypothesis", "evidence for", "support or reject", "group differences",
  "data shows", "treatment vs control", "observed pattern", "differential expression",
  "what is driving", "what explains", "data pattern", "I noticed", "my data suggests".
  Does NOT trigger for: data analysis (use sci-data-analysis), literature search
  (use sci-literature-research), writing (use sci-writing).
---

# Hypothesis & Experiment Design

## Outcome

Generate hypotheses from data + literature, design experiments with power analysis, and validate hypotheses statistically. Outputs to `projects/sci-hypothesis/` with date-stamped filenames.

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `research_context/research-profile.md` | full | Field, interests for hypothesis personalization |
| `context/learnings.md` | `## sci-hypothesis` section | Previous feedback |
| `projects/sci-data-analysis/` | latest report | Data context for hypothesis generation |
| `projects/sci-literature-research/` | latest summaries | Literature context |

## Dependencies

| Skill | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| `sci-data-analysis` | Required | data_ops.py functions for validation | Cannot validate hypotheses without it |
| `tool-paperclip` | Optional | Deep biomedical corpus grounding for hypotheses (8M full-text papers, regex, `map` across results) | Falls back to federated search via `sci-literature-research` |
| `sci-literature-research` | Optional | Federated + routing for non-biomedical hypotheses | Ask user to provide literature context manually |

Requires: Python venv with scipy, pandas, numpy (shared with sci-data-analysis).
Run `.claude/skills/sci-hypothesis/scripts/setup.sh` if packages missing.

## Step 0: Auto-Setup

Run `.claude/skills/sci-hypothesis/scripts/setup.sh` if first invocation. Checks for scipy, pandas, numpy in the shared venv.

## Step 1: Detect Intent

Parse user request into one of 3 modes:
- **generate** -- "hypothesis", "generate", "what could explain", "patterns suggest", "research question", "group differences", "data shows", "treatment vs control", "observed pattern", "differential expression", "what is driving", "what explains", "data pattern", "I noticed", "my data suggests"
- **design** -- "experiment", "design", "protocol", "how to test", "sample size", "power analysis"
- **validate** -- "validate", "test hypothesis", "evidence for", "support or reject", "check hypothesis"

If ambiguous, ask which mode the scientist wants.

**Session state:** Remember the current hypothesis, dataset, and results within a conversation. If the user says "now design an experiment for that", use the last generated hypothesis.

## Step 2: Generate Mode (HYPO-01, HYPO-04)

1. Get dataset path from user (or use already-loaded data from session)
2. Run `hypothesis_ops.analyze_patterns(filepath)` to extract correlations, group differences, summary stats
3. **Search literature** for context — apply the same routing logic as sci-literature-research Step 0.5 (see `.claude/skills/sci-literature-research/references/paperclip-routing.md`):
   - **Biomedical hypothesis** (genes, proteins, diseases, drugs, clinical, cell biology, etc.) → delegate to `tool-paperclip` skill. Print the Skill Routing Notice. Run `paperclip search "{derived terms}" -n 5`, then optionally `paperclip map "what effect sizes / sample sizes / mechanisms were reported?"` across the top results to ground the hypothesis in real prior findings. Include `citations.gxl.ai/papers/<doc_id>#L<n>` anchors in the hypothesis supporting-evidence block.
   - **Non-biomedical hypothesis** (ML, physics, social science, economics) → use federated search. Load deferred tools: `ToolSearch` query `select:mcp__paper-search__search_papers,mcp__paper-search__get_paper_details`. Call `mcp__paper-search__search_papers` with derived terms. Get top 5 papers for context.
   - **Cross-disciplinary hypothesis** → run both and merge (dedupe by DOI).
   - If both paths fail, ask the user to provide relevant literature context manually.
4. Combine data patterns + literature into hypothesis generation:
   - Generate 3-5 hypotheses
   - Each hypothesis gets: statement, confidence level (high/medium/low), supporting evidence (data pattern + literature reference), falsifiability criteria ("This would be disproven if...")
   - Rank by confidence
5. Read `references/evidence-spectrum.md` for framing guidance
6. Save to `projects/sci-hypothesis/{YYYY-MM-DD}_{descriptive-name}-hypotheses.md`
7. Show clickable absolute file path

## Step 3: Design Mode (HYPO-02, HYPO-05)

1. Get hypothesis text (from generate output or user-provided)
2. Determine study type and effect size:
   - If user provides effect size, use it
   - If data available, estimate from data and warn about small-sample uncertainty
   - If neither, use Cohen's medium (d=0.5) with sensitivity table showing small/medium/large
3. Run `hypothesis_ops.design_experiment(hypothesis, effect_size, test_type, alpha, power, k_groups)` for power analysis and structure
4. Read `references/experiment-designs.md` for the matching study type template
5. Fill in the full protocol: variables (IV/DV/controls), sample size with sensitivity table, randomization strategy, control group design, data collection plan, statistical analysis plan
6. Add practical guidance: common pitfalls, ethical flags ("human subjects -> IRB required"), timeline, resources
7. Generate report via `hypothesis_ops.generate_experiment_report(design)`
8. Save to `projects/sci-hypothesis/{YYYY-MM-DD}_{descriptive-name}-experiment.md`
9. Show clickable absolute file path

## Step 4: Validate Mode (HYPO-03)

1. Get hypothesis text and dataset path
2. Determine appropriate test:
   - Auto-select based on hypothesis type and data structure
   - Show reasoning to scientist
   - Allow override
3. Run `hypothesis_ops.validate_hypothesis(df, hypothesis_type, col_a, col_b, group_col, alpha, data_file)`
   - This calls data_ops.run_statistical_test() internally (no code duplication)
   - Logs to repro_logger for reproducibility
4. Present evidence spectrum verdict: Strong Support / Moderate Support / Inconclusive / Moderate Against / Strong Against
5. Read `references/evidence-spectrum.md` for interpretation language
6. Generate report via `hypothesis_ops.generate_hypothesis_report(results)`
7. Save to `projects/sci-hypothesis/{YYYY-MM-DD}_{descriptive-name}-validation.md`
8. Show clickable absolute file path

## Step 5: Feedback

After any operation: "How did this land? Want to adjust parameters, try a different test, or explore further?"
Log feedback to `context/learnings.md` under `## sci-hypothesis`.

## Rules

*Updated when the user flags issues. Read before every run.*

---

## Self-Update

If the user flags an issue, update the ## Rules section with the correction and today's date.
