#!/usr/bin/env python3
"""
last30days - Research a topic from the last 30 days on Reddit + X.

Adapted from https://github.com/Ronnie-Nutrition/last30days-skill

Usage:
    python3 last30days.py <topic> [options]

Options:
    --emit=MODE         Output mode: compact|json|md|context|path (default: compact)
    --sources=MODE      Source selection: auto|reddit|x|both (default: auto)
    --quick             Faster research with fewer sources
    --deep              Comprehensive research with more sources
    --debug             Enable verbose debug logging
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (
    dates, dedupe, env, http, models, normalize,
    openai_reddit, reddit_enrich, render, schema, score, ui, websearch, xai_x,
)


def _search_reddit(topic, config, selected_models, from_date, to_date, depth):
    raw_openai = None
    reddit_error = None
    try:
        raw_openai = openai_reddit.search_reddit(
            config["OPENAI_API_KEY"], selected_models["openai"],
            topic, from_date, to_date, depth=depth,
        )
    except http.HTTPError as e:
        raw_openai = {"error": str(e)}
        reddit_error = f"API error: {e}"
    except Exception as e:
        raw_openai = {"error": str(e)}
        reddit_error = f"{type(e).__name__}: {e}"

    reddit_items = openai_reddit.parse_reddit_response(raw_openai or {})

    if len(reddit_items) < 5 and not reddit_error:
        core = openai_reddit._extract_core_subject(topic)
        if core.lower() != topic.lower():
            try:
                retry_raw = openai_reddit.search_reddit(
                    config["OPENAI_API_KEY"], selected_models["openai"],
                    core, from_date, to_date, depth=depth,
                )
                retry_items = openai_reddit.parse_reddit_response(retry_raw)
                existing_urls = {item.get("url") for item in reddit_items}
                for item in retry_items:
                    if item.get("url") not in existing_urls:
                        reddit_items.append(item)
            except Exception:
                pass

    return reddit_items, raw_openai, reddit_error


def _search_x(topic, config, selected_models, from_date, to_date, depth):
    raw_xai = None
    x_error = None
    try:
        raw_xai = xai_x.search_x(
            config["XAI_API_KEY"], selected_models["xai"],
            topic, from_date, to_date, depth=depth,
        )
    except http.HTTPError as e:
        raw_xai = {"error": str(e)}
        x_error = f"API error: {e}"
    except Exception as e:
        raw_xai = {"error": str(e)}
        x_error = f"{type(e).__name__}: {e}"

    x_items = xai_x.parse_x_response(raw_xai or {})
    return x_items, raw_xai, x_error


def run_research(
    topic, sources, config, selected_models, from_date, to_date,
    depth="default", progress=None,
):
    reddit_items = []
    x_items = []
    raw_openai = None
    raw_xai = None
    raw_reddit_enriched = []
    reddit_error = None
    x_error = None

    web_needed = sources in ("all", "web", "reddit-web", "x-web")

    if sources == "web":
        if progress:
            progress.start_web_only()
            progress.end_web_only()
        return reddit_items, x_items, True, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error

    run_reddit = sources in ("both", "reddit", "all", "reddit-web")
    run_x = sources in ("both", "x", "all", "x-web")

    reddit_future = None
    x_future = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        if run_reddit:
            if progress:
                progress.start_reddit()
            reddit_future = executor.submit(
                _search_reddit, topic, config, selected_models, from_date, to_date, depth
            )
        if run_x:
            if progress:
                progress.start_x()
            x_future = executor.submit(
                _search_x, topic, config, selected_models, from_date, to_date, depth
            )

        if reddit_future:
            try:
                reddit_items, raw_openai, reddit_error = reddit_future.result()
                if reddit_error and progress:
                    progress.show_error(f"Reddit error: {reddit_error}")
            except Exception as e:
                reddit_error = f"{type(e).__name__}: {e}"
                if progress:
                    progress.show_error(f"Reddit error: {e}")
            if progress:
                progress.end_reddit(len(reddit_items))

        if x_future:
            try:
                x_items, raw_xai, x_error = x_future.result()
                if x_error and progress:
                    progress.show_error(f"X error: {x_error}")
            except Exception as e:
                x_error = f"{type(e).__name__}: {e}"
                if progress:
                    progress.show_error(f"X error: {e}")
            if progress:
                progress.end_x(len(x_items))

    if reddit_items:
        if progress:
            progress.start_reddit_enrich(1, len(reddit_items))
        for i, item in enumerate(reddit_items):
            if progress and i > 0:
                progress.update_reddit_enrich(i + 1, len(reddit_items))
            try:
                reddit_items[i] = reddit_enrich.enrich_reddit_item(item)
            except Exception as e:
                if progress:
                    progress.show_error(f"Enrich failed for {item.get('url', 'unknown')}: {e}")
            raw_reddit_enriched.append(reddit_items[i])
        if progress:
            progress.end_reddit_enrich()

    return reddit_items, x_items, web_needed, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error


def main():
    parser = argparse.ArgumentParser(description="Research a topic from the last 30 days on Reddit + X")
    parser.add_argument("topic", nargs="?", help="Topic to research")
    parser.add_argument("--emit", choices=["compact", "json", "md", "context", "path"], default="compact")
    parser.add_argument("--sources", choices=["auto", "reddit", "x", "both"], default="auto")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--include-web", action="store_true")

    args = parser.parse_args()

    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"
        from lib import http as http_module
        http_module.DEBUG = True

    if args.quick and args.deep:
        print("Error: Cannot use both --quick and --deep", file=sys.stderr)
        sys.exit(1)

    depth = "quick" if args.quick else "deep" if args.deep else "default"

    if not args.topic:
        print("Error: Please provide a topic to research.", file=sys.stderr)
        sys.exit(1)

    config = env.get_config()
    available = env.get_available_sources(config)

    sources, error = env.validate_sources(args.sources, available, args.include_web)
    if error:
        if "WebSearch fallback" in error or "No API keys" in error:
            print(f"Note: {error}", file=sys.stderr)
        else:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)

    from_date, to_date = dates.get_date_range(30)
    missing_keys = env.get_missing_keys(config)

    progress = ui.ProgressDisplay(args.topic, show_banner=True)
    if missing_keys != 'none':
        progress.show_promo(missing_keys)

    selected_models = models.get_models(config)

    mode_map = {
        "all": "all", "both": "both", "reddit": "reddit-only",
        "reddit-web": "reddit-web", "x": "x-only", "x-web": "x-web", "web": "web-only",
    }
    mode = mode_map.get(sources, sources)

    reddit_items, x_items, web_needed, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error = run_research(
        args.topic, sources, config, selected_models, from_date, to_date, depth, progress,
    )

    progress.start_processing()

    normalized_reddit = normalize.normalize_reddit_items(reddit_items, from_date, to_date)
    normalized_x = normalize.normalize_x_items(x_items, from_date, to_date)

    filtered_reddit = normalize.filter_by_date_range(normalized_reddit, from_date, to_date)
    filtered_x = normalize.filter_by_date_range(normalized_x, from_date, to_date)

    scored_reddit = score.score_reddit_items(filtered_reddit)
    scored_x = score.score_x_items(filtered_x)

    sorted_reddit = score.sort_items(scored_reddit)
    sorted_x = score.sort_items(scored_x)

    deduped_reddit = dedupe.dedupe_reddit(sorted_reddit)
    deduped_x = dedupe.dedupe_x(sorted_x)

    progress.end_processing()

    report = schema.create_report(args.topic, from_date, to_date, mode, selected_models.get("openai"), selected_models.get("xai"))
    report.reddit = deduped_reddit
    report.x = deduped_x
    report.reddit_error = reddit_error
    report.x_error = x_error
    report.context_snippet_md = render.render_context_snippet(report)

    render.write_outputs(report, raw_openai, raw_xai, raw_reddit_enriched)

    if sources == "web":
        progress.show_web_only_complete()
    else:
        progress.show_complete(len(deduped_reddit), len(deduped_x))

    if args.emit == "compact":
        print(render.render_compact(report, missing_keys=missing_keys))
    elif args.emit == "json":
        print(json.dumps(report.to_dict(), indent=2))
    elif args.emit == "md":
        print(render.render_full_report(report))
    elif args.emit == "context":
        print(report.context_snippet_md)
    elif args.emit == "path":
        print(render.get_context_path())

    if web_needed:
        print("\n" + "="*60)
        print("### WEBSEARCH REQUIRED ###")
        print("="*60)
        print(f"Topic: {args.topic}")
        print(f"Date range: {from_date} to {to_date}")
        print("Claude: Use WebSearch to find 8-15 relevant web pages.")
        print("EXCLUDE: reddit.com, x.com, twitter.com")
        print("INCLUDE: blogs, docs, news, tutorials from the last 30 days")
        print("="*60)


if __name__ == "__main__":
    main()
