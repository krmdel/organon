#!/usr/bin/env python3
"""Analyze competitor solutions for an Einstein Arena problem.

Usage:
    python3 analyze_competitors.py --problem-id 3 --top 10
    python3 analyze_competitors.py --problem prime-number-theorem
    python3 analyze_competitors.py --problem-id 3 --compare sol1.json sol2.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arena_ops import EinsteinArena


def deep_analysis(solutions: list) -> dict:
    """Detailed cross-solution analysis (requires numpy)."""
    try:
        import numpy as np
    except ImportError:
        return {"error": "numpy not installed — install for deep analysis"}

    results = {"solutions": []}

    for sol in solutions:
        agent = sol.get("agentName", sol.get("agent", {}).get("name", "?"))
        score = sol.get("score")
        solution_data = sol.get("solution", {})

        entry = {"agent": agent, "score": score}

        if "partial_function" in solution_data:
            pf = solution_data["partial_function"]
            keys = sorted(int(k) for k in pf.keys())
            vals = np.array([float(pf[str(k)]) for k in keys])

            entry.update({
                "n_keys": len(keys),
                "key_range": [keys[0], keys[-1]],
                "key_percentiles": {
                    "p25": int(np.percentile(keys, 25)),
                    "p50": int(np.percentile(keys, 50)),
                    "p75": int(np.percentile(keys, 75)),
                },
                "val_stats": {
                    "min": float(vals.min()),
                    "max": float(vals.max()),
                    "mean": float(vals.mean()),
                    "std": float(vals.std()),
                    "positive": int(np.sum(vals > 0)),
                    "negative": int(np.sum(vals < 0)),
                },
                "score_decomposition": {
                    "small_keys_lt100": float(-np.sum(
                        vals[np.array(keys) < 100] *
                        np.log(np.array(keys, dtype=float)[np.array(keys) < 100]) /
                        np.array(keys, dtype=float)[np.array(keys) < 100]
                    )) if any(k < 100 for k in keys) else 0,
                },
            })
        results["solutions"].append(entry)

    # Cross-comparison: shared keys between top solutions
    if len(results["solutions"]) >= 2:
        all_key_sets = []
        for sol in solutions:
            pf = sol.get("solution", {}).get("partial_function", {})
            all_key_sets.append(set(int(k) for k in pf.keys()))

        if len(all_key_sets) >= 2:
            shared = all_key_sets[0] & all_key_sets[1]
            unique_1 = all_key_sets[0] - all_key_sets[1]
            unique_2 = all_key_sets[1] - all_key_sets[0]
            results["cross_comparison"] = {
                "shared_keys": len(shared),
                "unique_to_1": len(unique_1),
                "unique_to_2": len(unique_2),
                "unique_to_1_range": [min(unique_1), max(unique_1)] if unique_1 else [],
                "unique_to_2_range": [min(unique_2), max(unique_2)] if unique_2 else [],
            }

    return results


def main():
    parser = argparse.ArgumentParser(description="Analyze Einstein Arena solutions")
    parser.add_argument("--problem-id", type=int, help="Problem ID (integer)")
    parser.add_argument("--problem", help="Problem slug (will look up ID)")
    parser.add_argument("--top", type=int, default=10, help="Number of solutions")
    parser.add_argument("--compare", nargs="+", help="Local solution files to compare")
    parser.add_argument("--creds", help="Credentials file path")
    parser.add_argument("--output", "-o", help="Save analysis to file")
    args = parser.parse_args()

    arena = EinsteinArena(credentials_path=args.creds)

    # Resolve problem ID
    problem_id = args.problem_id
    if not problem_id and args.problem:
        prob = arena.get_problem(args.problem)
        problem_id = prob["id"]
    if not problem_id:
        parser.error("--problem-id or --problem required")

    # Quick analysis
    quick = arena.analyze_solutions(problem_id, top_n=args.top)
    print(f"Quick Analysis ({quick['count']} solutions):")
    for a in quick["agents"]:
        print(f"  {a['agent']:<20} score={a.get('score', '?'):<20} "
              f"keys={a.get('n_keys', '?')} range={a.get('key_range', '?')}")
    if "gap_1_2" in quick:
        print(f"  Gap #1-#2: {quick['gap_1_2']:.2e}")

    # Deep analysis
    solutions = arena.get_best_solutions(problem_id, limit=args.top)
    deep = deep_analysis(solutions)

    if "cross_comparison" in deep:
        cc = deep["cross_comparison"]
        print(f"\nCross-comparison (#1 vs #2):")
        print(f"  Shared keys: {cc['shared_keys']}")
        print(f"  Unique to #1: {cc['unique_to_1']} (range {cc.get('unique_to_1_range', '?')})")
        print(f"  Unique to #2: {cc['unique_to_2']} (range {cc.get('unique_to_2_range', '?')})")

    if args.output:
        combined = {"quick": quick, "deep": deep}
        Path(args.output).write_text(json.dumps(combined, indent=2))
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
