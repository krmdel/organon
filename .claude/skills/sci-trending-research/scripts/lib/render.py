"""Output rendering for last30days skill.

Adapted from https://github.com/Ronnie-Nutrition/last30days-skill
"""

import json
from pathlib import Path
from typing import List, Optional

from . import schema

OUTPUT_DIR = Path.home() / ".local" / "share" / "last30days" / "out"


def ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _assess_data_freshness(report: schema.Report) -> dict:
    reddit_recent = sum(1 for r in report.reddit if r.date and r.date >= report.range_from)
    x_recent = sum(1 for x in report.x if x.date and x.date >= report.range_from)
    web_recent = sum(1 for w in report.web if w.date and w.date >= report.range_from)
    total_recent = reddit_recent + x_recent + web_recent
    total_items = len(report.reddit) + len(report.x) + len(report.web)
    return {
        "reddit_recent": reddit_recent,
        "x_recent": x_recent,
        "web_recent": web_recent,
        "total_recent": total_recent,
        "total_items": total_items,
        "is_sparse": total_recent < 5,
        "mostly_evergreen": total_items > 0 and total_recent < total_items * 0.3,
    }


def render_compact(report: schema.Report, limit: int = 15, missing_keys: str = "none") -> str:
    lines = []
    lines.append(f"## Research Results: {report.topic}")
    lines.append("")

    freshness = _assess_data_freshness(report)
    if freshness["is_sparse"]:
        lines.append("**⚠️ LIMITED RECENT DATA** - Few discussions from the last 30 days.")
        lines.append(f"Only {freshness['total_recent']} item(s) confirmed from {report.range_from} to {report.range_to}.")
        lines.append("")

    if report.from_cache:
        age_str = f"{report.cache_age_hours:.1f}h old" if report.cache_age_hours else "cached"
        lines.append(f"**⚡ CACHED RESULTS** ({age_str})")
        lines.append("")

    lines.append(f"**Date Range:** {report.range_from} to {report.range_to}")
    lines.append(f"**Mode:** {report.mode}")
    lines.append("")

    if report.reddit_error:
        lines.append("### Reddit Threads")
        lines.append(f"**ERROR:** {report.reddit_error}")
        lines.append("")
    elif report.reddit:
        lines.append("### Reddit Threads")
        lines.append("")
        for item in report.reddit[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.score is not None:
                    parts.append(f"{eng.score}pts")
                if eng.num_comments is not None:
                    parts.append(f"{eng.num_comments}cmt")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"
            date_str = f" ({item.date})" if item.date else " (date unknown)"
            lines.append(f"**{item.id}** (score:{item.score}) r/{item.subreddit}{date_str}{eng_str}")
            lines.append(f"  {item.title}")
            lines.append(f"  {item.url}")
            lines.append(f"  *{item.why_relevant}*")
            if item.comment_insights:
                lines.append(f"  Insights:")
                for insight in item.comment_insights[:3]:
                    lines.append(f"    - {insight}")
            lines.append("")

    if report.x_error:
        lines.append("### X Posts")
        lines.append(f"**ERROR:** {report.x_error}")
        lines.append("")
    elif report.x:
        lines.append("### X Posts")
        lines.append("")
        for item in report.x[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.likes is not None:
                    parts.append(f"{eng.likes}likes")
                if eng.reposts is not None:
                    parts.append(f"{eng.reposts}rt")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"
            date_str = f" ({item.date})" if item.date else " (date unknown)"
            lines.append(f"**{item.id}** (score:{item.score}) @{item.author_handle}{date_str}{eng_str}")
            lines.append(f"  {item.text[:200]}...")
            lines.append(f"  {item.url}")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    if report.web:
        lines.append("### Web Results")
        lines.append("")
        for item in report.web[:limit]:
            date_str = f" ({item.date})" if item.date else " (date unknown)"
            lines.append(f"**{item.id}** [WEB] (score:{item.score}) {item.source_domain}{date_str}")
            lines.append(f"  {item.title}")
            lines.append(f"  {item.url}")
            lines.append(f"  {item.snippet[:150]}...")
            lines.append("")

    return "\n".join(lines)


def render_context_snippet(report: schema.Report) -> str:
    lines = []
    lines.append(f"# Context: {report.topic} (Last 30 Days)")
    lines.append("")
    lines.append(f"*Generated: {report.generated_at[:10]} | Sources: {report.mode}*")
    lines.append("")
    lines.append("## Key Sources")
    lines.append("")

    all_items = []
    for item in report.reddit[:5]:
        all_items.append((item.score, "Reddit", item.title, item.url))
    for item in report.x[:5]:
        all_items.append((item.score, "X", item.text[:50] + "...", item.url))
    for item in report.web[:5]:
        all_items.append((item.score, "Web", item.title[:50] + "...", item.url))

    all_items.sort(key=lambda x: -x[0])
    for score, source, text, url in all_items[:7]:
        lines.append(f"- [{source}] {text}")
    lines.append("")
    return "\n".join(lines)


def render_full_report(report: schema.Report) -> str:
    lines = []
    lines.append(f"# {report.topic} - Last 30 Days Research Report")
    lines.append("")
    lines.append(f"**Generated:** {report.generated_at}")
    lines.append(f"**Date Range:** {report.range_from} to {report.range_to}")
    lines.append(f"**Mode:** {report.mode}")
    lines.append("")

    if report.reddit:
        lines.append("## Reddit Threads")
        lines.append("")
        for item in report.reddit:
            lines.append(f"### {item.id}: {item.title}")
            lines.append(f"- **Subreddit:** r/{item.subreddit}")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'} (confidence: {item.date_confidence})")
            lines.append(f"- **Score:** {item.score}/100")
            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Engagement:** {eng.score or '?'} points, {eng.num_comments or '?'} comments")
            if item.comment_insights:
                lines.append("**Key Insights:**")
                for insight in item.comment_insights:
                    lines.append(f"- {insight}")
            lines.append("")

    if report.x:
        lines.append("## X Posts")
        lines.append("")
        for item in report.x:
            lines.append(f"### {item.id}: @{item.author_handle}")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'}")
            lines.append(f"- **Score:** {item.score}/100")
            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Engagement:** {eng.likes or '?'} likes, {eng.reposts or '?'} reposts")
            lines.append(f"> {item.text}")
            lines.append("")

    return "\n".join(lines)


def write_outputs(
    report: schema.Report, raw_openai: Optional[dict] = None,
    raw_xai: Optional[dict] = None, raw_reddit_enriched: Optional[list] = None,
):
    ensure_output_dir()
    with open(OUTPUT_DIR / "report.json", 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    with open(OUTPUT_DIR / "report.md", 'w') as f:
        f.write(render_full_report(report))
    with open(OUTPUT_DIR / "last30days.context.md", 'w') as f:
        f.write(render_context_snippet(report))
    if raw_openai:
        with open(OUTPUT_DIR / "raw_openai.json", 'w') as f:
            json.dump(raw_openai, f, indent=2)
    if raw_xai:
        with open(OUTPUT_DIR / "raw_xai.json", 'w') as f:
            json.dump(raw_xai, f, indent=2)
    if raw_reddit_enriched:
        with open(OUTPUT_DIR / "raw_reddit_threads_enriched.json", 'w') as f:
            json.dump(raw_reddit_enriched, f, indent=2)


def get_context_path() -> str:
    return str(OUTPUT_DIR / "last30days.context.md")
