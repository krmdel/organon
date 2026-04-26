---
name: meta-skill-creator
description: Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from scratch, edit, or optimize an existing skill, run evals to test a skill, benchmark skill performance with variance analysis, or optimize a skill's description for better triggering accuracy.
---

# Skill Creator

Create, iterate, and optimize skills. The core loop: define intent → draft SKILL.md → run test cases → evaluate with user → improve → repeat.

Pay attention to context cues when communicating — some users know JSON and assertions, others just opened a terminal. Explain terms briefly if in doubt.

---

## Creating a Skill

### Step 1: Capture Intent

Extract from conversation history first (tools used, steps taken, corrections made). Fill gaps by asking:

1. What should this skill enable Claude to do?
2. When should it trigger? (phrases / contexts)
3. What is the expected output format?
4. Does it produce output files? If yes → output folder is `projects/{skill-folder-name}/`; filenames include dates `{name}_{YYYY-MM-DD}.md`. Always save output — this is not optional.
5. Should we set up test cases? (Objectively-verifiable outputs benefit from them; subjective outputs usually don't.)

### Step 2: Skill Ecosystem Awareness

Scan `.claude/skills/` and read YAML frontmatter of each installed skill. Map:
- **Overlaps** — extend an existing skill or delineate boundaries instead of duplicating.
- **Upstream** — which skills produce context this new skill should consume?
- **Downstream** — which skills might benefit from this skill's output?
- **Trigger conflicts** — add negative triggers to both skills if keywords clash.

Add a `## Skill Relationships` section to the new SKILL.md.

### Step 3: Interview and Research

Ask about edge cases, input/output formats, example files, success criteria, dependencies. Check MCPs for relevant tools. Use subagents for parallel research if available.

### Step 4: Write the SKILL.md

**Mandatory frontmatter fields:** `name` (kebab-case, matches folder), `description` (trigger phrases + what it does — lean pushy to avoid under-triggering).

**Canonical SKILL.md Section Order — every skill must follow this exactly:**

```
---
name: {category}-{skill-name}
description: >
  {trigger phrases, what it does, negative triggers}
---

# {Skill Title}

{1-2 sentence overview}

## Outcome
{What it produces, output paths, file formats}

## Context Needs
{Table: File | Load level | Purpose}

## Dependencies                    ← only if applicable
{Table: Skill | Required? | What it provides | Without it}

## Skill Relationships             ← only if applicable
{Upstream, downstream, trigger conflicts}

## Before You Start                ← optional gate/mode selection

## Step N: {Step Title}            ← numbered steps as TOP-LEVEL ## headings
{Each step is its own ## heading, NOT nested under ## Instructions}

## Rules
{Hard constraints, dated entries — read before every run}

## Self-Update
{Instructions for runtime self-modification of Rules}

## Troubleshooting                 ← always LAST if present
```

Enforcement:
- Steps are always top-level `##` — never nested under `## Methodology`.
- `## Rules` and `## Self-Update` always follow all steps.
- `## Outcome` and `## Context Needs` always present (even if "None").
- Additional skill-specific sections go between the last step and `## Rules`.

**Learnings Integration (required):** Include a reference to `context/learnings.md` in Context Needs. The skill reads its own section before generating output and logs feedback back after major deliverables. Section name in learnings.md must match the skill folder name exactly. After writing the skill, open `context/learnings.md` and add `## {skill-folder-name}` under `# Individual Skills` if it doesn't exist.

**Self-Update Rules (required):** Every skill must include a `## Rules` section and an instruction: "If the user flags an issue, update `## Rules` immediately with the correction and today's date." Format: `- {YYYY-MM-DD}: {rule}`. This is distinct from learnings — Rules are direct corrections read before every run.

**Output path (mandatory for all output-producing skills):** Save to `projects/{skill-folder-name}/`. State "Always save output to disk. This is not optional." Only foundation skills writing exclusively to `research_context/` are exempt.

For detailed writing patterns, anatomy, progressive disclosure, and example-output guidance, see `references/skill-writing-guide.md`.

---

## Running and Evaluating Test Cases

After drafting, come up with 2-3 realistic test prompts. Share with user for confirmation, then run them. For the full eval-loop procedure (spawn runs + baselines, draft assertions, grade, aggregate, launch viewer, collect feedback), see `references/eval-loop.md`. Also covers the improvement loop, blind comparison, and environment-specific adaptations (Claude.ai, Cowork).

Save test cases to `evals/evals.json`. Results go in `<skill-name>-workspace/iteration-<N>/`.

---

## Description Optimization

After the skill is in good shape, offer to optimize its description for better triggering accuracy. Full procedure (generate eval queries, user review via HTML template, run `scripts/run_loop.py`, apply best description) in `references/description-optimization.md`.

---

## Package and Present

If the `present_files` tool is available:
```bash
python -m scripts.package_skill <path/to/skill-folder>
```
Direct user to the resulting `.skill` file.

---

## Reference Files

- `references/schemas.md` — JSON schemas for evals.json, grading.json, benchmark.json
- `references/eval-loop.md` — full eval running procedure, improvement loop, blind comparison, Claude.ai + Cowork modes
- `references/description-optimization.md` — description trigger optimization procedure
- `references/skill-writing-guide.md` — skill anatomy, progressive disclosure, writing patterns

Agent sub-prompts: `agents/grader.md`, `agents/comparator.md`, `agents/analyzer.md`.

---

## Rules

*Updated when the user flags issues. Read before every run.*

---

## Self-Update

If the user flags an issue, update `## Rules` immediately with the correction and today's date.
