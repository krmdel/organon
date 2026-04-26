#!/usr/bin/env python3
"""tool-arena-runner — single entry point for Einstein Arena campaigns.

Composes Organon skills into one CLI:
    # Precision polish
    polish     -> dispatches to ops-ulp-polish/scripts/polish.py with arena defaults
    tri-verify -> runs three independent verification methods (float64 + mpmath + extra)
    recon      -> bootstraps a new arena project directory (PLAYBOOK.md + NOTES.md)

    # API operations (delegated to tool-einstein-arena scripts)
    fetch      -> fetch problem spec, verifier, leaderboard, solutions, discussions
    register   -> register a new agent (proof-of-work challenge)
    analyze    -> analyze competitor solutions for a problem
    submit     -> submit a solution with optional local pre-verification
    monitor    -> check evaluation status or list agent activity
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Repo-relative paths resolved from this file.
SKILL_DIR = Path(__file__).resolve().parent.parent                  # .../tool-arena-runner
SKILLS_ROOT = SKILL_DIR.parent                                       # .../.claude/skills
OPS_ULP_POLISH_SCRIPT = SKILLS_ROOT / "ops-ulp-polish" / "scripts" / "polish.py"
ARENA_SKILL_DIR = SKILLS_ROOT / "tool-einstein-arena"
ARENA_SCRIPTS_DIR = ARENA_SKILL_DIR / "scripts"
PLAYBOOK_TEMPLATE = ARENA_SKILL_DIR / "assets" / "playbook-template.md"


# ---------------------------------------------------------------------------
# Subcommand: polish
# ---------------------------------------------------------------------------

def _build_polish_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="arena-runner polish",
        description=(
            "Dispatch to ops-ulp-polish with arena-problem defaults "
            "(warm-start from solutions/best.json, 3600s budget)."
        ),
    )
    p.add_argument("--project-dir", required=True,
                   help="Arena project directory containing solutions/best.json + evaluator.py")
    p.add_argument("--config", default=None,
                   help="Warm-start config path (default: {project-dir}/solutions/best.json)")
    p.add_argument("--evaluator", required=True,
                   help="Evaluator spec, e.g. 'evaluator:eval_fn'")
    p.add_argument("--max-ulps", type=int, default=4)
    p.add_argument("--max-sweeps", type=int, default=20)
    p.add_argument("--budget-sec", type=float, default=3600.0)
    p.add_argument("--out", default=None,
                   help="Output path (default: {project-dir}/solutions/polished.json)")
    return p


def cmd_polish(argv: list[str]) -> int:
    args = _build_polish_parser().parse_args(argv)
    project = Path(args.project_dir).resolve()

    config = Path(args.config).resolve() if args.config else (project / "solutions" / "best.json")
    if not config.is_file():
        print(
            f"[arena-runner] ERROR: warm-start file not found: {config}\n"
            f"               Expected solutions/best.json under {project} "
            f"or --config <path>.",
            file=sys.stderr,
        )
        return 2

    if not OPS_ULP_POLISH_SCRIPT.is_file():
        print(
            f"[arena-runner] ERROR: ops-ulp-polish script not found at "
            f"{OPS_ULP_POLISH_SCRIPT}\n"
            f"               Install the ops-ulp-polish skill or check PATH.",
            file=sys.stderr,
        )
        return 3

    out = Path(args.out).resolve() if args.out else (project / "solutions" / "polished.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(OPS_ULP_POLISH_SCRIPT),
        "--config", str(config),
        "--evaluator", args.evaluator,
        "--max-ulps", str(args.max_ulps),
        "--max-sweeps", str(args.max_sweeps),
        "--budget-sec", str(args.budget_sec),
        "--out", str(out),
    ]

    print(f"[arena-runner] polish -> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(project))
    return int(result.returncode or 0)


# ---------------------------------------------------------------------------
# Subcommand: tri-verify
# ---------------------------------------------------------------------------

def _build_tri_verify_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="arena-runner tri-verify",
        description="Run three independent verifications on a solution file.",
    )
    p.add_argument("--solution", required=True, help="Path to the solution JSON file")
    p.add_argument("--verifier", required=True,
                   help="Verifier spec 'module:fn'; the module is expected to expose "
                        "float_score / mpmath_score / extra_score callables")
    p.add_argument("--tolerance", type=float, default=1e-9)
    return p


def cmd_tri_verify(argv: list[str]) -> int:
    import importlib
    import json

    from tri_verify import tri_verify  # type: ignore

    args = _build_tri_verify_parser().parse_args(argv)
    sol_path = Path(args.solution).resolve()
    if not sol_path.is_file():
        print(f"[arena-runner] ERROR: solution file not found: {sol_path}", file=sys.stderr)
        return 2

    mod_path, _, _ = args.verifier.partition(":")
    try:
        mod = importlib.import_module(mod_path)
    except Exception as exc:  # pragma: no cover - user module failures
        print(f"[arena-runner] ERROR: cannot import verifier module {mod_path!r}: {exc}",
              file=sys.stderr)
        return 2

    with open(sol_path) as f:
        solution = json.load(f)

    float_fn = getattr(mod, "float_score", None)
    mpmath_fn = getattr(mod, "mpmath_score", None)
    extra_fn = getattr(mod, "extra_score", None)

    def _wrap(fn):
        if fn is None:
            return None
        return lambda: fn(solution)

    result = tri_verify(
        _wrap(float_fn), _wrap(mpmath_fn), _wrap(extra_fn),
        tolerance=args.tolerance,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "pass" else 1


# ---------------------------------------------------------------------------
# Subcommand: recon
# ---------------------------------------------------------------------------

def _build_recon_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="arena-runner recon",
        description="Bootstrap a new arena project directory (PLAYBOOK.md + NOTES.md).",
    )
    p.add_argument("--slug", required=True, help="Arena problem slug, e.g. 'difference-bases'")
    p.add_argument("--project-dir", required=True, help="Target project directory")
    p.add_argument("--template", default=str(PLAYBOOK_TEMPLATE),
                   help="Playbook template path (defaults to tool-einstein-arena asset)")
    return p


def cmd_recon(argv: list[str]) -> int:
    from recon import recon  # type: ignore

    args = _build_recon_parser().parse_args(argv)
    try:
        recon(
            slug=args.slug,
            project_dir=Path(args.project_dir),
            template_path=Path(args.template),
        )
    except FileNotFoundError as exc:
        print(f"[arena-runner] ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


# ---------------------------------------------------------------------------
# API subcommands (delegated to tool-einstein-arena scripts)
# ---------------------------------------------------------------------------

def _dispatch_arena_script(script_name: str, argv: list[str]) -> int:
    script = ARENA_SCRIPTS_DIR / script_name
    if not script.is_file():
        print(
            f"[arena-runner] ERROR: arena script not found: {script}\n"
            f"               Ensure tool-einstein-arena skill is installed.",
            file=sys.stderr,
        )
        return 3
    result = subprocess.run([sys.executable, str(script)] + argv)
    return int(result.returncode or 0)


def cmd_fetch(argv: list[str]) -> int:
    """Fetch problem spec, verifier, leaderboard, solutions, discussions."""
    return _dispatch_arena_script("fetch_problem.py", argv)


def cmd_register(argv: list[str]) -> int:
    """Register a new agent via proof-of-work challenge."""
    return _dispatch_arena_script("register.py", argv)


def cmd_analyze(argv: list[str]) -> int:
    """Analyze competitor solutions for a problem."""
    return _dispatch_arena_script("analyze_competitors.py", argv)


def cmd_submit(argv: list[str]) -> int:
    """Submit a solution with optional local pre-verification."""
    return _dispatch_arena_script("submit.py", argv)


def cmd_monitor(argv: list[str]) -> int:
    """Check evaluation status or list agent activity."""
    return _dispatch_arena_script("monitor.py", argv)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

# Name -> module attribute name (looked up lazily via globals() so that
# tests monkey-patching `arena_runner.cmd_polish` (etc.) are honoured).
SUBCOMMANDS = {
    "polish": "cmd_polish",
    "tri-verify": "cmd_tri_verify",
    "recon": "cmd_recon",
    "fetch": "cmd_fetch",
    "register": "cmd_register",
    "analyze": "cmd_analyze",
    "submit": "cmd_submit",
    "monitor": "cmd_monitor",
}


def _build_top_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="arena-runner",
        description=(
            "Single entry point for Einstein Arena campaigns.\n"
            "Precision: polish | tri-verify | recon\n"
            "API ops:   fetch | register | analyze | submit | monitor"
        ),
    )
    p.add_argument("subcommand", choices=list(SUBCOMMANDS.keys()),
                   help="polish | tri-verify | recon | fetch | register | analyze | submit | monitor")
    p.add_argument("rest", nargs=argparse.REMAINDER, help="arguments forwarded to the subcommand")
    return p


def run(subcommand: str, argv: list[str]) -> int:
    """Testable entry point. Returns the subcommand's exit code."""
    # argparse.ArgumentParser.exit(2, ...) raises SystemExit(2) on unknown sub.
    if subcommand not in SUBCOMMANDS:
        parser = _build_top_parser()
        parser.error(f"unknown subcommand: {subcommand!r} (expected one of "
                     f"{sorted(SUBCOMMANDS)})")
    # Look up via the module's globals so tests can monkey-patch the command
    # functions (e.g. patch.object(arena_runner, 'cmd_polish', ...)).
    fn = globals()[SUBCOMMANDS[subcommand]]
    rc = fn(argv)
    return int(rc or 0)


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in {"-h", "--help"}:
        # Show a top-level help that mentions every subcommand.
        _build_top_parser().print_help()
        return 0
    subcommand, rest = argv[0], argv[1:]
    return run(subcommand, rest)


if __name__ == "__main__":
    sys.exit(main())
