#!/usr/bin/env python3
"""Fetch full problem data: spec, verifier, leaderboard, solutions, discussions.

Usage:
    python3 fetch_problem.py prime-number-theorem
    python3 fetch_problem.py prime-number-theorem --output-dir ./pnt/
    python3 fetch_problem.py --list   # list all problems
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arena_ops import EinsteinArena


def main():
    parser = argparse.ArgumentParser(description="Fetch Einstein Arena problem data")
    parser.add_argument("slug", nargs="?", help="Problem slug (e.g. prime-number-theorem)")
    parser.add_argument("--list", action="store_true", help="List all problems")
    parser.add_argument("--output-dir", "-o", default=".", help="Output directory")
    parser.add_argument("--creds", help="Credentials file path")
    args = parser.parse_args()

    arena = EinsteinArena(credentials_path=args.creds)

    if args.list:
        problems = arena.list_problems()
        print(f"{'ID':>4} {'Slug':<40} {'Title'}")
        print("-" * 80)
        for p in problems:
            print(f"{p.get('id', '?'):>4} {p.get('slug', '?'):<40} {p.get('title', '?')}")
        return

    if not args.slug:
        parser.error("slug is required (or use --list)")

    data = arena.fetch_all(args.slug, output_dir=args.output_dir)
    prob = data["problem"]

    print(f"\n--- Problem Summary ---")
    print(f"  Title: {prob.get('title', 'N/A')}")
    print(f"  ID: {prob.get('id', 'N/A')}")
    print(f"  Scoring: {prob.get('scoring', 'N/A')}")
    print(f"  Min Improvement: {prob.get('minImprovement', 'N/A')}")
    print(f"  Leaderboard entries: {len(data['leaderboard'])}")
    print(f"  Solutions available: {len(data['solutions'])}")
    print(f"  Discussion threads: {len(data['discussions'])}")


if __name__ == "__main__":
    main()
