---
name: science-paper-alerts
schedule: every_4h
description: Check for new papers matching saved research queries
model: sonnet
max_budget_usd: 0.50
enabled: false
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Read research_context/research-profile.md for research interests and field.

Task: Search for new papers published in the last 24 hours matching the scientist's research interests.

For each research interest or topic listed in research_context/research-profile.md:
1. Use the sci-literature-research skill (search mode) with source "all" and max_results 5
2. Filter results to papers published in the last 24 hours where possible
3. For each paper found, include: title, authors, journal, DOI, and a 1-sentence summary

Save the results to: research/alerts/paper-alert_{today's date in YYYY-MM-DD format}.md

Format the output as:
# Paper Alerts - {date}

## {Research Interest/Topic}
- **{Title}** -- {Authors} -- {Journal} -- DOI: {DOI}
  {1-sentence summary}

If no new papers are found for a topic: note "No new papers found for this topic in the last 24 hours."

If search fails for a topic: log "Search failed for {topic}: {error}" and continue to next topic.

If all searches fail: create the alert file with a brief error summary and exit.
