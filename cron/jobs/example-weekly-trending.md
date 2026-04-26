---
name: example-weekly-trending
schedule: every_2h
description: AI automation trending research every 2 hours
model: sonnet
max_budget_usd: 0.75
enabled: false
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context. Read context/SOUL.md for voice.

Task: Research what's trending in AI automation over the last 7 days.
Focus on: Claude Code, n8n workflows, agentic systems, MCP servers.

Use the sci-trending-research skill methodology:
1. Search Reddit for top threads in r/ClaudeAI, r/n8n, r/LocalLLaMA
2. Search X/Twitter for posts about Claude Code and n8n
3. Search web for recent blog posts and announcements

Save the research brief to:
projects/sci-trending-research/weekly-ai-automation_{today's date in YYYY-MM-DD format}.md

Include in the brief:
- Top 5 Reddit discussions with upvote counts and key takeaways
- Top 5 X posts with engagement data
- Key themes and emerging patterns
- 3-5 content angles that could be turned into posts

If web search is unavailable, note the failure and exit without creating the output file.
