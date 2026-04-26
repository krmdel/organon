---
name: test-watchdog
schedule: every_10m
description: Simple test job to verify watchdog execution
model: haiku
max_budget_usd: 0.10
enabled: false
---

You are running as a scheduled job for Organon.

Task: Write a single line confirming the watchdog works, including the current date and time.

Save to: projects/ops-cron/watchdog-test_{today's date in YYYY-MM-DD format}.md

Keep it to one line. Example: "Watchdog ran successfully at 2026-03-12 14:30:00"
