---
name: ops-cron
description: >
  Schedule recurring tasks that run automatically via a system-level watchdog,
  even when Claude Code is closed. Job definitions persist in cron/jobs/ as the
  registry. The watchdog (launchd on Mac, Task Scheduler on Windows) checks
  every hour and runs due jobs headlessly via claude -p. Triggers on:
  "schedule a job", "cron job", "run this every morning", "automate daily",
  "recurring task", "set up a scheduled job", "check scheduled jobs",
  "list scheduled jobs", "install watchdog", "uninstall watchdog".
  Does NOT trigger for one-off tasks or in-session reminders.
---

# Scheduled Jobs

Recurring tasks that persist across sessions and run automatically. Job definitions live in `cron/jobs/`. Execution uses a system-level watchdog that runs `claude -p` headlessly -- jobs keep running even when Claude Code is closed.

## How It Works

The watchdog is a background process registered with your OS scheduler (launchd on Mac, Task Scheduler on Windows). Every hour it scans `cron/jobs/`, checks what's due, and runs each due job via `claude -p` with the model and budget from the job file. Each execution is stateless and self-contained. Install once, forget about it.

## Outcome

Job definition files in `cron/jobs/`. Automatic execution in the background. Logs for completed runs in `cron/logs/`.

## Context Needs

| File | Load level | How it shapes this skill |
|------|-----------|--------------------------|
| `context/learnings.md` | `## ops-cron` section | Known issues with specific jobs |

No brand context needed -- this is infrastructure.

---

## Step 1: Determine the Action

| Action | User says | What to do |
|--------|----------|------------|
| **Create** | "schedule a job", "run X every morning" | Build a job file (Step 2) then offer to install watchdog (Step 3) |
| **List** | "list jobs", "what's scheduled" | Read all files in `cron/jobs/`, show status table |
| **Install** | "install watchdog", "start scheduled jobs" | Run `bash scripts/install-watchdog.sh` |
| **Uninstall** | "uninstall watchdog", "stop all jobs" | Run `bash scripts/uninstall-watchdog.sh` |
| **Stop job** | "stop the X job", "disable X" | Set `enabled: false` in the job file |
| **Remove** | "remove the morning briefing job" | Delete the job file |
| **Logs** | "check job logs", "did the job run" | Read latest from `cron/logs/` |
| **Status** | "is the watchdog running" | Check for launchd plist (Mac) or scheduled task (Windows) |

## Step 2: Create a Job File

Ask the user (max 3 questions):
1. **What should it do?** -- The task in plain language
2. **How often?** -- "every 30 minutes", "every 2 hours", etc.
3. **Any constraints?** -- Budget cap, specific model

Create the job file at `cron/jobs/{job-name}.md`. See `references/job-format.md` for the format.

**Key rules for job prompts:**
- Self-contained -- each execution has no memory of the last
- Reference specific file paths
- Say where to save output
- Keep prompts focused -- one clear task per job

## Step 3: Install the Watchdog

If the watchdog isn't already installed, offer to install it:

**Mac:**
```bash
bash scripts/install-watchdog.sh
```

**Windows (PowerShell as admin):**
```powershell
powershell scripts/install-watchdog.ps1
```

The installer:
1. Checks `claude` CLI is available
2. Calculates estimated daily cost from enabled jobs
3. Registers with the OS scheduler
4. Starts running immediately

## Step 4: Verify

Show the user:
```
Watchdog: installed (checking every 60 minutes)

Scheduled jobs:
  trending-research    every 2h    enabled    sonnet    $0.50 cap
  inbox-check          every 30m   enabled    haiku     $0.25 cap

Estimated daily cost: $0.40 - $1.50
Logs: cron/logs/
```

---

## Schedule Reference

| User says | `schedule` value | How often it runs |
|-----------|-----------------|-------------------|
| Every 10 minutes | `every_10m` | 6x/hour |
| Every 30 minutes | `every_30m` | 2x/hour |
| Every hour | `every_1h` | 1x/hour |
| Every 2 hours | `every_2h` | Every 2 hours |
| Every 4 hours | `every_4h` | Every 4 hours |
| When I open Claude | `session_start` | Once per session (watchdog skips these) |

No cron expressions. Human-readable intervals only.

---

## Heartbeat Integration

At session start (CLAUDE.md heartbeat step 9):

1. Check if watchdog is installed (launchd plist exists on Mac)
2. If installed: report status: "Watchdog is active -- your N jobs run automatically"
3. If not installed but enabled jobs exist: suggest installing the watchdog

---

## Rules

*Updated automatically when the user flags issues. Read before every run.*

---

## Self-Update

If the user reports a job failing or a scheduling issue -- update the `## Rules` section immediately with the fix and today's date. Also log to `context/learnings.md` under `## ops-cron`.
