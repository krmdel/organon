"""Orchestrator state machine for the single-auditor review pipeline.

Used by `sci-communication` and `sci-writing` review mode. The actual
subagent spawning happens in Claude's skill loop via the Agent tool —
this script's job is to set up state, run verify_ops.py, and read the
auditor's structured JSON report.

CLI subcommands (all emit JSON to stdout):

  init <category> <slug> [--force]   create workspace + state file
  gate <category> <slug>             run verify_ops.py on {slug}.md
  retry-check <category> <slug>      read {slug}-audit.json, decide retry
  finalize <category> <slug>         confirm save is allowed
  status <category> <slug>           dump current state

Tier 2 invariants (same contract as paper_pipeline):
  * Phase preconditions enforced per command.
  * phase='refused' is terminal.
  * Audit report is {slug}-audit.json with a nonce echoing state.nonce.
  * init refuses re-init without --force (appends to ledger).
  * State writes are atomic.

Exit codes: 0 ok, 1 error, 2 blocked (revise/retry), 3 refused.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# WG2 (Phase 9): citation marker pattern aligned with verify_ops.BROAD_MARKER_RE.
# A bare `"[@" in text` substring check matched literal `[@` in code blocks
# or pseudo-syntax that verify_ops would NOT flag, so a draft could be
# refused by the auditor pipeline yet pass verify_ops, or vice versa. Pin
# the patterns together so the gate's preconditions and the verifier's
# detection agree on what counts as a citation.
_BROAD_MARKER_RE = re.compile(r"\[@[A-Za-z][A-Za-z0-9_-]*")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
VERIFY_OPS = PROJECT_ROOT / ".claude/skills/sci-writing/scripts/verify_ops.py"

# Per-category retry budget for the auditor cascade. sci-communication
# blogs/tutorials cite more loosely than formal manuscripts and benefit
# from a second chance when the auditor catches a subtle claim/quote
# mismatch that the writer can patch without re-running research.
# sci-writing review mode stays at 1 because the full paper cascade
# (paper_pipeline) is the primary integrity loop; this auditor is a
# lighter second opinion on an already-vetted draft.
MAX_RETRIES = 1  # legacy default, retained for back-compat
MAX_RETRIES_BY_CATEGORY = {
    "sci-communication": 2,
    "sci-writing": 1,
}
ALLOWED_CATEGORIES = {"sci-communication", "sci-writing"}

ALLOWED_TRANSITIONS = {
    "gate": {"init", "retry"},
    "retry-check": {"gated"},
    "finalize": {"audited"},
    "post-humanize": {"finalized"},
    "status": None,
}

VALID_AUDIT_VERDICTS = {"ship", "revise", "refuse"}


# ============================================================
# Errors
# ============================================================


class PipelineError(RuntimeError):
    pass


class ForgeryError(PipelineError):
    pass


# ============================================================
# State
# ============================================================


def _new_nonce() -> str:
    return uuid.uuid4().hex


@dataclass
class PipelineState:
    pipeline: str = "auditor"
    category: str = ""
    slug: str = ""
    phase: str = "init"
    nonce: str = field(default_factory=_new_nonce)
    retry_count: int = 0
    max_retries: int = MAX_RETRIES
    mechanical_exits: list[int] = field(default_factory=list)
    audit_verdicts: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    # Records whether the most recent mechanical gate (verify_ops) passed or
    # was blocked by CRITICAL findings (exit 2). finalize checks this so a
    # draft that the mechanical gate blocked can never be saved even if the
    # AI auditor verdict is "ship".
    last_gate_status: str = "unknown"
    # C2: humanize lock. Set by cmd_finalize, cleared by cmd_post_humanize
    # on a pass. While the lock is set, verify_gate.py refuses any
    # Write/Edit on {slug}.md — the conductor must run post-humanize
    # first (or explicitly clear the lock via init --force). This
    # closes the gap where a humanizer pass could silently break the
    # verbatim quote contract and ship because the conductor forgot to
    # call post-humanize.
    humanize_lock: bool = False
    finalized_at: Optional[str] = None

    def log(self, event: str, **kwargs) -> None:
        self.history.append(
            {
                "event": event,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                **kwargs,
            }
        )


def workspace(category: str, slug: str) -> Path:
    return PROJECT_ROOT / "projects" / category / slug


def state_path(category: str, slug: str) -> Path:
    return workspace(category, slug) / ".pipeline_state.json"


def load_state(category: str, slug: str) -> PipelineState:
    p = state_path(category, slug)
    if not p.exists():
        raise FileNotFoundError(
            f"No pipeline state for {category}/{slug}. Run `init` first."
        )
    data = json.loads(p.read_text())
    return PipelineState(**data)


def save_state(state: PipelineState) -> None:
    p = state_path(state.category, state.slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def _require_phase(state: PipelineState, command: str) -> None:
    if state.phase == "refused":
        raise PipelineError(
            f"pipeline refused — terminal state; '{command}' rejected. "
            "Only `status` may run from refused."
        )
    allowed = ALLOWED_TRANSITIONS.get(command)
    if allowed is None:
        return
    if state.phase not in allowed:
        raise PipelineError(
            f"'{command}' cannot run from phase='{state.phase}'. "
            f"Expected one of {sorted(allowed)}."
        )


# ============================================================
# Ledger
# ============================================================


def _ledger_path() -> Path:
    env = os.environ.get("SCI_OS_LEDGER")
    if env:
        return Path(env)
    return Path.home() / ".scientific-os" / "pipeline-ledger.jsonl"


def _append_ledger(event: dict) -> None:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **event,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


# ============================================================
# Structured audit report
# ============================================================


def _audit_report_path(category: str, slug: str) -> Path:
    return workspace(category, slug) / f"{slug}-audit.json"


def _load_audit_report(category: str, slug: str, expected_nonce: str) -> dict:
    path = _audit_report_path(category, slug)
    if not path.exists():
        raise PipelineError(
            f"Structured audit report missing at {path}. The subagent must "
            f"write {path.name} with schema "
            "{version, nonce, phase, verdict, counts, findings}."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Audit report is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PipelineError("Audit report must be a JSON object")
    if data.get("nonce") != expected_nonce:
        raise ForgeryError(
            f"Nonce mismatch on {path.name}: expected '{expected_nonce}', "
            f"got '{data.get('nonce')}'. Refusing to trust this report."
        )
    if data.get("phase") != "audit":
        raise PipelineError(
            f"Audit report declares phase='{data.get('phase')}', expected 'audit'"
        )
    verdict = data.get("verdict")
    if verdict not in VALID_AUDIT_VERDICTS:
        raise PipelineError(
            f"Audit report has invalid verdict='{verdict}'. "
            f"Expected one of {sorted(VALID_AUDIT_VERDICTS)}."
        )
    counts = data.get("counts") or {}
    if not isinstance(counts, dict):
        raise PipelineError("Audit counts must be a dict")
    return data


def _counts_int(counts: dict, key: str) -> int:
    val = counts.get(key, 0)
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _parse_audit(category: str, slug: str, expected_nonce: str) -> dict:
    data = _load_audit_report(category, slug, expected_nonce)
    counts = data.get("counts") or {}
    return {
        "verdict": data["verdict"],
        "fatal": _counts_int(counts, "fatal"),
        "major": _counts_int(counts, "major"),
        "minor": _counts_int(counts, "minor"),
    }


# ============================================================
# Subcommands
# ============================================================


def cmd_init(category: str, slug: str, force: bool = False) -> dict:
    if category not in ALLOWED_CATEGORIES:
        raise ValueError(
            f"category must be one of {sorted(ALLOWED_CATEGORIES)}, got '{category}'"
        )
    ws = workspace(category, slug)
    sp = state_path(category, slug)
    if sp.exists():
        if not force:
            raise PipelineError(
                f"State already exists for '{category}/{slug}' at {sp}. "
                "Re-init is forbidden without --force."
            )
        prior = json.loads(sp.read_text())
        _append_ledger({
            "event": "forced-reinit",
            "pipeline": "auditor",
            "category": category,
            "slug": slug,
            "prior_phase": prior.get("phase"),
            "prior_retry_count": prior.get("retry_count"),
            "prior_nonce": prior.get("nonce"),
        })
    ws.mkdir(parents=True, exist_ok=True)
    state = PipelineState(
        category=category,
        slug=slug,
        phase="init",
        max_retries=MAX_RETRIES_BY_CATEGORY.get(category, MAX_RETRIES),
    )
    state.log(
        "init",
        workspace=str(ws),
        nonce=state.nonce,
        forced=force,
        max_retries=state.max_retries,
    )
    save_state(state)
    return {
        "status": "ok",
        "pipeline": "auditor",
        "category": category,
        "slug": slug,
        "workspace": str(ws),
        "nonce": state.nonce,
        "next": (
            "draft {slug}.md, {slug}.bib, {slug}.md.citations.json, "
            "then call `gate`"
        ),
    }


def _find_sibling_bib(ws: Path, slug: str) -> Optional[Path]:
    candidate = ws / f"{slug}.bib"
    if candidate.exists():
        return candidate
    for bib in sorted(ws.glob("*.bib")):
        return bib
    return None


def cmd_gate(category: str, slug: str) -> dict:
    state = load_state(category, slug)
    _require_phase(state, "gate")
    ws = workspace(category, slug)
    md = ws / f"{slug}.md"
    if not md.exists():
        raise FileNotFoundError(
            f"Expected draft at {md}. The skill must write it before calling gate."
        )
    bib = _find_sibling_bib(ws, slug)
    quotes = ws / f"{slug}.quotes.json"

    # Tier 4: sci-writing review mode (auditor pipeline on an existing
    # manuscript) is only allowed when the upstream seed already exists.
    # Without it, the auditor would be grading the writer's memory
    # against itself.
    if category == "sci-writing" and not quotes.exists():
        raise PipelineError(
            f"sci-writing review mode requires an upstream seed at "
            f"{quotes}. Refusing to reverse-engineer the sidecar from the "
            "draft. Run sci-literature-research cite mode first to "
            "produce the quotes.json."
        )

    # H3: sci-communication also refuses when the upstream seed is
    # missing AND the draft has citation markers. A blog post with
    # `[@Key]` markers but no quotes.json means Phase H (upstream
    # provenance trace) cannot run — the auditor would be grading the
    # writer's own citations against themselves. We surface a targeted
    # error with the exact fix path instead of a cryptic verify_ops
    # failure downstream. Drafts without any `[@Key]` markers
    # (expertise-only posts, lay explainers with no sourced claims)
    # are allowed to proceed.
    if category == "sci-communication" and not quotes.exists():
        try:
            draft_text = md.read_text(encoding="utf-8")
        except OSError:
            draft_text = ""
        if _BROAD_MARKER_RE.search(draft_text):
            raise PipelineError(
                f"sci-communication draft at {md.name} has citation markers "
                f"([@Key]) but no upstream seed at {quotes.name}. Refusing: "
                "the auditor cannot prove the sidecar quotes weren't invented "
                "by the writer. To fix:\n"
                "  1. Run sci-literature-research cite mode on the source "
                "material to produce the quotes.json, OR\n"
                "  2. Remove the [@Key] markers from the draft if the post "
                "is expertise-based and genuinely uncited.\n"
                f"Place the resulting {quotes.name} next to {md.name} and "
                "re-run gate."
            )

    cmd = [
        sys.executable,
        str(VERIFY_OPS),
        str(md),
        "--bib",
        str(bib) if bib else "",
        "--no-fix",
        "--json",
    ]
    if quotes.exists():
        cmd.extend(["--quotes", str(quotes)])
    result = subprocess.run(cmd, capture_output=True, text=True)
    exit_code = result.returncode
    state.mechanical_exits.append(exit_code)
    state.phase = "gated" if exit_code in (0, 2) else "refused"
    state.last_gate_status = "passed" if exit_code == 0 else ("blocked" if exit_code == 2 else "refused")
    state.log(
        "gate",
        exit_code=exit_code,
        gate_status=state.last_gate_status,
        bib=str(bib) if bib else None,
    )
    save_state(state)

    report: Optional[dict] = None
    try:
        report = json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        report = None

    mechanical_critical = 0
    if report and isinstance(report.get("counts"), dict):
        mechanical_critical = report["counts"].get("critical", 0)

    return {
        "status": (
            "passed"
            if exit_code == 0
            else ("blocked" if exit_code == 2 else "refused")
        ),
        "exit_code": exit_code,
        "mechanical_critical": mechanical_critical,
        "bib": str(bib) if bib else None,
        "report": report,
        "nonce": state.nonce,
        "stderr": result.stderr.strip() or None,
        "next": (
            "refuse" if exit_code == 3
            else "spawn sci-auditor via Agent tool, then call `retry-check`"
        ),
    }


def cmd_retry_check(category: str, slug: str) -> dict:
    state = load_state(category, slug)
    _require_phase(state, "retry-check")
    parsed = _parse_audit(category, slug, state.nonce)
    state.audit_verdicts.append(parsed["verdict"])
    state.log("audit-parsed", **parsed)

    fatal = parsed["fatal"]
    verdict = parsed["verdict"]
    needs_retry = (fatal > 0 or verdict == "refuse") and state.retry_count < state.max_retries
    refused = (fatal > 0 or verdict == "refuse") and state.retry_count >= state.max_retries

    if needs_retry:
        state.retry_count += 1
        state.phase = "retry"
        state.log("retry-triggered", attempt=state.retry_count)
    elif refused:
        state.phase = "refused"
        state.log("refused", reason="FATAL persists after retry budget exhausted")
    else:
        state.phase = "audited"

    save_state(state)
    return {
        "status": "retry" if needs_retry else ("refused" if refused else "ok"),
        "verdict": verdict,
        "fatal": parsed["fatal"],
        "major": parsed["major"],
        "minor": parsed["minor"],
        "retry_count": state.retry_count,
        "max_retries": state.max_retries,
        "next": (
            "apply revision plan in parent skill, then re-run `gate` + re-spawn sci-auditor"
            if needs_retry
            else ("refuse to save" if refused else "call `finalize`")
        ),
    }


def cmd_finalize(category: str, slug: str) -> dict:
    state = load_state(category, slug)
    _require_phase(state, "finalize")
    parsed = _parse_audit(category, slug, state.nonce)

    if parsed["fatal"] > 0 or parsed["verdict"] == "refuse":
        state.phase = "refused"
        state.log("finalize-refused", **parsed)
        save_state(state)
        return {
            "status": "refused",
            "reason": "FATAL findings present at finalize time",
            "audit": parsed,
        }

    if state.mechanical_exits and state.mechanical_exits[-1] == 3:
        state.phase = "refused"
        state.log("finalize-refused", reason="mechanical exit 3")
        save_state(state)
        return {
            "status": "refused",
            "reason": "verify_ops refused (contract failure) on last gate",
        }

    # Mirror paper_pipeline's gate-status check: if the mechanical gate
    # emitted CRITICAL findings (exit 2, last_gate_status="blocked"), the
    # draft must not be saved even if the AI auditor's verdict is "ship".
    # The auditor operates on the sidecar, not the raw CRITICAL report, so
    # it can miss a fabricated-author or title-mismatch finding that the
    # mechanical Tier 5 check caught.
    if state.last_gate_status == "blocked":
        state.phase = "refused"
        state.log(
            "finalize-refused",
            reason="mechanical gate blocked (exit 2) — unresolved CRITICAL findings",
        )
        save_state(state)
        return {
            "status": "refused",
            "reason": (
                "verify_ops gate is blocked on CRITICAL findings (fabricated "
                "quote, author mismatch, unmatched bib key, or missing source "
                "anchor). Fix the draft + sidecar and re-run gate before finalize."
            ),
        }

    state.phase = "finalized"
    state.humanize_lock = True
    state.finalized_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state.log("finalized", **parsed)
    save_state(state)
    return {
        "status": "ok",
        "phase": "finalized",
        "humanize_lock": True,
        "workspace": str(workspace(category, slug)),
        "artifacts": sorted(
            p.name for p in workspace(category, slug).iterdir() if p.is_file()
        ),
        "audit": parsed,
        "note": (
            "humanize_lock is set. verify_gate will refuse any further "
            "Write/Edit on the draft until you run `post-humanize` (which "
            "clears the lock on pass, or flips to refused on fail). If you "
            "don't intend to run the humanizer, call post-humanize anyway "
            "— it's a no-op re-verification that simply clears the lock."
        ),
    }


def cmd_post_humanize(category: str, slug: str) -> dict:
    """Tier 4 T4.1: re-run verify_ops after the humanizer.

    The tool-humanizer rewrites prose to remove AI-tells, which can
    paraphrase the very verbatim quotes the auditor just validated.
    This command runs the mechanical gate again on the post-humanizer
    manuscript and, on CRITICAL findings, flips the pipeline to
    refused so no subsequent finalize call can ship it.

    Precondition: phase='finalized' (from a prior pass).
    """
    state = load_state(category, slug)
    _require_phase(state, "post-humanize")
    ws = workspace(category, slug)
    md = ws / f"{slug}.md"
    if not md.exists():
        raise FileNotFoundError(f"Expected humanized draft at {md}")
    bib = _find_sibling_bib(ws, slug)
    quotes = ws / f"{slug}.quotes.json"

    cmd = [
        sys.executable,
        str(VERIFY_OPS),
        str(md),
        "--bib",
        str(bib) if bib else "",
        "--no-fix",
        "--json",
    ]
    if quotes.exists():
        cmd.extend(["--quotes", str(quotes)])
    result = subprocess.run(cmd, capture_output=True, text=True)
    exit_code = result.returncode
    state.mechanical_exits.append(exit_code)
    state.log("post-humanize", exit_code=exit_code)

    report: Optional[dict] = None
    try:
        report = json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        report = None

    if exit_code == 0:
        # C2: clear the humanize_lock so verify_gate allows subsequent
        # edits. Lock stays set if anything below fails.
        state.humanize_lock = False
        save_state(state)
        return {
            "status": "passed",
            "exit_code": 0,
            "report": report,
            "humanize_lock": False,
            "next": "ship",
        }

    # Any non-zero exit after humanization is a drift — revert and refuse.
    state.phase = "refused"
    state.log(
        "post-humanize-refused",
        exit_code=exit_code,
        reason="humanizer broke the verbatim contract",
    )
    save_state(state)
    return {
        "status": "refused",
        "exit_code": exit_code,
        "report": report,
        "reason": (
            "The humanizer introduced content that no longer matches the "
            "verified sidecar. Roll back the humanizer pass before shipping."
        ),
        "next": "rollback humanizer output, then redraft",
    }


def cmd_status(category: str, slug: str) -> dict:
    state = load_state(category, slug)
    return asdict(state)


# ============================================================
# CLI
# ============================================================


def _dispatch(args: argparse.Namespace) -> tuple[int, dict]:
    try:
        if args.command == "init":
            return 0, cmd_init(
                args.category,
                args.slug,
                force=bool(getattr(args, "force", False)),
            )
        if args.command == "gate":
            payload = cmd_gate(args.category, args.slug)
            code = 0 if payload["status"] == "passed" else (
                3 if payload["status"] == "refused" else 2
            )
            return code, payload
        if args.command == "retry-check":
            payload = cmd_retry_check(args.category, args.slug)
            code = (
                0
                if payload["status"] == "ok"
                else (3 if payload["status"] == "refused" else 2)
            )
            return code, payload
        if args.command == "finalize":
            payload = cmd_finalize(args.category, args.slug)
            return (0 if payload["status"] == "ok" else 3), payload
        if args.command == "post-humanize":
            payload = cmd_post_humanize(args.category, args.slug)
            return (0 if payload["status"] == "passed" else 3), payload
        if args.command == "status":
            return 0, cmd_status(args.category, args.slug)
    except ForgeryError as exc:
        return 3, {"status": "refused", "error": str(exc), "kind": "forgery"}
    except PipelineError as exc:
        return 1, {"status": "error", "error": str(exc), "kind": "pipeline"}
    except Exception as exc:
        return 1, {"status": "error", "error": str(exc)}
    return 1, {"status": "error", "error": f"unknown command {args.command}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "gate", "retry-check", "finalize", "post-humanize", "status"):
        p = sub.add_parser(name)
        p.add_argument("category", choices=sorted(ALLOWED_CATEGORIES))
        p.add_argument("slug")
        if name == "init":
            p.add_argument(
                "--force",
                action="store_true",
                help="Overwrite existing state; appends to pipeline ledger.",
            )
    args = parser.parse_args(argv)
    code, payload = _dispatch(args)
    print(json.dumps(payload, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
