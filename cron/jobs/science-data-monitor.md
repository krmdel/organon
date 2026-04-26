---
name: science-data-monitor
schedule: every_4h
description: Monitor tracked datasets for changes
model: sonnet
max_budget_usd: 0.50
enabled: false
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: Monitor tracked datasets for changes by comparing current file state to the last known state.

Steps:
1. Read all .md files in research/projects/ and find the datasets listed in the `datasets:` frontmatter field of each project
2. Find the most recent research/alerts/data-monitor_*.md file (if it exists) to get the last known file states
3. For each tracked dataset path:
   a. Check if the file exists and get its current modification timestamp and file size
   b. Compare to the last known state recorded in the most recent data-monitor alert
   c. If the dataset has changed: use the sci-data-analysis skill (profile mode) to get current summary statistics
4. Save to: research/alerts/data-monitor_{today's date in YYYY-MM-DD format}.md

Format the output as:
# Data Monitor - {date}

| Dataset | Status | Last Modified | File Size | Row Count |
|---------|--------|--------------|-----------|-----------|
{rows -- Status is CHANGED, STABLE, or MISSING}

## Changed Datasets
{For each CHANGED dataset: include the current summary statistics from sci-data-analysis profile mode}

If no datasets are tracked in any research/projects/*.md file: create the file with "No datasets configured for monitoring."

If a dataset file does not exist at its tracked path: mark as MISSING and note the path.

If sci-data-analysis profiling fails for a dataset: note "Profile failed: {error}" and continue.
