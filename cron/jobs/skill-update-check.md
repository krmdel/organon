---
name: "Skill Update Check"
time: "09:00"
days: "weekdays"
active: "true"
model: "haiku"
notify: "on_finish"
description: "Checks for new or updated skills in the catalog"
timeout: "5m"
retry: "1"
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: Check if any skills have been added or updated since the last check.

Steps:

1. Read `.claude/skills/_catalog/catalog.json` to get the full list of available skills.
2. Read `.claude/skills/_catalog/installed.json` to get what's currently installed.
3. List all folders in `.claude/skills/` to see what's actually on disk.
4. Compare:
   - Are there skills in the catalog that aren't installed? List them with a one-line description.
   - Are there installed skills whose folder is missing from disk? Flag these as broken.
5. Read `cron/status/skill-update-check.json` if it exists — compare today's catalog snapshot to the previous one to detect newly added catalog entries.

Save output to: projects/ops-cron/skill-update-check_{today's date in YYYY-MM-DD format}.md

Format:
- **New in catalog** — skills available but not installed (skip if none)
- **Not installed** — full list of uninstalled skills with descriptions
- **Issues** — any broken references or missing folders (skip if none)

If the catalog file doesn't exist or can't be read, note the error and exit without creating the output file.
