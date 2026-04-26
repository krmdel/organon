# Pipeline Orchestration Reference

## How Pipelines Work

Pipelines are multi-step workflows that chain existing skills in a defined sequence.

- **Defined as:** Markdown files in `research/pipelines/`
- **Executed by:** Claude reading the pipeline definition and running each step sequentially
- **Invoked by:** Name (e.g., "run the literature monitor pipeline") or description ("search for new papers on CRISPR and summarize the top ones")
- **Output goes to:** `research/alerts/` — separate from notes and project files

Each step invokes an existing skill capability (sci-literature-research, sci-data-analysis, etc.) using natural language instructions that match that skill's routing triggers.

**Pipeline execution flow:**
1. Scientist requests a pipeline (named or described)
2. System shows the step plan before execution: `Running {pipeline_name} pipeline ({N} steps)...`
3. System executes steps sequentially, reporting status per step
4. On failure: retry once, then log and continue remaining steps
5. System writes output to `research/alerts/` with a Pipeline Status section

---

## Error Handling

Pipeline error handling follows a retry-then-continue pattern (per D-12):

1. **If a step fails:** Retry once immediately
2. **If retry also fails:** Log the failure to the output file, continue with remaining steps
3. **Never silently drop errors** — every failure is documented in the Pipeline Status section
4. **Always produce an output file**, even if the pipeline is fully or partially failed

**Per-step status reporting (copywriting from UI-SPEC):**

| Event | Copy |
|-------|------|
| Pipeline started | `Running {pipeline_name} pipeline ({N} steps)...` |
| Step success | `Step {N}/{total}: {step_name} -- complete` |
| Step failed (first attempt) | `Step {N}/{total}: {step_name} -- failed, retrying once...` |
| Step failed (final) | `Step {N}/{total}: {step_name} -- failed after retry. Logged to research/alerts/. Continuing remaining steps.` |
| Pipeline complete (all ok) | `Pipeline complete. {succeeded}/{total} steps succeeded. Output: research/alerts/{filename}.md` |
| Pipeline partial (some failed) | `Pipeline finished with errors. {succeeded}/{total} steps succeeded, {failed} failed. Check research/alerts/{filename}.md for details.` |

**Every pipeline output file MUST include a `## Pipeline Status` section:**

```markdown
## Pipeline Status
- Step 1: {step_name} -- complete | failed
- Step 2: {step_name} -- complete | failed | skipped
- Step 3: {step_name} -- complete | failed
```

Use `skipped` when a step was intentionally skipped because a preceding required step failed.

---

## Built-in Pipelines

Two built-in pipeline templates are available in `research/pipelines/`:

### literature-monitor

**Purpose:** Search for new papers on a topic and summarize the top results.

**Pattern:** search → summarize → alert

**Steps:**
1. **Search** — Use sci-literature-research (search mode) to find recent papers on the topic
2. **Summarize** — Use sci-literature-research (summarize mode) on the top 3 results
3. **Alert** — Compile into a dated alert file in `research/alerts/`

**Definition file:** `research/pipelines/literature-monitor.md`

### data-watch

**Purpose:** Monitor a dataset for significant changes in structure or statistics.

**Pattern:** load → analyze → flag

**Steps:**
1. **Load** — Use sci-data-analysis (load mode) to read the dataset and get current shape and types
2. **Analyze** — Use sci-data-analysis (profile mode) to generate descriptive statistics
3. **Flag** — Compare to baseline (if available) and flag as STABLE or CHANGED

**Definition file:** `research/pipelines/data-watch.md`

---

## Custom Pipelines

Scientists can describe custom workflows in natural language (per D-11):

- **Natural language description:** "Search for papers on {topic}, extract the methods sections, and compile a methods summary"
- **System behavior:** Compose the skill chain from the description, show the proposed steps for confirmation, then execute
- **Saving:** After successful execution, offer to save the pipeline definition for reuse: "Save this as a reusable pipeline? [y/N]"
- **Custom pipeline files:** Saved to `research/pipelines/{name}.md` for future invocation by name

When composing a custom pipeline, map the scientist's description to available skill triggers:
- Literature operations → sci-literature-research (search, summarize, cite, trends modes)
- Data operations → sci-data-analysis (load, analyze, clean, plot, profile modes)
- Hypothesis operations → sci-hypothesis (generate, design, validate modes)

---

## Pipeline File Format

All pipeline definition files follow this structure:

```markdown
# {Pipeline Name}

## Trigger
{What activates this pipeline -- manual, cron schedule, or event}

## Input
- {param}: {description} ({required/optional}, default: {value})

## Steps
1. **{Step Name}**: {Skill} ({mode}) -- {description}
2. **{Step Name}**: {Skill} ({mode}) -- {description}
3. **{Step Name}**: {Output/Flag step} -- {description}

## Output
research/alerts/{pipeline-name}_{YYYY-MM-DD}.md

## Error Handling
{Per-step error handling notes}
```

**Format rules:**
- Steps are numbered and use the pattern: `**{Name}**: {skill} ({mode}) -- {description}`
- Output filenames include the date in `YYYY-MM-DD` format
- Error Handling section documents any step-specific failure behavior beyond the default retry-then-continue

---

## Copywriting

All Pipeline Mode output uses these exact strings (from UI-SPEC):

| Trigger | Copy |
|---------|------|
| Pipeline started | `Running {pipeline_name} pipeline ({N} steps)...` |
| Step success | `Step {N}/{total}: {step_name} -- complete` |
| Step failed + retry | `Step {N}/{total}: {step_name} -- failed, retrying once...` |
| Step failed final | `Step {N}/{total}: {step_name} -- failed after retry. Logged to research/alerts/. Continuing remaining steps.` |
| Pipeline complete | `Pipeline complete. {succeeded}/{total} steps succeeded. Output: research/alerts/{filename}.md` |
| Pipeline partial | `Pipeline finished with errors. {succeeded}/{total} steps succeeded, {failed} failed. Check research/alerts/{filename}.md for details.` |
| No pipelines | `No pipeline templates found. Available built-in pipelines: literature-monitor, data-watch. Or describe a custom workflow.` |
