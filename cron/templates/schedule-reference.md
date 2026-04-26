---
name: "Schedule Reference"
time: "09:00"
days: "daily"
active: "false"
model: "sonnet"
---

<!-- This template shows all available scheduling options. -->
<!-- Copy this file to cron/jobs/ and edit the frontmatter + prompt below. -->

<!--
=== TIME OPTIONS ===

Exact time (runs once at that time):
  time: "09:00"               # 9:00 AM
  time: "14:30"               # 2:30 PM
  time: "00:00"               # Midnight

Multiple times (runs at each listed time):
  time: "09:00,17:00"         # Twice daily: 9 AM and 5 PM
  time: "08:00,12:00,18:00"   # Three times daily
  time: "09:00,13:00,17:00"   # Three times during work hours

Minute intervals (runs every N minutes):
  time: "every_1m"            # Every minute (testing only!)
  time: "every_5m"            # Every 5 minutes
  time: "every_10m"           # Every 10 minutes
  time: "every_15m"           # Every 15 minutes
  time: "every_30m"           # Every 30 minutes

Hour intervals (runs on the hour, every N hours):
  time: "every_1h"            # Every hour (24x/day)
  time: "every_2h"            # Every 2 hours (12x/day)
  time: "every_4h"            # Every 4 hours (6x/day)
  time: "every_6h"            # Every 6 hours (4x/day)
  time: "every_8h"            # Every 8 hours (3x/day)
  time: "every_12h"           # Every 12 hours (2x/day)

=== DAYS OPTIONS ===

  days: "daily"               # Every day
  days: "weekdays"            # Monday–Friday
  days: "weekends"            # Saturday–Sunday
  days: "mon"                 # Specific day
  days: "mon,wed,fri"         # Multiple specific days
  days: "tue,thu"             # Tuesday and Thursday

=== MODEL OPTIONS ===

  model: "haiku"              # Fast + cheap ($0.01–0.05/run)
  model: "sonnet"             # Balanced ($0.05–0.25/run) — default
  model: "opus"               # Most capable ($0.25–2.00/run)

=== ACTIVE ===

  active: "true"              # Job runs on schedule
  active: "false"             # Job is paused
-->

<!-- EDIT: Replace everything below with your prompt -->

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: Your task description here.

Save output to: projects/ops-cron/output_{today's date in YYYY-MM-DD format}.md

If anything fails, note the error and exit without creating the output file.
