---
name: "daily-prompt"
time: "09:00"
days: "daily"
active: "true"
model: "sonnet"
# notify: "on_finish"
# description: ""
# timeout: "30m"
# retry: "0"
---

<!-- EDIT: Replace everything below with your prompt. -->
<!-- This runs once daily at the time above. -->

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: <!-- EDIT: Describe what this job should do -->

Save output to: projects/ops-cron/daily-prompt_{today's date in YYYY-MM-DD format}.md

If anything fails, note the error and exit without creating the output file.
