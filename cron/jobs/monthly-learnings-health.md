---
name: "Monthly Learnings Health Check"
time: "10:00"
days: "mon"
active: "true"
model: "sonnet"
notify: "on_finish"
description: "Monthly audit of learnings.md for bloat, contradictions, and gaps"
timeout: "10m"
retry: "0"
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: Audit `context/learnings.md` for health issues and produce a cleanup report.

This job runs every Monday but should only produce a full report on the first Monday of each month. On other Mondays, check the date — if today is NOT the first Monday of the month, write a single line "Not first Monday — skipping" to the output file and exit.

Steps (first Monday only):

1. Read `context/learnings.md` in full.

2. Check for **bloat**:
   - Total line count. Flag if over 500 lines.
   - Any individual skill section over 100 lines. Flag with line count.
   - Any entries that are redundant (say the same thing in different words).

3. Check for **contradictions**:
   - Entries within the same skill section that give conflicting advice.
   - Entries in "What works well" that contradict entries in "What doesn't work well".

4. Check for **gaps**:
   - List all installed skills (scan `.claude/skills/` folders).
   - Compare against section headings in learnings.md under `# Individual Skills`.
   - Flag any installed skill that has NO learnings section, or a section with zero entries.

5. Check for **staleness**:
   - Are there learnings referencing skills that are no longer installed?
   - Are there entries that feel outdated based on context (references to old approaches, removed features)?

Save the report to: projects/ops-cron/learnings-health_{today's date in YYYY-MM-DD format}.md

Format:

## Learnings Health Check — {today's date}

### Summary
- Total lines: {N}
- Skill sections: {N} ({N} with entries, {N} empty)
- Issues found: {N}

### Bloat
- {flagged sections with line counts, or "All sections within limits"}

### Contradictions
- {any conflicting entries, or "None found"}

### Gaps
- {skills missing learnings sections}

### Stale Entries
- {entries referencing removed skills or outdated approaches}

### Recommended Actions
- {specific suggestions: "Consolidate 3 redundant entries in ## sci-writing", "Add learnings section for sci-research-mgmt", etc.}

If learnings.md doesn't exist, create a minimal report noting the file is missing and suggesting the user run a few skills to generate initial learnings.
