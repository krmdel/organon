---
name: sci-tools
description: >
  Browse and search the Harvard ToolUniverse catalog of 2,200+ biomedical tools
  from the CLI, and create custom scientific skills with validated templates.
  Two modes: browse (search, filter, drill-down on biomedical tools) and create
  (generate sci-* skills from natural language descriptions with scientific defaults).
  Triggers on: "tools for", "find tools", "search tools", "browse tools",
  "ToolUniverse", "biomedical tools", "what tools exist for", "tool catalog",
  "refresh tools", "update catalog", "create a research skill", "build a science skill",
  "new scientific skill", "custom research skill".
  Does NOT trigger for: general "create a skill" without science context
  (use meta-skill-creator), data analysis (use sci-data-analysis),
  literature search (use sci-literature-research).
---

# Tool Ecosystem

## Outcome

Browse 2,200+ biomedical tools from Harvard's ToolUniverse catalog with instant
local search, or create custom sci-* skills from natural language descriptions.
Browse results display as compact tables (per D-03). Custom skills are validated
and auto-registered into the ecosystem.

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `research_context/research-profile.md` | full | Field context for skill creation personalization |
| `context/learnings.md` | `## sci-tools` section | Previous feedback |

## Dependencies

| Skill | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| `meta-skill-creator` | Required (for create mode) | Full skill creation workflow | Browse mode still works; create mode unavailable |

## Step 0: Auto-Setup

Run `.claude/skills/sci-tools/scripts/setup.sh` if first invocation. Downloads the ToolUniverse catalog snapshot to `data/tooluniverse-catalog.json` if not present.

## Step 1: Detect Intent

Parse user request into mode:
- **browse** -- "tools for", "find tools", "search tools", "browse tools", "ToolUniverse", "biomedical tools", "what tools exist for", "tool catalog", "show categories", "list categories"
- **refresh** -- "refresh tools", "update catalog", "re-download catalog"
- **create** -- "create a research skill", "build a science skill", "new scientific skill", "custom research skill", "I need a skill that" (in science context)

If ambiguous, ask which mode.

## Step 2: Browse Mode (TOOL-01, TOOL-04)

1. Run catalog search using `catalog_ops.search_catalog(query, category=category, limit=20)`.
2. If user specified a category, use it. If category doesn't match exactly, use fuzzy matching (substring). If no results, show available categories via `catalog_ops.list_categories()`.
3. Display results using `catalog_ops.format_results_table(results)` -- compact table with Name, Category, Type, Description (per D-03).
4. Show result count and "last refreshed" date from catalog metadata.
5. Ask: "Want details on any of these tools? Name one to drill down."

## Step 3: Drill-Down (TOOL-04)

1. Run `catalog_ops.get_tool_details(tool_name)` to get full schema via `tu info --json`.
2. Display: full description, parameters (name, type, required), return schema, test examples, usage notes.
3. If MCP tools available (`mcp__tooluniverse__get_tool_info`), use those as alternative for richer documentation.

## Step 4: Refresh Mode (TOOL-01)

1. Run `catalog_ops.refresh_catalog()`.
2. Report: "Catalog refreshed: {total_tools} tools. Last update: {refreshed_at}."
3. If refresh fails (network error, uvx unavailable), report error and note catalog still usable from last snapshot.

## Step 5: Create Mode (TOOL-03, TOOL-05)

1. Load `research_context/research-profile.md` for field context.
2. Get scientific defaults from `validate_ops.get_scientific_defaults()`:
   - Pre-fill category prefix: `sci-`
   - Pre-fill output path: `projects/sci-{skill-name}/`
   - Pre-fill context needs: `research-profile.md` (full)
   - Include reproducibility logging step
3. Read `.claude/skills/sci-tools/references/sci-skill-template.md` for the template structure.
4. Read `.claude/skills/meta-skill-creator/SKILL.md` and follow its methodology starting from "Capture Intent", but with these pre-filled values as defaults. The scientist only needs to describe what the skill should do -- scientific conventions are assumed (per D-06, D-07).
5. After scaffold is generated: offer to test (per D-08). Scientist can say "looks good" to skip eval, or provide test prompts to iterate.

## Step 6: Validate Created Skill (TOOL-05)

1. Run `validate_ops.validate_skill(skill_dir)`. Report errors and warnings.
2. Run `validate_ops.check_trigger_conflicts(skill_dir)`. If conflicts found, show them with suggestions (per D-11): "Trigger phrase '{phrase}' conflicts with {existing_skill}. Suggested alternative: '{suggestion}'." Non-blocking -- scientist decides.
3. If no errors: skill is ready. Heartbeat reconciliation will auto-register it in CLAUDE.md on next session (per D-10).
4. If errors: show them and offer to fix.

## Step 7: Feedback

Ask: "How did this land? Any adjustments?"
Log feedback to `context/learnings.md` under `## sci-tools`.

## Rules

- Always run setup.sh before first catalog search
- Always show compact table format for browse results (per D-03)
- Always use local catalog for search (per D-01), MCP/CLI for drill-down only (per D-02)
- Never duplicate meta-skill-creator logic -- delegate to it (per D-06)
- Always pre-fill scientific defaults for create mode (per D-07)
- Always run validation after skill creation (per D-09)
- Trigger conflicts are warnings, not blockers (per D-11)
- SkillsMP marketplace is deferred to v2 (per D-05). If asked, explain it's planned for a future version.

---

## Self-Update

If the user flags an issue, update the ## Rules section with the correction and today's date.
