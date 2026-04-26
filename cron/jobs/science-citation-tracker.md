---
name: science-citation-tracker
schedule: every_4h
description: Track citation counts for publications linked to research projects
model: sonnet
max_budget_usd: 0.50
enabled: false
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: Track citation counts for publications linked to research projects.

IMPORTANT: ONLY run on Mondays. Check the current day of the week. If today is NOT Monday, exit immediately with the message: "Not Monday -- skipping citation check." Do not create any output file.

If today IS Monday, proceed:

1. Read all .md files in research/projects/ and find the linked_publications listed in the YAML frontmatter of each project (look for DOIs in the linked_publications field)
2. Find the most recent research/alerts/citation-tracker_*.md file (if it exists) to get the last known citation counts
3. For each DOI found across all projects: use the sci-literature-research skill to search by DOI and get the current citation count
4. Compare the current citation count to the last known count from the previous tracker alert (if available) to calculate the delta
5. Save to: research/alerts/citation-tracker_{today's date in YYYY-MM-DD format}.md

Format the output as:
# Citation Tracker - {date}

| Paper | Current Citations | Change | Source |
|-------|------------------|--------|--------|
{rows -- Change is +N, -N, or "new" if no previous data}

If no linked_publications with DOIs are found in any research/projects/*.md file: create the file with "No publications tracked for citations."

If citation lookup fails for a DOI: note "Lookup failed for {DOI}: {error}" and continue to next DOI.

If no previous tracker file exists: record all counts as "new" with no delta.
