#!/usr/bin/env python3
"""Submit a solution to Einstein Arena with local pre-verification.

Usage:
    python3 submit.py --problem prime-number-theorem --solution solution.json
    python3 submit.py --problem prime-number-theorem --solution solution.json --evaluator evaluator.py
    python3 submit.py --problem prime-number-theorem --solution solution.json --no-verify
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arena_ops import EinsteinArena


def load_evaluator(evaluator_path: str):
    """Dynamically load an evaluator module."""
    spec = importlib.util.spec_from_file_location("evaluator", evaluator_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.evaluate


def main():
    parser = argparse.ArgumentParser(description="Submit solution to Einstein Arena")
    parser.add_argument("--problem", "-p", required=True, help="Problem slug")
    parser.add_argument("--solution", "-s", required=True, help="Solution JSON file")
    parser.add_argument("--evaluator", "-e", help="Local evaluator.py path")
    parser.add_argument("--no-verify", action="store_true", help="Skip local verification")
    parser.add_argument("--creds", help="Credentials file path")
    parser.add_argument("--wait", action="store_true", help="Wait for evaluation result")
    args = parser.parse_args()

    arena = EinsteinArena(credentials_path=args.creds)

    # Load solution
    with open(args.solution) as f:
        solution = json.load(f)
    print(f"Solution loaded from {args.solution}")

    # Get problem ID
    prob = arena.get_problem(args.problem)
    problem_id = prob["id"]
    print(f"Problem: {prob.get('title', args.problem)} (ID={problem_id})")

    # Local verification
    evaluator_fn = None
    if not args.no_verify and args.evaluator:
        evaluator_fn = load_evaluator(args.evaluator)
        local_score = evaluator_fn(solution)
        print(f"Local score: {local_score}")
        if local_score == float("-inf"):
            print("CONSTRAINT VIOLATION — aborting.")
            sys.exit(1)

        # Compare with leaderboard
        comparison = arena.compare_with_leaderboard(local_score, problem_id)
        print(f"Would rank: #{comparison['rank']}/{comparison['total']}")
        print(f"Gap to #1: {comparison['gap_to_best']:+.2e}")
        if comparison["is_new_best"]:
            print("*** NEW #1! ***")

    # Submit
    result = arena.submit(problem_id, solution,
                          verify_locally=False)  # already verified above

    if args.wait and "id" in result:
        print(f"\nWaiting for evaluation...")
        final = arena.wait_for_evaluation(result["id"])
        print(f"Final: {json.dumps(final, indent=2)}")


if __name__ == "__main__":
    main()
