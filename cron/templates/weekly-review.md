---
name: "weekly-review"
time: "17:00"
days: "fri"
active: "true"
model: "sonnet"
# notify: "on_finish"
# description: ""
# timeout: "30m"
# retry: "0"
---

<!-- EDIT: Customise the review prompt below -->

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: Review this week's activity and produce a summary.

1. Read all files in cron/logs/ from the last 7 days. Summarise what ran and what failed.
2. Read context/memory/ files from the last 7 days. Summarise key decisions and deliverables.
3. Note any open threads that need attention next week.

Save the review to: projects/ops-cron/{today's date in YYYY-MM-DD format}_weekly-review.md

If anything fails, note the error and continue with what you can access.
