---
name: "Weekly AI Trending"
time: "every_2h"
days: "weekdays"
active: "false"
model: "sonnet"
# notify: "on_finish"
# description: ""
# timeout: "30m"
# retry: "0"
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context. Read context/SOUL.md for voice.

Use the sci-trending-research skill methodology (read .claude/skills/sci-trending-research/SKILL.md for the full approach).

Task: Research what's trending in AI automation over the last 7 days.
Focus on: Claude Code, n8n workflows, agentic systems, MCP servers.

Steps:
1. Search Reddit for top threads in r/ClaudeAI, r/n8n, r/LocalLLaMA
2. Search X/Twitter for posts about Claude Code and n8n
3. Search web for recent blog posts and announcements

Save the research brief to:
projects/sci-trending-research/{today's date in YYYY-MM-DD format}_weekly-ai-automation.md

Include in the brief:
- Top 5 Reddit discussions with upvote counts and key takeaways
- Top 5 X posts with engagement data
- Key themes and emerging patterns
- 3-5 content angles that could be turned into posts

If web search is unavailable, note the failure and exit without creating the output file.
