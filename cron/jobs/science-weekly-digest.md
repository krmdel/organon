---
name: science-weekly-digest
schedule: every_4h
description: Weekly summary of research activity across all projects
model: sonnet
max_budget_usd: 0.75
enabled: false
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: Compile a weekly research digest summarizing all activity from the past 7 days.

IMPORTANT: ONLY run on Sundays. Check the current day of the week. If today is NOT Sunday, exit immediately with the message: "Not Sunday -- skipping weekly digest." Do not create any output file.

If today IS Sunday, proceed:

1. Read all note files from research/notes/ that were created in the last 7 days
2. Read all .md files in research/projects/ and note any milestone status changes from the last 7 days
3. Read all .md files in research/experiments/ created or modified in the last 7 days
4. Read all files in research/alerts/ created in the last 7 days (paper alerts, data monitor results)
5. Compile the weekly digest

Save to: research/alerts/weekly-digest_{today's date in YYYY-MM-DD format}.md

Format the output as:
# Weekly Research Digest - {date}

## This Week's Notes
{Count of notes files created. Key themes and topics observed across entries.}
{If none: "No research notes this week."}

## Project Updates
{For each active project: list any milestones changed to complete, in-progress, or any new entries in Progress Notes.}
{If none: "No project milestone updates this week."}

## New Experiments
{List any experiment log files created this week (research/experiments/).}
{If none: "No new experiments logged this week."}

## Alerts Summary
{Summarize paper alerts and data monitor results from this week -- count of new papers found, datasets changed.}
{If none: "No alerts generated this week."}

## Next Week
{List upcoming milestones from research/projects/ due within the next 14 days, sorted by date.}
{If none: "No upcoming deadlines in the next 14 days."}

If no activity at all was found: create the file with a brief "Quiet week -- no activity recorded."
