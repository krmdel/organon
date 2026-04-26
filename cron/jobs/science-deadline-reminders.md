---
name: science-deadline-reminders
schedule: every_4h
description: Check research project deadlines and alert on upcoming
model: haiku
max_budget_usd: 0.25
enabled: false
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: Scan all files in research/projects/ for milestone deadlines and report their status.

Steps:
1. Read each .md file in research/projects/
2. Parse the YAML frontmatter of each file to find the milestones list
3. For each milestone with status not equal to "complete":
   - If deadline is within 7 days of today: flag as URGENT
   - If deadline is within 30 days of today: flag as UPCOMING
   - If deadline is before today: flag as OVERDUE
4. Save to: research/alerts/deadline-reminder_{today's date in YYYY-MM-DD format}.md

Format the output as:
# Deadline Reminders - {date}

## OVERDUE
| Project | Milestone | Due Date | Days Overdue |
|---------|-----------|----------|--------------|
{rows or "None" if no overdue milestones}

## URGENT (within 7 days)
| Project | Milestone | Due Date | Days Remaining |
|---------|-----------|----------|----------------|
{rows or "None" if no urgent milestones}

## UPCOMING (within 30 days)
| Project | Milestone | Due Date | Days Remaining |
|---------|-----------|----------|----------------|
{rows or "None" if no upcoming milestones}

If no project files exist in research/projects/ or all milestones are complete: create the file with "All clear -- no pending deadlines."

If a project file cannot be parsed: log "Could not parse {filename}: {reason}" and continue to next file.
