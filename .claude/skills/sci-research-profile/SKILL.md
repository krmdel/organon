---
name: sci-research-profile
description: >
  Build and manage a scientist's research profile via interactive onboarding.
  Captures core identity, research focus, preferences, and tool ecosystem.
  Stored in research_context/research-profile.md for downstream skills.
  Triggers on: "research profile", "set up my profile", "who am I",
  "my research", "update profile", "research onboarding", "configure research".
  Foundation skill -- run before any execution skill that reads research context.
  Does NOT trigger for literature search, data analysis, or manuscript writing.
---

# Research Profile

## Outcome

File saved to `research_context/`:
- `research-profile.md` -- the scientist's full research profile (identity, focus, preferences, tools)

Any downstream skill can reference this file to personalize literature search, writing assistance, analysis defaults, and tool recommendations without asking the user again.

## Context Needs

| File | Load level | How it shapes this skill |
|------|-----------|--------------------------|
| `research_context/research-profile.md` | **writes** | Creates or updates this file |
| `context/learnings.md` | `## sci-research-profile` section | Apply previous feedback |

Load if they exist. Proceed without them if not.

---

## Step 0: Check Existing Profile

**Check if `research_context/research-profile.md` exists.**

If it exists:
> "You already have a research profile. Want to update it, view your research evolution, or keep the current one?"

- **Update** -- proceed to Step 1, pre-filling existing values. Show what changed before saving.
- **Show evolution** -- display the `## Research Activity Log` section (rendered as a table) plus any keyword/question additions made via `meta-wrap-up`. The profile evolves automatically across sessions via the repo-root profile-evolve.py script.
- **Keep** -- exit. Print: "Keeping your current profile."

If it doesn't exist -- proceed to Step 1.

**Note on profile evolution:** After each session, `meta-wrap-up` runs the repo-root profile-evolve.py script which:
- Always appends today's session to the `## Research Activity Log` (factual record)
- Proposes new keywords for recurring topics (requires user approval)
- Never modifies Core Identity, Institution, Department, or Career Stage

---

## Step 1: Core Identity

Prompt:
> "Let's set up your research profile. I'll ask a few questions about your research to personalize your experience. This takes about 2 minutes."
>
> "First, tell me about yourself -- your name, institution, department, and career stage."

Extract from free-form response:
- **Name:** full name
- **Institution:** university, lab, or company
- **Department:** department or division
- **Career Stage:** one of: PhD Student, Postdoc, Assistant Prof, Associate Prof, Full Prof, Industry Researcher, Research Scientist, Other

If career stage doesn't match a known value, ask for clarification with the list of options.

---

## Step 2: Research Focus

Prompt:
> "What's your primary research field? Include subfields, keywords, and any active research questions."

Extract:
- **Primary Field:** e.g., Computational Biology
- **Subfields:** list of subfields
- **Keywords:** comma-separated research keywords
- **Active Questions:** numbered list of current research questions

---

## Step 3: Preferences

Prompt:
> "What are your preferences for journals, citation style, and writing conventions?"

Extract:
- **Preferred Journals:** list of journals
- **Citation Style:** one of APA, Nature, IEEE, Vancouver, Chicago
- **Writing Conventions:** e.g., passive voice, Oxford comma, American English

---

## Step 4: Tool Ecosystem

Prompt:
> "What tools do you use? Programming languages, statistical packages, databases, workflow managers."

Extract:
- **Languages:** e.g., Python, R, MATLAB
- **Statistical Tools:** e.g., scipy, statsmodels, R/lme4
- **Databases:** e.g., UniProt, PDB, GEO, TCGA
- **Other:** e.g., Docker, Nextflow, Snakemake

---

## Step 5: Confirmation

Show the parsed profile summary in the markdown format from `references/profile-schema.md`.

Ask:
> "Does this look right? I can update any section."

- **Approved** -- save to `research_context/research-profile.md`. Print: "Research profile saved to {absolute_path}".
- **Edits requested** -- update the specified sections, re-display, and confirm again.

---

## Step 6: Graceful Degradation

If the user skips any section (says "skip" or provides no input), write "Not specified" for those fields. The profile is usable with partial data -- downstream skills treat "Not specified" as absent and fall back to generic behavior.

---

## Rules

*Updated automatically when the user flags issues. Read before every run.*

---

## Self-Update

If the user flags an issue with the output -- wrong parsing, bad format, missing context, incorrect assumption -- update the `## Rules` section in this SKILL.md immediately with the correction and today's date. Don't just log it to learnings; fix the skill so it doesn't repeat the mistake.
