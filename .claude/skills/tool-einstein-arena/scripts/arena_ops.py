#!/usr/bin/env python3
"""Unified interface to Einstein Arena API.

Usage:
    from arena_ops import EinsteinArena
    arena = EinsteinArena()
    problems = arena.list_problems()
    problem = arena.get_problem("prime-number-theorem")
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://einsteinarena.com"

# Default credentials location: projects/tool-einstein-arena/.credentials.json (repo root)
_SCRIPT_DIR = Path(__file__).resolve().parent
# Walk up until we find a dir containing `projects/` (the repo root)
def _find_repo_root(p: Path) -> Path:
    cur = p
    for _ in range(10):
        if (cur / "CLAUDE.md").is_file() and (cur / ".claude").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    # fallback: 4 levels up from scripts dir
    return p.parents[3] if len(p.parents) > 3 else p.parent

_REPO_ROOT = _find_repo_root(_SCRIPT_DIR)
_DEFAULT_CREDS = _REPO_ROOT / "projects" / "tool-einstein-arena" / ".credentials.json"


class EinsteinArena:
    """Unified interface to Einstein Arena API."""

    def __init__(self, credentials_path: Optional[str] = None):
        """Load credentials from file or env var EINSTEIN_ARENA_API_KEY."""
        self.base = BASE_URL
        self.api_key = None
        self.agent_name = None
        self.agent_id = None

        # Try env var first
        if os.environ.get("EINSTEIN_ARENA_API_KEY"):
            self.api_key = os.environ["EINSTEIN_ARENA_API_KEY"]
            return

        # Try credentials file
        creds_path = Path(credentials_path) if credentials_path else _DEFAULT_CREDS
        if creds_path.exists():
            with open(creds_path) as f:
                creds = json.load(f)
            self.api_key = creds.get("api_key")
            self.agent_name = creds.get("name")
            self.agent_id = creds.get("id")

    @property
    def _headers(self) -> dict:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def _require_auth(self):
        if not self.api_key:
            raise RuntimeError(
                "No API key. Register first with arena.register('AgentName') "
                "or set EINSTEIN_ARENA_API_KEY env var."
            )

    def _get(self, path: str, params: Optional[dict] = None,
             auth: bool = False) -> dict:
        if auth:
            self._require_auth()
        headers = self._headers if auth else {}
        resp = requests.get(f"{self.base}{path}", params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json_data: dict, auth: bool = False) -> dict:
        if auth:
            self._require_auth()
        headers = self._headers if auth else {}
        resp = requests.post(f"{self.base}{path}", json=json_data, headers=headers)
        resp.raise_for_status()
        return resp.json()

    # ─── Registration ─────────────────────────────────────────────

    def register(self, agent_name: str,
                 save_path: Optional[str] = None) -> dict:
        """Request challenge, solve PoW, register agent, save credentials."""
        print(f"[1/3] Requesting challenge for '{agent_name}'...")
        data = self._post("/api/agents/challenge", {"name": agent_name})
        challenge = data["challenge"]
        difficulty = data["difficulty"]
        print(f"  Challenge: {challenge[:20]}... ({difficulty} bits)")

        print(f"[2/3] Solving proof-of-work...")
        nonce = self._solve_pow(challenge, difficulty)

        print(f"[3/3] Registering agent...")
        result = self._post("/api/agents/register", {
            "name": agent_name,
            "challenge": challenge,
            "nonce": nonce,
        })

        agent = result["agent"]
        self.api_key = agent["api_key"]
        self.agent_name = agent_name
        self.agent_id = agent.get("id")

        creds = {
            "name": agent_name,
            "id": self.agent_id,
            "api_key": self.api_key,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        out_path = Path(save_path) if save_path else _DEFAULT_CREDS
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(creds, f, indent=2)

        print(f"  Registered! ID={self.agent_id}")
        print(f"  Credentials saved to {out_path}")
        return creds

    @staticmethod
    def _solve_pow(challenge: str, difficulty: int) -> int:
        zeros = difficulty // 4
        extra = difficulty % 4
        nonce = 0
        t0 = time.time()
        while True:
            h = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
            if h[:zeros] == "0" * zeros and (
                extra == 0 or int(h[zeros], 16) < (16 >> extra)
            ):
                print(f"  Solved in {time.time() - t0:.1f}s (nonce={nonce})")
                return nonce
            nonce += 1
            if nonce % 1_000_000 == 0:
                print(f"  ... {nonce // 1_000_000}M nonces ({time.time() - t0:.0f}s)")

    # ─── Problem Discovery ────────────────────────────────────────

    def list_problems(self) -> list:
        """List all problems with stats."""
        return self._get("/api/problems")

    def get_problem(self, slug: str) -> dict:
        """Full problem spec: description, scoring, verifier, solutionSchema."""
        return self._get(f"/api/problems/{slug}")

    def save_verifier(self, slug: str, path: str):
        """Extract and save evaluator.py from problem spec."""
        prob = self.get_problem(slug)
        if "verifier" not in prob:
            raise ValueError(f"No verifier found for '{slug}'")
        Path(path).write_text(prob["verifier"])
        print(f"Verifier saved to {path} ({len(prob['verifier'])} chars)")

    # ─── Leaderboard & Solutions ──────────────────────────────────

    def get_leaderboard(self, problem_id: int, limit: int = 20) -> list:
        """Ranked agents with scores and submission counts."""
        return self._get("/api/leaderboard",
                         params={"problem_id": problem_id, "limit": limit})

    def get_best_solutions(self, problem_id: int, limit: int = 20) -> list:
        """Actual solution data from top agents."""
        return self._get("/api/solutions/best",
                         params={"problem_id": problem_id, "limit": limit})

    def analyze_solutions(self, problem_id: int, top_n: int = 10) -> dict:
        """Statistical analysis of top solutions: key ranges, value distributions."""
        solutions = self.get_best_solutions(problem_id, limit=top_n)
        if not solutions:
            return {"error": "No solutions found"}

        analysis = {
            "count": len(solutions),
            "agents": [],
        }

        for sol in solutions:
            agent_info = {
                "agent": sol.get("agentName", sol.get("agent", {}).get("name", "?")),
                "score": sol.get("score"),
            }

            solution_data = sol.get("solution", {})
            if "partial_function" in solution_data:
                pf = solution_data["partial_function"]
                keys = sorted(int(k) for k in pf.keys())
                vals = [float(pf[str(k)]) for k in keys]
                agent_info.update({
                    "n_keys": len(keys),
                    "key_range": [keys[0], keys[-1]] if keys else [],
                    "val_range": [min(vals), max(vals)] if vals else [],
                    "val_mean": sum(vals) / len(vals) if vals else 0,
                })
            analysis["agents"].append(agent_info)

        # Cross-solution comparison
        if len(analysis["agents"]) >= 2:
            a1, a2 = analysis["agents"][0], analysis["agents"][1]
            if a1.get("score") and a2.get("score"):
                analysis["gap_1_2"] = a1["score"] - a2["score"]

        return analysis

    # ─── Discussions ──────────────────────────────────────────────

    def get_threads(self, slug: str, sort: str = "top",
                    limit: int = 50) -> list:
        """All discussion threads with metadata."""
        return self._get(f"/api/problems/{slug}/threads",
                         params={"sort": sort, "limit": limit})

    def get_thread_with_replies(self, thread_id: int) -> dict:
        """Full thread content plus all replies."""
        return self._get(f"/api/threads/{thread_id}")

    def post_thread(self, slug: str, title: str, body: str) -> dict:
        """Create new discussion thread (enters moderation queue)."""
        return self._post(f"/api/problems/{slug}/threads",
                          {"title": title, "body": body}, auth=True)

    def post_reply(self, thread_id: int, body: str) -> dict:
        """Reply to thread."""
        return self._post(f"/api/threads/{thread_id}/replies",
                          {"body": body}, auth=True)

    # ─── Submission ───────────────────────────────────────────────

    def submit(self, problem_id: int, solution: dict,
               verify_locally: bool = True,
               evaluator_fn=None) -> dict:
        """Submit solution. Optionally verify with local evaluator first.

        Args:
            problem_id: Problem ID (integer).
            solution: Solution dict (e.g. {"partial_function": {...}}).
            verify_locally: Run local evaluator before submitting.
            evaluator_fn: callable(solution) -> float. If None, skips local check.

        Returns:
            API response with solution ID.
        """
        self._require_auth()

        if verify_locally and evaluator_fn:
            local_score = evaluator_fn(solution)
            print(f"  Local score: {local_score}")
            if local_score == float("-inf"):
                raise ValueError("CONSTRAINT VIOLATION — not submitting.")

        resp = self._post("/api/solutions", {
            "problem_id": problem_id,
            "solution": solution,
        }, auth=True)

        print(f"  Submitted! Solution ID: {resp.get('id')}")
        return resp

    def check_submission(self, solution_id: int) -> dict:
        """Check evaluation status and score."""
        return self._get(f"/api/solutions/{solution_id}", auth=True)

    def wait_for_evaluation(self, solution_id: int,
                            timeout: int = 1200,
                            poll_interval: int = 60) -> dict:
        """Poll until evaluated, return final status."""
        self._require_auth()
        t0 = time.time()
        while time.time() - t0 < timeout:
            status = self.check_submission(solution_id)
            state = status.get("status", "unknown")
            if state in ("evaluated", "scored", "completed", "failed", "error"):
                print(f"  Evaluation complete: {state}")
                return status
            elapsed = time.time() - t0
            print(f"  Status: {state} ({elapsed:.0f}s elapsed, "
                  f"next check in {poll_interval}s)")
            time.sleep(poll_interval)

        raise TimeoutError(
            f"Evaluation not complete after {timeout}s for solution {solution_id}"
        )

    # ─── Agent Activity ───────────────────────────────────────────

    def get_my_activity(self, statuses: Optional[list] = None) -> list:
        """All submissions and threads by this agent."""
        params = {}
        if statuses:
            params["statuses"] = ",".join(statuses)
        return self._get("/api/agents/activity", params=params, auth=True)

    # ─── Utilities ────────────────────────────────────────────────

    def compare_with_leaderboard(self, local_score: float,
                                  problem_id: int) -> dict:
        """Where would this score rank? Gap to #1? Beats minImprovement?"""
        lb = self.get_leaderboard(problem_id)
        if not lb:
            return {"rank": 1, "total": 0, "is_new_best": True}

        scores = [entry.get("score", 0) for entry in lb]
        rank = sum(1 for s in scores if s >= local_score) + 1
        best = max(scores) if scores else 0
        gap = local_score - best
        min_improvement = 1e-5  # typical threshold

        return {
            "rank": rank,
            "total": len(lb),
            "best_score": best,
            "gap_to_best": gap,
            "beats_best": gap > min_improvement,
            "min_improvement": min_improvement,
            "is_new_best": rank == 1 and gap > min_improvement,
        }

    def fetch_all(self, slug: str, output_dir: str = ".") -> dict:
        """Fetch everything for a problem: spec, verifier, leaderboard,
        solutions, discussions. Save to output_dir."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        prob = self.get_problem(slug)
        (out / "problem.json").write_text(json.dumps(prob, indent=2))

        if "verifier" in prob:
            (out / "evaluator.py").write_text(prob["verifier"])

        problem_id = prob["id"]

        lb = self.get_leaderboard(problem_id)
        (out / "leaderboard.json").write_text(json.dumps(lb, indent=2))

        sols = self.get_best_solutions(problem_id)
        (out / "best_solutions.json").write_text(json.dumps(sols, indent=2))

        threads = self.get_threads(slug)
        (out / "discussions.json").write_text(json.dumps(threads, indent=2))

        print(f"Fetched all data for '{slug}' to {out.resolve()}")
        return {
            "problem": prob,
            "leaderboard": lb,
            "solutions": sols,
            "discussions": threads,
        }
