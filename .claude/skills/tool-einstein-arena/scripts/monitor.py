#!/usr/bin/env python3
"""Monitor evaluation status and agent activity.

Usage:
    python3 monitor.py --solution-id 42
    python3 monitor.py --solution-id 42 --wait
    python3 monitor.py --activity   # list all agent activity
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arena_ops import EinsteinArena


def main():
    parser = argparse.ArgumentParser(description="Monitor Einstein Arena submissions")
    parser.add_argument("--solution-id", type=int, help="Solution ID to check")
    parser.add_argument("--wait", action="store_true",
                        help="Wait for evaluation to complete")
    parser.add_argument("--timeout", type=int, default=1200,
                        help="Wait timeout in seconds (default: 1200)")
    parser.add_argument("--activity", action="store_true",
                        help="List all agent activity")
    parser.add_argument("--creds", help="Credentials file path")
    args = parser.parse_args()

    arena = EinsteinArena(credentials_path=args.creds)

    if args.activity:
        activity = arena.get_my_activity()
        print(json.dumps(activity, indent=2))
        return

    if not args.solution_id:
        parser.error("--solution-id required (or use --activity)")

    if args.wait:
        result = arena.wait_for_evaluation(
            args.solution_id, timeout=args.timeout
        )
    else:
        result = arena.check_submission(args.solution_id)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
