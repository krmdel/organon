---
name: "Weekly Activity Digest"
time: "17:00"
days: "fri"
active: "true"
model: "sonnet"
notify: "on_finish"
description: "Summarises the week's sessions, deliverables, and cron job activity"
timeout: "10m"
retry: "0"
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context. Read context/SOUL.md for voice.

Task: Produce a weekly digest of everything that happened this week.

Steps:

1. Read all memory files from this week in `context/memory/` (Monday through today). Extract:
   - Session goals and what was accomplished
   - Key decisions made
   - Deliverables produced (with file paths)
   - Open threads that carried over or are still unresolved

2. Read all cron log files in `cron/logs/` from the last 7 days. Summarise:
   - How many scheduled jobs ran
   - Any failures or timeouts (include job name and date)
   - Read `cron/status/*.json` for run/fail counts

3. Check `context/learnings.md` — were any new learnings added this week? Summarise additions.

4. Check `research_context/` file modification dates. Flag anything older than 30 days as potentially stale.

Save the digest to: projects/ops-cron/weekly-digest_{today's date in YYYY-MM-DD format}.md

Format the output as:

## Week of {Monday's date} — {today's date}

### Sessions
- {date}: {goal} — {outcome}

### Deliverables
- `{path}` — {what it is}

### Scheduled Jobs
- {N} runs this week, {N} failures
- {any notable issues}

### Learnings Added
- {summary of new entries, or "None this week"}

### Open Threads
- {anything unresolved heading into next week}

### Freshness Check
- {any research_context files older than 30 days}

Keep it concise — bullet points, not paragraphs. This is a quick status read, not a report.

If memory files don't exist for this week, note "No sessions recorded this week" and continue with the cron and freshness sections.
