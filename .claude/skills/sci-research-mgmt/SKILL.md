---
name: sci-research-mgmt
description: >
  Capture research notes, track projects with milestones and deadlines, schedule
  automated science tasks, and run cross-skill pipelines. Four modes via natural
  language: note (capture, search, promote), project (create, dashboard, detail,
  update), schedule (presets, custom, list), pipeline (run, create, list).
  Triggers on: "research note", "log observation", "jot down", "capture idea",
  "research project", "track project", "milestones", "deadlines", "project dashboard",
  "schedule alerts", "paper alerts", "set up monitoring", "deadline reminders",
  "run pipeline", "literature monitor", "data watch", "search notes", "promote experiment".
  Does NOT trigger for: data analysis (use sci-data-analysis), literature search
  (use sci-literature-research), hypothesis generation (use sci-hypothesis),
  scientific writing (use sci-writing).
---

# Research Management

## Outcome
Capture, organize, and automate research activities. Notes in research/notes/, experiments in research/experiments/, projects in research/projects/, alerts in research/alerts/, pipelines in research/pipelines/.

## Context Needs
| File | Load level | Purpose |
|------|-----------|---------|
| research_context/research-profile.md | full | Research interests for paper alerts, field context |
| context/learnings.md | `## sci-research-mgmt` section | Previous feedback |

## Dependencies
| Skill | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| sci-literature-research | Optional | Paper search for alerts and pipelines | Paper alert cron jobs won't find papers |
| sci-data-analysis | Optional | Data profiling for monitoring pipelines | Data monitoring cron jobs won't analyze |
| sci-hypothesis | Optional | Experiment design for note promotion | Promotion creates template only, no auto-design |
| ops-cron | Optional | Scheduling infrastructure | Schedule mode unavailable, manual execution only |

## Step 0: Detect Intent
Parse the user's natural language into a mode:
- **note** -- "note", "log", "jot", "capture", "observation", "idea", "search notes", "find in notes", "promote", "experiment log"
- **project** -- "project", "track", "milestone", "deadline", "dashboard", "progress"
- **schedule** -- "schedule", "alert", "paper alerts", "monitoring", "cron", "automate", "reminder"
- **pipeline** -- "pipeline", "workflow", "literature monitor", "data watch", "chain", "run pipeline"

## Step 1: Note Mode
Read references/note-template.md for format.

### Capture
1. Determine today's date (YYYY-MM-DD)
2. Check if research/notes/{date}.md exists
3. If not: create file with `# Research Notes - {date}` header
4. Append entry: `## {HH:MM} - {Title} {#tags}`
5. Detect tags from user's text (observations -> #observation, ideas -> #idea, experiments -> #experiment, meetings -> #meeting). Preserve any explicit #tags the user includes.
6. Confirm: "Logged to research/notes/{date}.md at {HH:MM}."
7. First-use: also show "Tip: Add inline tags like #idea, #experiment, #observation, or #meeting to make notes searchable."

### Search
1. Run: bash .claude/skills/sci-research-mgmt/scripts/search_notes.sh [--tag TAG] [QUERY]
2. Display results per UI-SPEC search format
3. If no results: "No notes matching \"{query}\". Try a broader term or different tag."

### Promote
1. Read references/experiment-template.md for format
2. Find #experiment entries in the specified day's note (default: today)
3. Copy entry to research/experiments/{date}_{slug}.md using template
4. Ask: "Pipe to sci-hypothesis for full experiment design? [y/N]"
5. If yes: invoke sci-hypothesis generate mode with the hypothesis text
6. Confirm: "Promoted to research/experiments/{date}_{slug}.md."

## Step 2: Project Mode
Read references/project-template.md for format.

### Create
1. Gather from user: project name, goal, PI, collaborators, funding, IRB, deadline, initial milestones
2. Create research/projects/{slug}.md with full YAML frontmatter
3. Confirm: "Research project \"{name}\" created at research/projects/{slug}.md."

### Dashboard
1. Read all files in research/projects/
2. Parse YAML frontmatter from each
3. Render table: | Project | Status | Next Milestone | Deadline | Progress |
4. Footer: "*{N} active, {M} paused. Next deadline: {project} in {N} days.*"

### Detail
1. Read specified project file
2. Show full milestone timeline with [x]/[~]/[ ]/[!] indicators
3. Show recent progress notes (last 5)
4. Show linked outputs as file paths

### Update
1. Parse update type: milestone complete, add note, change status, add link
2. Update YAML frontmatter or markdown body accordingly
3. Add progress note entry with today's date

## Step 3: Schedule Mode
Uses ops-cron skill for job management.

### Install Preset
1. Available presets: paper-alerts, deadline-reminders, data-monitor, weekly-digest, citation-tracker
2. All preset files already exist in cron/jobs/science-{name}.md
3. To install: set enabled: true in the job file (presets ship enabled by default)
4. Confirm: "Installed {name} cron job. Schedule: {schedule}. Output: research/alerts/."

### Custom Job
1. Delegate to ops-cron skill for custom job creation
2. Suggest output path: research/alerts/ for science-related jobs

### List
1. Read all cron/jobs/science-*.md files
2. Show table: | Job | Schedule | Enabled | Description |

## Step 4: Pipeline Mode
Read references/pipeline-templates.md for orchestration rules.

### Run
1. Match to built-in pipeline (research/pipelines/literature-monitor.md or data-watch.md) or custom
2. Read pipeline definition file
3. Show step plan: "Running {name} pipeline ({N} steps)..."
4. Execute each step, reporting: "Step {N}/{total}: {name} -- complete"
5. On failure: retry once. If still fails: "Step {N}: {name} -- failed after retry." Log and continue.
6. Write output to research/alerts/{pipeline}_{date}.md with ## Pipeline Status section
7. Summary: "Pipeline complete. {succeeded}/{total} steps succeeded."

### Create
1. Accept natural language description of desired workflow
2. Compose skill chain from description
3. Save to research/pipelines/{name}.md using pipeline file format from references/pipeline-templates.md
