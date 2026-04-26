"""Orchestrator state machine for the 4-agent paper review cascade.

Used by `sci-writing` draft mode. Subagent spawning happens in the skill
(Claude) loop via the Agent tool — this script is the state manager that
Claude calls at each transition point:

  init                 create workspace + state file (issues nonce)
  check-research       confirm sci-researcher's artifacts exist
  gate-draft           run verify_ops.py on the writer's draft
  collect-verification parse {slug}-verification.json (nonce-gated)
  collect-review       parse {slug}-review.json (nonce-gated)
  retry-check          decide whether a one-shot retry is needed
  finalize             confirm save is allowed
  status               dump current state

Tier 2 invariants:
  * Phase preconditions (ALLOWED_TRANSITIONS) enforce the correct call
    order — out-of-order calls are rejected, not silently accepted.
  * phase='refused' is terminal. Only `status` runs from refused.
  * Subagent reports are structured JSON ({slug}-verification.json,
    {slug}-review.json). Markdown files are human-readable only. The
    report JSON MUST echo state.nonce, or the pipeline refuses to parse
    it — this raises the friction for a parent conductor that tries to
    forge the cascade by hand-writing the verdict files.
  * init refuses to overwrite existing state unless --force, and --force
    appends to an append-only ledger outside the workspace.
  * State writes are atomic (tempfile + os.replace).

Exit codes: 0 ok, 1 error, 2 blocked (revise), 3 refused (do not save).
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

PROJECT_ROOT = Path(__file__).resolve().parents[4]
VERIFY_OPS = PROJECT_ROOT / ".claude/skills/sci-writing/scripts/verify_ops.py"
REPRO_DIR = PROJECT_ROOT / "repro"

_SCRIPTS_DIR = PROJECT_ROOT / ".claude" / "skills" / "sci-writing" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from researcher_ops import (  # type: ignore
        validate_research_compliance as _validate_receipts,
        parse_receipts_table as _parse_receipts,
        cross_reference_receipts as _cross_reference_receipts,
        verify_receipts_against_api as _verify_receipts_api,
        check_receipt_confidence as _check_receipt_conf,
    )
    _RESEARCHER_OPS_AVAILABLE = True
    _RESEARCHER_OPS_IMPORT_ERROR: str | None = None
except ImportError as _researcher_import_err:  # pragma: no cover - import guard
    _RESEARCHER_OPS_AVAILABLE = False
    _RESEARCHER_OPS_IMPORT_ERROR = str(_researcher_import_err)

try:
    from writing_ops import parse_bib_file as _parse_bib_file  # type: ignore
    _WRITING_OPS_AVAILABLE = True
except ImportError:
    _WRITING_OPS_AVAILABLE = False

MAX_RETRIES = 1
CATEGORY = "sci-writing"

# Match `doi = {10.xxx/yyy}` or `doi = "10.xxx/yyy"` in BibTeX entries.
# Case-insensitive on the key; accepts either brace or quote delimiters.
_BIB_DOI_RE = re.compile(r'doi\s*=\s*[{"]([^}"]+)[}"]', re.IGNORECASE)


def _extract_dois_from_bib(bib_path: Path) -> list[str]:
    """Parse a .bib file and return every DOI entry (de-duplicated, ordered)."""
    if not bib_path.exists():
        return []
    text = bib_path.read_text(encoding="utf-8", errors="replace")
    seen: set[str] = set()
    dois: list[str] = []
    for match in _BIB_DOI_RE.finditer(text):
        doi = match.group(1).strip()
        if doi and doi not in seen:
            seen.add(doi)
            dois.append(doi)
    return dois


def _verify_dois_via_crossref(dois: list[str]) -> list[dict]:
    """Call repro.citation_verify.batch_verify on a list of DOIs.

    Kept as a module-level helper so tests can monkeypatch it without
    touching the network. Respects `SCI_OS_SKIP_DOI_VERIFY=1` for
    offline/CI runs where CrossRef access is unavailable.
    """
    if os.environ.get("SCI_OS_SKIP_DOI_VERIFY") == "1":
        return []
    if not dois:
        return []
    # Lazy import: repro/ is a separate module and we don't want
    # paper_pipeline import to fail if repro/ is missing (e.g. in a
    # minimal test fixture tree).
    repro_path = str(REPRO_DIR)
    if repro_path not in sys.path:
        sys.path.insert(0, repro_path)
    try:
        from citation_verify import batch_verify  # type: ignore
    except ImportError:
        return []
    return batch_verify(dois)

# Phase precondition map. Each command can only fire from one of the
# listed phases. refused is terminal and never appears here (only
# status is allowed from refused — enforced separately).
ALLOWED_TRANSITIONS = {
    "check-research": {"init", "research-incomplete"},
    "gate-draft": {"researched", "retry"},
    "collect-verification": {"drafted"},
    "collect-review": {"verified"},
    "retry-check": {"reviewed"},
    "finalize": {"clean", "needs-major-revision"},
    "status": None,  # always allowed
}

VALID_VERIFIER_VERDICTS = {"clean", "revise", "refuse"}
VALID_REVIEW_VERDICTS = {"ship", "revise", "refuse"}


# ============================================================
# Errors
# ============================================================


class PipelineError(RuntimeError):
    """Raised when a pipeline command is called in an invalid state."""


class ForgeryError(PipelineError):
    """Raised when a subagent report's nonce does not match state."""


# ============================================================
# State
# ============================================================


def _new_nonce() -> str:
    return uuid.uuid4().hex


@dataclass
class PaperState:
    pipeline: str = "paper"
    slug: str = ""
    topic: str = ""
    section: str = ""
    phase: str = "init"
    nonce: str = field(default_factory=_new_nonce)
    retry_count: int = 0
    max_retries: int = MAX_RETRIES
    mechanical_exits: list[int] = field(default_factory=list)
    # M7: explicit gate-draft status. phase="drafted" alone is ambiguous
    # because exit 0 (clean) and exit 2 (blocked by CRITICAL) both
    # advance the phase. Downstream code needs to tell these apart to
    # surface the right verdict. Values: "passed" | "blocked" | "refused"
    # | None (before any gate runs).
    last_gate_status: Optional[str] = None
    verification_counts: list[dict] = field(default_factory=list)
    review_counts: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)

    def log(self, event: str, **kwargs) -> None:
        self.history.append(
            {
                "event": event,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                **kwargs,
            }
        )


def workspace(slug: str) -> Path:
    return PROJECT_ROOT / "projects" / CATEGORY / slug


def state_path(slug: str) -> Path:
    return workspace(slug) / ".pipeline_state.json"


def load_state(slug: str) -> PaperState:
    p = state_path(slug)
    if not p.exists():
        raise FileNotFoundError(f"No paper pipeline state for {slug}. Run `init` first.")
    data = json.loads(p.read_text())
    return PaperState(**data)


def save_state(state: PaperState) -> None:
    """Atomic write: temp file + os.replace so a crash mid-write leaves
    the previous valid state in place instead of a truncated file."""
    p = state_path(state.slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def _require_phase(state: PaperState, command: str) -> None:
    """Fail fast on out-of-order calls and on terminal refused state."""
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
# Ledger (append-only, outside the workspace)
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
# Structured report parsers
# ============================================================


def _verification_report_path(slug: str) -> Path:
    return workspace(slug) / f"{slug}-verification.json"


def _review_report_path(slug: str) -> Path:
    return workspace(slug) / f"{slug}-review.json"


def _load_report(path: Path, expected_nonce: str, phase: str,
                 valid_verdicts: set[str]) -> dict:
    if not path.exists():
        raise PipelineError(
            f"Structured report missing at {path}. The subagent must write "
            f"{path.name} with the schema "
            "{version, nonce, phase, verdict, counts: {...}, findings}."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Report {path.name} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise PipelineError(f"Report {path.name} must be a JSON object")
    if data.get("nonce") != expected_nonce:
        raise ForgeryError(
            f"Nonce mismatch on {path.name}: expected '{expected_nonce}', "
            f"got '{data.get('nonce')}'. The report was not produced by a "
            "subagent that received the current pipeline nonce — refusing to "
            "trust it."
        )
    if data.get("phase") != phase:
        raise PipelineError(
            f"Report {path.name} declares phase='{data.get('phase')}', "
            f"expected '{phase}'"
        )
    verdict = data.get("verdict")
    if verdict not in valid_verdicts:
        raise PipelineError(
            f"Report {path.name} has invalid verdict='{verdict}'. "
            f"Expected one of {sorted(valid_verdicts)}."
        )
    counts = data.get("counts") or {}
    if not isinstance(counts, dict):
        raise PipelineError(f"Report {path.name} counts must be a dict")
    return data


def _counts_int(counts: dict, key: str) -> int:
    val = counts.get(key, 0)
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


# ============================================================
# Subcommands
# ============================================================


def cmd_init(slug: str, topic: str = "", section: str = "",
             force: bool = False) -> dict:
    ws = workspace(slug)
    sp = state_path(slug)
    if sp.exists():
        if not force:
            raise PipelineError(
                f"State already exists for '{slug}' at {sp}. Re-init is "
                "forbidden without --force (it would reset retry_count and "
                "rotate the nonce, defeating the retry budget)."
            )
        prior = json.loads(sp.read_text())
        _append_ledger({
            "event": "forced-reinit",
            "pipeline": "paper",
            "slug": slug,
            "prior_phase": prior.get("phase"),
            "prior_retry_count": prior.get("retry_count"),
            "prior_nonce": prior.get("nonce"),
        })
    ws.mkdir(parents=True, exist_ok=True)
    state = PaperState(slug=slug, topic=topic, section=section, phase="init")
    state.log("init", workspace=str(ws), topic=topic, section=section,
              nonce=state.nonce, forced=force)
    save_state(state)
    return {
        "status": "ok",
        "pipeline": "paper",
        "slug": slug,
        "workspace": str(ws),
        "nonce": state.nonce,
        "next": "spawn sci-researcher via Agent tool, then call `check-research`",
    }


_COVERAGE_UNRESOLVED_RE = re.compile(
    r"##\s*Coverage status.*?Unresolved[^:]*[:：](.*?)(?=\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_BULLET_LINE_RE = re.compile(r"^\s*[-*+]\s+(.+)$", re.MULTILINE)


def _parse_coverage_gaps(research_md_path: Path) -> list[str]:
    """C4: Extract unresolved sub-claim gaps from the ## Coverage status section."""
    if not research_md_path.exists():
        return []
    text = research_md_path.read_text(encoding="utf-8", errors="replace")
    match = _COVERAGE_UNRESOLVED_RE.search(text)
    if not match:
        return []
    body = match.group(1).strip()
    if not body or body.lower() in ("none", "n/a", ""):
        return []
    gaps = [m.group(1).strip() for m in _BULLET_LINE_RE.finditer(body)]
    if not gaps:
        # Inline format: "Unresolved gaps: sub-claim 3, sub-claim 5"
        gaps = [g.strip() for g in re.split(r"[,;]", body) if g.strip()]
    return gaps


def cmd_check_research(slug: str) -> dict:
    state = load_state(slug)
    _require_phase(state, "check-research")
    ws = workspace(slug)
    bib_path = ws / f"{slug}.bib"
    required = [ws / "research.md", bib_path, ws / f"{slug}.quotes.json"]
    missing = [p.name for p in required if not p.exists()]
    if missing:
        state.phase = "research-incomplete"
        state.log("check-research", missing=missing)
        save_state(state)
        return {"status": "incomplete", "missing": missing}

    # Phase 9 — researcher_ops fail-closed.
    # Pre-Phase-9: if researcher_ops failed to import at module load time,
    # _RESEARCHER_OPS_AVAILABLE was set to False and the receipts/B2/B3
    # checks below were silently skipped. That was the same fail-open
    # shape Phase 8 fixed for verify_ops on the publish path. Now: refuse
    # cmd_check_research unless SCI_OS_ALLOW_UNGATED=1 is set, and log the
    # bypass to the pipeline ledger so the audit trail records the override.
    if not _RESEARCHER_OPS_AVAILABLE:
        if os.environ.get("SCI_OS_ALLOW_UNGATED", "").strip().lower() not in (
            "1", "true", "yes"
        ):
            state.phase = "research-incomplete"
            state.log(
                "check-research",
                researcher_ops_unavailable=True,
                import_error=_RESEARCHER_OPS_IMPORT_ERROR,
            )
            save_state(state)
            return {
                "status": "incomplete",
                "reason": (
                    "researcher_ops module is unavailable "
                    f"({_RESEARCHER_OPS_IMPORT_ERROR}). The receipts and "
                    "Tier B forensics cannot run, so the gate refuses to "
                    "advance check-research. Phase 9 fail-closed: a broken "
                    "venv is no longer a silent skip. Fix the import error "
                    "and retry. To bypass in an emergency, set "
                    "SCI_OS_ALLOW_UNGATED=1 — the bypass is logged."
                ),
                "import_error": _RESEARCHER_OPS_IMPORT_ERROR,
            }
        else:
            state.log(
                "check-research",
                researcher_ops_ungated_bypass=True,
                import_error=_RESEARCHER_OPS_IMPORT_ERROR,
            )

    # Fix A — pre-gate CrossRef validation. The mechanical verifier at
    # gate-draft time already runs CrossRef lookups on every bib entry
    # (check_bib_integrity in verify_ops.py), but doing it here catches
    # a hallucinated DOI ONE phase earlier — before a full writer cycle
    # burns tokens on a draft citing a nonexistent paper. This is
    # defense-in-depth: if gate-draft's CrossRef check is somehow
    # bypassed, check-research still refuses to advance.
    dois = _extract_dois_from_bib(bib_path)
    verify_results = _verify_dois_via_crossref(dois)
    failed = [r for r in verify_results if r.get("error")]
    if failed:
        state.phase = "research-incomplete"
        state.log(
            "check-research",
            failed_dois=[r.get("doi") for r in failed],
            reason="CrossRef verification failed",
        )
        save_state(state)
        return {
            "status": "incomplete",
            "reason": (
                "one or more DOIs in the .bib could not be verified against "
                "CrossRef — likely fabricated or malformed"
            ),
            "failed_dois": [
                {"doi": r.get("doi"), "error": r.get("error")} for r in failed
            ],
            "next": (
                "re-run sci-researcher with corrected DOIs, or remove "
                "unverifiable entries from the .bib"
            ),
        }

    # Phase 3 — researcher compliance: research.md must contain a
    # '## Verification receipts' table documenting what was actually
    # retrieved from APIs per evidence entry. If the table is absent or
    # empty the bib may be filled from training memory, not live data.
    if _RESEARCHER_OPS_AVAILABLE:
        research_md = ws / "research.md"
        try:
            ok, receipt_findings = _validate_receipts(research_md)
        except FileNotFoundError:
            ok, receipt_findings = False, []
        if not ok:
            state.phase = "research-incomplete"
            state.log(
                "check-research",
                phase3_receipts_missing=True,
                reason="research.md missing Verification receipts table",
            )
            save_state(state)
            return {
                "status": "incomplete",
                "reason": (
                    "research.md does not contain a '## Verification receipts' "
                    "table. The sci-researcher agent must document, for each "
                    "evidence entry, the exact title and first author returned "
                    "from the API — not from memory. Re-spawn sci-researcher "
                    "with the Phase 3 compliance instruction, then re-run "
                    "check-research."
                ),
                "compliance_findings": receipt_findings,
            }

    # Tier B — receipt forensics: B2 cross-reference receipts vs bib entries
    # (unconditional); B3 API re-validation (env-gated inside the function).
    if _RESEARCHER_OPS_AVAILABLE and _WRITING_OPS_AVAILABLE:
        research_md = ws / "research.md"
        receipts = _parse_receipts(research_md)
        if receipts:
            bib_entries_full = _parse_bib_file(str(bib_path))
            xref_findings = _cross_reference_receipts(receipts, bib_entries_full)
            criticals_xref = [f for f in xref_findings if f.get("severity") == "critical"]
            if criticals_xref:
                state.phase = "research-incomplete"
                state.log(
                    "check-research",
                    receipt_forensics_xref=True,
                    critical_count=len(criticals_xref),
                    reason="Receipt cross-reference found bib mismatches",
                )
                save_state(state)
                return {
                    "status": "incomplete",
                    "reason": (
                        f"Receipt forensics found {len(criticals_xref)} CRITICAL "
                        "mismatch(es) between the Verification receipts table and the "
                        ".bib file. Fix the bib or the receipt rows so they agree, "
                        "then re-run check-research."
                    ),
                    "compliance_findings": xref_findings,
                }

            api_findings = _verify_receipts_api(receipts)
            criticals_api = [f for f in api_findings if f.get("severity") == "critical"]
            if criticals_api:
                state.phase = "research-incomplete"
                state.log(
                    "check-research",
                    receipt_forensics_api=True,
                    critical_count=len(criticals_api),
                    reason="Receipt API re-validation found mismatches",
                )
                save_state(state)
                return {
                    "status": "incomplete",
                    "reason": (
                        f"Receipt API re-validation found {len(criticals_api)} CRITICAL "
                        "mismatch(es): receipt rows do not match the live API response. "
                        "Re-spawn sci-researcher to regenerate receipts from live data."
                    ),
                    "compliance_findings": api_findings,
                }

    # C4: surface coverage gaps so the writer sees them before drafting.
    coverage_gaps = _parse_coverage_gaps(ws / "research.md")

    state.phase = "researched"
    state.log(
        "check-research",
        ok=True,
        dois_verified=len(verify_results) if verify_results else 0,
        coverage_gaps=len(coverage_gaps),
    )
    save_state(state)
    gap_note = (
        f" NOTE: {len(coverage_gaps)} sub-claim(s) have no supporting evidence "
        f"(coverage_gaps field) — writer must mark these [GAP:...] or hedge; "
        f"do NOT cite into a gap."
        if coverage_gaps else ""
    )
    return {
        "status": "ok",
        "artifacts": [p.name for p in required],
        "dois_verified": len(verify_results) if verify_results else 0,
        "nonce": state.nonce,
        "coverage_gaps": coverage_gaps,
        "next": "spawn sci-writer via Agent tool, then call `gate-draft`" + gap_note,
    }


def cmd_gate_draft(slug: str) -> dict:
    state = load_state(slug)
    _require_phase(state, "gate-draft")
    ws = workspace(slug)
    md = ws / f"{slug}-draft.md"
    bib = ws / f"{slug}.bib"
    source = ws / "research.md"
    quotes = ws / f"{slug}.quotes.json"
    if not md.exists():
        raise FileNotFoundError(f"Expected writer draft at {md}")
    cmd = [
        sys.executable,
        str(VERIFY_OPS),
        str(md),
        "--bib",
        str(bib),
        "--source",
        str(source),
        "--no-fix",
        "--json",
    ]
    # Tier 4: always pass upstream quotes.json so verify_ops runs the
    # provenance trace against the pre-fetched seeds. check-research
    # already enforces that this file exists before phase="researched",
    # so reaching gate-draft without it means the file was deleted
    # mid-flight — refuse rather than silently skip the provenance check.
    if not quotes.exists():
        raise FileNotFoundError(
            f"Upstream quotes sidecar missing at {quotes}. "
            "check-research requires it to exist before gate-draft runs; "
            "do not delete it between phases."
        )
    cmd.extend(["--quotes", str(quotes)])
    result = subprocess.run(cmd, capture_output=True, text=True)
    state.mechanical_exits.append(result.returncode)
    # M7: disambiguate "blocked but advance" from "clean and advance".
    # Both exit 0 and exit 2 move phase to "drafted" (so downstream
    # verifier/reviewer can still run), but last_gate_status lets
    # readers tell a clean gate from a blocked one.
    if result.returncode == 0:
        state.phase = "drafted"
        state.last_gate_status = "passed"
    elif result.returncode == 2:
        state.phase = "drafted"
        state.last_gate_status = "blocked"
    else:
        state.phase = "refused"
        state.last_gate_status = "refused"
    state.log("gate-draft", exit_code=result.returncode, gate_status=state.last_gate_status)
    save_state(state)

    report: Optional[dict] = None
    try:
        report = json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        report = None

    # B5: check sidecar source_confidence vs upstream seed confidence.
    # Runs at gate-draft time because the draft sidecar only exists after
    # the writer finishes. MAJOR findings are advisory — do not change gate status.
    if _RESEARCHER_OPS_AVAILABLE:
        try:
            seed_quotes: dict = {}
            if quotes.exists():
                qdata = json.loads(quotes.read_text(encoding="utf-8"))
                for entry in qdata.get("quotes") or []:
                    k = (entry.get("key") or "").strip().lower()
                    if k:
                        seed_quotes[k] = entry

            draft_sidecar = ws / f"{slug}-draft.md.citations.json"
            sidecar_quotes: dict = {}
            if draft_sidecar.exists():
                sdata = json.loads(draft_sidecar.read_text(encoding="utf-8"))
                for claim in sdata.get("claims") or []:
                    k = (claim.get("key") or "").strip().lower()
                    if k:
                        sidecar_quotes[k] = claim

            if seed_quotes and sidecar_quotes:
                receipts = _parse_receipts(ws / "research.md") if (ws / "research.md").exists() else []
                b5_findings = _check_receipt_conf(receipts, seed_quotes, sidecar_quotes)
                if b5_findings and report is not None:
                    existing = report.get("findings") or []
                    report = {**report, "findings": existing + b5_findings}
                    summary = report.get("summary") or {}
                    report["summary"] = {
                        **summary,
                        "major": summary.get("major", 0) + len(b5_findings),
                    }
        except Exception:
            pass  # B5 is advisory; never let wiring errors block the gate

    return {
        "status": (
            "passed"
            if result.returncode == 0
            else ("blocked" if result.returncode == 2 else "refused")
        ),
        "exit_code": result.returncode,
        "report": report,
        "nonce": state.nonce,
        "stderr": result.stderr.strip() or None,
        "next": (
            "refuse" if result.returncode == 3
            else "spawn sci-verifier via Agent tool, then call `collect-verification`"
        ),
    }


def cmd_collect_verification(slug: str) -> dict:
    state = load_state(slug)
    _require_phase(state, "collect-verification")
    report = _load_report(
        _verification_report_path(slug),
        expected_nonce=state.nonce,
        phase="verification",
        valid_verdicts=VALID_VERIFIER_VERDICTS,
    )
    counts = report.get("counts") or {}
    parsed = {
        "verdict": report["verdict"],
        "critical": _counts_int(counts, "critical"),
        "major": _counts_int(counts, "major"),
        "minor": _counts_int(counts, "minor"),
    }
    state.verification_counts.append(parsed)
    state.phase = "verified"
    state.log("collect-verification", **parsed)
    save_state(state)
    return {
        "status": "ok",
        **parsed,
        "next": "spawn sci-reviewer via Agent tool, then call `collect-review`",
    }


def cmd_collect_review(slug: str) -> dict:
    state = load_state(slug)
    _require_phase(state, "collect-review")
    report = _load_report(
        _review_report_path(slug),
        expected_nonce=state.nonce,
        phase="review",
        valid_verdicts=VALID_REVIEW_VERDICTS,
    )
    counts = report.get("counts") or {}
    parsed = {
        "verdict": report["verdict"],
        "fatal": _counts_int(counts, "fatal"),
        "major": _counts_int(counts, "major"),
        "minor": _counts_int(counts, "minor"),
    }
    state.review_counts.append(parsed)
    state.phase = "reviewed"
    state.log("collect-review", **parsed)
    save_state(state)
    return {
        "status": "ok",
        **parsed,
        "next": "call `retry-check`",
    }


def cmd_retry_check(slug: str) -> dict:
    state = load_state(slug)
    _require_phase(state, "retry-check")
    last_v = state.verification_counts[-1] if state.verification_counts else {}
    last_r = state.review_counts[-1] if state.review_counts else {}
    fatal = (last_r.get("fatal") or 0) + (last_v.get("critical") or 0)
    major = (last_r.get("major") or 0) + (last_v.get("major") or 0)
    refused = (
        last_r.get("verdict") == "refuse"
        or last_v.get("verdict") == "refuse"
        or fatal > 0
    )

    needs_retry = refused and state.retry_count < state.max_retries
    hard_refuse = refused and state.retry_count >= state.max_retries

    if needs_retry:
        state.retry_count += 1
        state.phase = "retry"
        state.log("retry-triggered", attempt=state.retry_count, fatal=fatal, major=major)
    elif hard_refuse:
        state.phase = "refused"
        state.log("refused", reason="FATAL persists after retry budget", fatal=fatal)
    elif major > 0:
        state.phase = "needs-major-revision"
        state.log("major-revision", major=major)
    else:
        state.phase = "clean"
        state.log("clean", fatal=fatal, major=major)

    save_state(state)

    return {
        "status": (
            "retry"
            if needs_retry
            else ("refused" if hard_refuse else ("revise" if major > 0 else "ok"))
        ),
        "fatal": fatal,
        "major": major,
        "retry_count": state.retry_count,
        "max_retries": state.max_retries,
        "next": (
            "respawn sci-writer with {slug}-review.md as fix instructions, "
            "then re-run gate-draft + verifier + reviewer + retry-check"
            if needs_retry
            else (
                "refuse to save"
                if hard_refuse
                else ("address MAJOR findings, then call finalize" if major > 0 else "call finalize")
            )
        ),
    }


def cmd_finalize(slug: str) -> dict:
    state = load_state(slug)
    _require_phase(state, "finalize")
    last_v = state.verification_counts[-1] if state.verification_counts else {}
    last_r = state.review_counts[-1] if state.review_counts else {}
    fatal = (last_r.get("fatal") or 0) + (last_v.get("critical") or 0)
    last_gate = state.mechanical_exits[-1] if state.mechanical_exits else None

    if fatal > 0 or last_v.get("verdict") == "refuse" or last_r.get("verdict") == "refuse":
        state.phase = "refused"
        state.log("finalize-refused", fatal=fatal)
        save_state(state)
        return {"status": "refused", "reason": "FATAL findings at finalize time"}

    if last_gate == 3:
        state.phase = "refused"
        state.log("finalize-refused", reason="mechanical exit 3")
        save_state(state)
        return {"status": "refused", "reason": "verify_ops refused on last gate"}

    # Citation integrity gate: the mechanical verifier (verify_ops.py)
    # catches fabricated quotes, unmatched bib keys, bad paperclip anchors,
    # and upstream-provenance mismatches. Exit 2 = one or more CRITICAL
    # findings. Both exit 0 and exit 2 advance phase to "drafted" so the
    # downstream semantic verifier/reviewer can still weigh in, but
    # finalize MUST NOT save a draft that the mechanical gate blocked —
    # the semantic verifier operates on the sidecar, not the raw CRITICAL
    # report, and can miss a fabricated quote that the mechanical gate
    # caught. If the last gate was blocked, the writer must re-run
    # gate-draft with a fixed sidecar before finalize can succeed.
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
                "quote, unmatched bib key, or missing source anchor). Fix the "
                "draft + sidecar and re-run gate-draft before finalize."
            ),
        }

    state.phase = "finalized"
    state.log("finalized")
    save_state(state)
    ws = workspace(slug)
    artifacts = sorted(p.name for p in ws.iterdir() if p.is_file())
    return {
        "status": "ok",
        "phase": "finalized",
        "workspace": str(ws),
        "artifacts": artifacts,
    }


def cmd_status(slug: str) -> dict:
    return asdict(load_state(slug))


# M: next-command hint table for resume.
_PHASE_NEXT_HINT = {
    "init":                 "spawn sci-researcher via Agent tool, then `check-research`",
    "researched":           "spawn sci-writer via Agent tool, then `gate-draft`",
    "drafted":              "spawn sci-verifier via Agent tool, then `collect-verification`",
    "verified":             "spawn sci-reviewer via Agent tool, then `collect-review`",
    "reviewed":             "run `retry-check`",
    "retry":                "re-spawn sci-writer with review findings, then `gate-draft`",
    "gated-verifier-ready": "spawn sci-verifier via Agent tool, then `collect-verification`",
    "finalized":            "pipeline complete — artifacts are saved",
    "refused":              "terminal; fix underlying issues and `init --force`",
}


def cmd_resume(slug: str) -> dict:
    """C3: resume an interrupted pipeline without rotating the nonce.

    Unlike `init --force` (which rotates the nonce and resets
    retry_count — the audit finding that interrupts silently
    unlocked the retry budget), `resume` is a read-only continuation
    hint. It loads the existing state, reports phase, nonce,
    retry_count, and the next command the conductor should run based
    on the current phase. Nothing mutates.

    If the workspace has no .pipeline_state.json, raise PipelineError
    — there is nothing to resume; the user wants `init` instead.
    """
    sp = state_path(slug)
    if not sp.exists():
        raise PipelineError(
            f"No pipeline state at {sp}. Nothing to resume — run "
            f"`paper_pipeline.py init {slug}` to start a fresh cascade."
        )
    state = load_state(slug)
    next_hint = _PHASE_NEXT_HINT.get(
        state.phase,
        f"(no hint registered for phase={state.phase!r}; inspect state manually)",
    )
    return {
        "status": "resumed",
        "slug": slug,
        "phase": state.phase,
        "nonce": state.nonce,
        "retry_count": state.retry_count,
        "max_retries": state.max_retries,
        "last_gate_status": state.last_gate_status,
        "next": next_hint,
        "note": (
            "resume is read-only: nonce + retry_count preserved. "
            "If phase is 'refused', the only recovery is `init --force`."
        ),
    }


# ============================================================
# CLI
# ============================================================


def _dispatch(args: argparse.Namespace) -> tuple[int, dict]:
    try:
        if args.command == "init":
            return 0, cmd_init(
                args.slug,
                args.topic or "",
                args.section or "",
                force=bool(getattr(args, "force", False)),
            )
        if args.command == "check-research":
            payload = cmd_check_research(args.slug)
            return (0 if payload["status"] == "ok" else 2), payload
        if args.command == "gate-draft":
            payload = cmd_gate_draft(args.slug)
            code = 0 if payload["status"] == "passed" else (
                3 if payload["status"] == "refused" else 2
            )
            return code, payload
        if args.command == "collect-verification":
            payload = cmd_collect_verification(args.slug)
            return (0 if payload["status"] == "ok" else 2), payload
        if args.command == "collect-review":
            payload = cmd_collect_review(args.slug)
            return (0 if payload["status"] == "ok" else 2), payload
        if args.command == "retry-check":
            payload = cmd_retry_check(args.slug)
            code = {
                "ok": 0,
                "revise": 2,
                "retry": 2,
                "refused": 3,
            }[payload["status"]]
            return code, payload
        if args.command == "finalize":
            payload = cmd_finalize(args.slug)
            return (0 if payload["status"] == "ok" else 3), payload
        if args.command == "status":
            return 0, cmd_status(args.slug)
        if args.command == "resume":
            return 0, cmd_resume(args.slug)
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
    for name in (
        "init",
        "check-research",
        "gate-draft",
        "collect-verification",
        "collect-review",
        "retry-check",
        "finalize",
        "status",
        "resume",
    ):
        p = sub.add_parser(name)
        p.add_argument("slug")
        if name == "init":
            p.add_argument("--topic", default="")
            p.add_argument("--section", default="")
            p.add_argument(
                "--force",
                action="store_true",
                help="Overwrite existing state. Rotates the nonce and "
                     "appends an entry to the pipeline ledger.",
            )
    args = parser.parse_args(argv)
    code, payload = _dispatch(args)
    print(json.dumps(payload, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
