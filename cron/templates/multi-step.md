---
name: "morning-kickoff"
time: "09:00"
days: "weekdays"
active: "true"
model: "sonnet"
# notify: "on_finish"
# description: ""
# timeout: "30m"
# retry: "0"
---

<!-- EDIT: This template shows multi-step prompts with multiple skills -->

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context. Read context/SOUL.md for voice.

Do the following in order:

1. Read yesterday's memory file (context/memory/) and note any open threads.

2. Research what's trending in AI automation on Reddit and X over the last 24 hours.
   Focus on Claude Code, agentic workflows, and automation tools.

3. Based on what you find, draft 2 content ideas that connect the trends to our positioning.
   Read research_context/research-profile.md for our angles.

4. Save everything to: projects/ops-cron/morning-kickoff_{today's date in YYYY-MM-DD format}.md

Format the output as:
- **Open threads** from yesterday
- **Trending now** — top 3 items with links
- **Content ideas** — 2 draft angles with hooks

If web search fails, skip the trending section and focus on open threads and content ideas from existing context.
