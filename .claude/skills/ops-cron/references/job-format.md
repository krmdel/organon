# Job File Format

Every scheduled job is a markdown file in `cron/jobs/` with YAML frontmatter and a prompt body.

---

## YAML Frontmatter

```yaml
---
name: job-name                    # Kebab-case, unique, matches filename
schedule: every_2h                # See schedule values below
description: What this job does   # One-liner for the jobs table
model: sonnet                     # sonnet (default) | haiku | opus
max_budget_usd: 0.50              # Hard cap per execution
enabled: true                     # Set to false to skip without deleting
---
```

### Required fields
- `name` -- must match the filename (without .md)
- `schedule` -- one of the schedule values below
- `description` -- what humans see in the jobs list

### Optional fields (with defaults)
- `model` -- defaults to `sonnet`
- `max_budget_usd` -- defaults to `0.50`
- `enabled` -- defaults to `true`

### Schedule values

| Value | Meaning | Runs per day (approx) |
|-------|---------|----------------------|
| `every_10m` | Every 10 minutes | 144 |
| `every_30m` | Every 30 minutes | 48 |
| `every_1h` | Every hour | 24 |
| `every_2h` | Every 2 hours | 12 |
| `every_4h` | Every 4 hours | 6 |
| `session_start` | Run once when session opens | Watchdog skips these |

---

## Prompt Body

Everything after the frontmatter `---` is the prompt executed by `claude -p` each time the job runs.

### Rules for good job prompts

1. **Self-contained.** Each execution has no memory of the last. State everything needed.
2. **Specific file paths.** "Read research_context/research-profile.md" not "check voice context".
3. **Explicit output location.** "Save results to projects/sci-trending-research/daily_{date}.md"
4. **Date-aware.** Use "today's date" -- Claude resolves it at runtime.
5. **Bounded scope.** One clear task. Don't chain 5 skills in one job.
6. **Error handling.** Say what to do if something fails (e.g., "If web search fails, exit without creating output").

### Example prompt body

```markdown
You are running as a scheduled job for Organon.

Read CLAUDE.md for system context. Read context/SOUL.md for voice.

Task: Research what's trending in AI automation on Reddit and X over the
last 7 days. Focus on Claude Code, n8n, and agentic workflows.

Save the brief to: projects/sci-trending-research/weekly-ai-automation_{today's date in YYYY-MM-DD format}.md

Format: Use the sci-trending-research skill methodology. Include:
- Top 5 Reddit threads with engagement counts
- Top 5 X posts with engagement counts
- Key themes and patterns
- Actionable content angles

If web search fails, note the failure and exit without creating the output file.
```

---

## How Jobs Get Executed

The watchdog (`scripts/watchdog.sh`) runs every hour via your OS scheduler. For each enabled job:

1. Parse the YAML frontmatter
2. Check if the job is due (based on schedule interval and last run time)
3. Run: `claude -p "{prompt}" --model {model} --max-turns 25 --allowedTools "Read,Write,Edit,Bash,Glob,Grep,WebSearch,WebFetch"`
4. Log output to `cron/logs/{name}_{date}.log`
5. Record the run time in `cron/watchdog.state.json`

Jobs with `schedule: session_start` are skipped by the watchdog -- they only run inside interactive Claude Code sessions.

---

## Cost Estimation

| Model | Typical cost per execution |
|-------|-----------------------------|
| haiku | $0.01-0.05 |
| sonnet | $0.05-0.25 |
| opus | $0.25-2.00 |

A sonnet job running every 2 hours for an 8-hour day = 4 executions = ~$0.40-1.00/day.

**Budget guard:** Always set `max_budget_usd`. Start low ($0.50) and increase only if the job needs it.
