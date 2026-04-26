"""Orchestrator tests for the paper pipeline state machine.

Subagent spawning is Claude's job; these tests seed workspace files the
way a real run would and exercise every Python transition.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".claude/skills/sci-writing/scripts"))

import paper_pipeline  # noqa: E402


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_pipeline, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("SCI_OS_LEDGER", str(tmp_path / "ledger.jsonl"))
    return tmp_path


def _nonce(slug: str) -> str:
    return paper_pipeline.load_state(slug).nonce


def _seed_research(ws: Path, slug: str) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "research.md").write_text(
        "# Research\n\n"
        "## Evidence table\n\n"
        "| 1 | Mali2013 | RNA | 2013 | 10.1038/nature12373 | PubMed | high |\n\n"
        "## Verification receipts\n\n"
        "| # | API source | Returned title | First author | DOI |\n"
        "|---|---|---|---|---|\n"
        "| 1 | crossref | RNA-guided human genome engineering via Cas9 "
        "| Mali | 10.1038/nature12373 |\n"
    )
    (ws / f"{slug}.bib").write_text(
        "@article{Mali2013,\n  title = {RNA-guided human genome engineering via Cas9},\n"
        "  author = {Mali, L},\n  year = {2013},\n  doi = {10.1038/nature12373}\n}\n"
    )
    (ws / f"{slug}.quotes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "source": "test",
                "generated_at": "2026-04-13T10:30:00Z",
                "quotes": [
                    {
                        "key": "Mali2013",
                        "doi": "10.1038/nature12373",
                        "candidate_quotes": [
                            {
                                "text": "RNA-guided Cas9 enables precise editing of the human genome.",
                                "source_anchor": "10.1038/nature12373",
                                "source_type": "doi",
                                "confidence": "abstract",
                            }
                        ],
                    }
                ],
            }
        )
    )


def _seed_clean_draft(ws: Path, slug: str) -> None:
    (ws / f"{slug}-draft.md").write_text(
        "Plain prose section with no citation markers.\n"
    )
    # sidecar is not required when there are no [@Key] markers


def _seed_verification(ws: Path, slug: str, verdict: str, critical: int = 0,
                       major: int = 0, minor: int = 0, nonce: str | None = None) -> None:
    """Seed a structured verifier report at {slug}-verification.json.

    Tier 2: parsers read JSON, not markdown, and require a nonce match.
    """
    assert nonce is not None, "nonce required — Tier 2 contract"
    (ws / f"{slug}-verification.json").write_text(
        json.dumps({
            "version": 1,
            "nonce": nonce,
            "phase": "verification",
            "verdict": verdict,
            "counts": {"critical": critical, "major": major, "minor": minor},
            "findings": [],
        })
    )


def _seed_review(ws: Path, slug: str, verdict: str, fatal: int = 0,
                 major: int = 0, minor: int = 0, nonce: str | None = None) -> None:
    assert nonce is not None, "nonce required — Tier 2 contract"
    (ws / f"{slug}-review.json").write_text(
        json.dumps({
            "version": 1,
            "nonce": nonce,
            "phase": "review",
            "verdict": verdict,
            "counts": {"fatal": fatal, "major": major, "minor": minor},
            "findings": [],
        })
    )


def test_init_creates_workspace(tmp_root):
    payload = paper_pipeline.cmd_init("biomarker-intro", topic="X", section="intro")
    assert payload["status"] == "ok"
    state_file = tmp_root / "projects/sci-writing/biomarker-intro/.pipeline_state.json"
    assert state_file.exists()


def test_check_research_missing(tmp_root):
    paper_pipeline.cmd_init("miss", topic="X")
    result = paper_pipeline.cmd_check_research("miss")
    assert result["status"] == "incomplete"
    assert "research.md" in result["missing"]


def test_check_research_ok(tmp_root):
    paper_pipeline.cmd_init("ok-research", topic="X")
    ws = tmp_root / "projects/sci-writing/ok-research"
    _seed_research(ws, "ok-research")
    result = paper_pipeline.cmd_check_research("ok-research")
    assert result["status"] == "ok"


def test_check_research_rejects_fabricated_doi(tmp_root, monkeypatch):
    """Fix A — citation integrity defense-in-depth: check-research runs
    CrossRef verification on every DOI in the .bib before advancing to
    phase='researched'. A hallucinated DOI must fail here, one phase
    earlier than the mechanical gate, so a full writer cycle isn't
    wasted on a fabricated paper.
    """
    # Force the helper to return a failure — simulates CrossRef 404.
    def fake_verify(dois):
        return [
            {"doi": d, "error": "DOI not found in CrossRef.", "is_retracted": None}
            for d in dois
        ]

    monkeypatch.setattr(paper_pipeline, "_verify_dois_via_crossref", fake_verify)
    # The autouse fixture sets SCI_OS_SKIP_DOI_VERIFY=1; our monkeypatch
    # bypasses that by replacing the helper directly.

    paper_pipeline.cmd_init("fake-doi", topic="X")
    ws = tmp_root / "projects/sci-writing/fake-doi"
    _seed_research(ws, "fake-doi")  # seeds a plausible-looking bib entry

    result = paper_pipeline.cmd_check_research("fake-doi")
    assert result["status"] == "incomplete", (
        "check-research must refuse to advance when CrossRef can't verify "
        "a DOI — this is the pre-gate fabrication guard"
    )
    assert "CrossRef" in result["reason"]
    assert result["failed_dois"][0]["doi"] == "10.1038/nature12373"
    state = paper_pipeline.load_state("fake-doi")
    assert state.phase == "research-incomplete"


def test_extract_dois_from_bib_handles_both_delimiters(tmp_root):
    """DOI extraction regex must pick up both brace and quote delimiters
    and dedupe across multiple entries."""
    bib = tmp_root / "m.bib"
    bib.write_text(
        '@article{a,\n  doi = {10.1/aaa}\n}\n'
        '@article{b,\n  DOI = "10.2/bbb"\n}\n'
        '@article{c,\n  doi = {10.1/aaa}\n}\n'  # duplicate
    )
    dois = paper_pipeline._extract_dois_from_bib(bib)
    assert dois == ["10.1/aaa", "10.2/bbb"]


def test_gate_draft_passes_clean_draft(tmp_root):
    slug = "clean-draft"
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    _seed_research(ws, slug)
    _seed_clean_draft(ws, slug)
    paper_pipeline.cmd_check_research(slug)
    result = paper_pipeline.cmd_gate_draft(slug)
    assert result["status"] == "passed"
    assert result["exit_code"] == 0


def test_collect_verification_clean(tmp_root):
    slug = "verify-clean"
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    _seed_research(ws, slug)
    _seed_clean_draft(ws, slug)
    paper_pipeline.cmd_check_research(slug)
    paper_pipeline.cmd_gate_draft(slug)
    _seed_verification(ws, slug, "clean", nonce=_nonce(slug))
    result = paper_pipeline.cmd_collect_verification(slug)
    assert result["status"] == "ok"
    assert result["verdict"] == "clean"


def test_collect_review_ship(tmp_root):
    slug = "review-ship"
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    _seed_research(ws, slug)
    _seed_clean_draft(ws, slug)
    paper_pipeline.cmd_check_research(slug)
    paper_pipeline.cmd_gate_draft(slug)
    nonce = _nonce(slug)
    _seed_verification(ws, slug, "clean", nonce=nonce)
    paper_pipeline.cmd_collect_verification(slug)
    _seed_review(ws, slug, "ship", nonce=nonce)
    result = paper_pipeline.cmd_collect_review(slug)
    assert result["status"] == "ok"
    assert result["verdict"] == "ship"


def _run_through(slug: str, tmp_root: Path, verification_verdict: str,
                 review_verdict: str, critical: int = 0, fatal: int = 0,
                 major: int = 0) -> None:
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    _seed_research(ws, slug)
    _seed_clean_draft(ws, slug)
    paper_pipeline.cmd_check_research(slug)
    paper_pipeline.cmd_gate_draft(slug)
    nonce = _nonce(slug)
    _seed_verification(ws, slug, verification_verdict, critical=critical, nonce=nonce)
    paper_pipeline.cmd_collect_verification(slug)
    _seed_review(ws, slug, review_verdict, fatal=fatal, major=major, nonce=nonce)
    paper_pipeline.cmd_collect_review(slug)


def test_retry_fires_once_then_refuses(tmp_root):
    slug = "retry-loop"
    _run_through(slug, tmp_root, "refuse", "refuse", critical=1, fatal=1)

    first = paper_pipeline.cmd_retry_check(slug)
    assert first["status"] == "retry"
    assert first["retry_count"] == 1

    # Realistic retry: re-run gate_draft → verification → review → retry-check.
    ws = tmp_root / f"projects/sci-writing/{slug}"
    paper_pipeline.cmd_gate_draft(slug)
    nonce = _nonce(slug)
    _seed_verification(ws, slug, "refuse", critical=1, nonce=nonce)
    paper_pipeline.cmd_collect_verification(slug)
    _seed_review(ws, slug, "refuse", fatal=1, nonce=nonce)
    paper_pipeline.cmd_collect_review(slug)
    second = paper_pipeline.cmd_retry_check(slug)
    assert second["status"] == "refused"


def test_retry_ok_path(tmp_root):
    slug = "ok-path"
    _run_through(slug, tmp_root, "clean", "ship")
    result = paper_pipeline.cmd_retry_check(slug)
    assert result["status"] == "ok"


def test_retry_major_only_returns_revise(tmp_root):
    slug = "majors"
    _run_through(slug, tmp_root, "revise", "revise", major=2)
    result = paper_pipeline.cmd_retry_check(slug)
    assert result["status"] == "revise"
    assert result["major"] >= 2


def test_finalize_ok_on_ship(tmp_root):
    slug = "finalize-ok"
    _run_through(slug, tmp_root, "clean", "ship")
    paper_pipeline.cmd_retry_check(slug)
    result = paper_pipeline.cmd_finalize(slug)
    assert result["status"] == "ok"


def test_finalize_blocked_when_retry_pending(tmp_root):
    """Tier 2 precondition: finalize cannot run while phase=retry."""
    slug = "finalize-retry"
    _run_through(slug, tmp_root, "refuse", "refuse", critical=1, fatal=1)
    paper_pipeline.cmd_retry_check(slug)  # phase -> retry (first retry allowed)
    with pytest.raises(paper_pipeline.PipelineError):
        paper_pipeline.cmd_finalize(slug)


def test_finalize_refuses_blocked_gate_even_if_semantic_checks_pass(tmp_root):
    """Citation integrity gate: the mechanical verifier (verify_ops.py)
    catches fabricated quotes and unmatched bib keys. Exit 2 = one or
    more CRITICAL findings. The semantic verifier/reviewer operate on
    the sidecar and can miss what the mechanical gate caught, so
    finalize MUST NOT save when last_gate_status='blocked', even if
    both downstream agents return clean verdicts.

    Regression for the finalize escape hatch where a blocked gate
    combined with clean semantic passes would reach phase='finalized'.
    """
    slug = "blocked-gate-semantic-clean"
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    _seed_research(ws, slug)
    # Seed a draft that will trip the mechanical gate: a [@Key] marker
    # whose sidecar claims a source anchor that doesn't exist. We fake
    # the blocked state directly since verify_ops is integration-tested
    # elsewhere — the point here is the finalize enforcement contract.
    _seed_clean_draft(ws, slug)
    paper_pipeline.cmd_check_research(slug)
    paper_pipeline.cmd_gate_draft(slug)

    # Force the blocked state (simulates verify_ops returning exit 2).
    state = paper_pipeline.load_state(slug)
    state.last_gate_status = "blocked"
    state.mechanical_exits[-1] = 2
    paper_pipeline.save_state(state)

    nonce = _nonce(slug)
    _seed_verification(ws, slug, "clean", nonce=nonce)
    paper_pipeline.cmd_collect_verification(slug)
    _seed_review(ws, slug, "ship", nonce=nonce)
    paper_pipeline.cmd_collect_review(slug)
    paper_pipeline.cmd_retry_check(slug)

    result = paper_pipeline.cmd_finalize(slug)
    assert result["status"] == "refused", (
        "finalize must refuse when the mechanical gate was blocked, "
        "regardless of semantic verifier/reviewer verdicts"
    )
    assert "gate" in result["reason"].lower()
    final_state = paper_pipeline.load_state(slug)
    assert final_state.phase == "refused"


def test_finalize_refused_terminal_after_retry_budget(tmp_root):
    """After the retry budget is exhausted on FATAL, phase=refused and
    finalize is locked with the refused-terminal error."""
    slug = "finalize-refused-terminal"
    _run_through(slug, tmp_root, "refuse", "refuse", critical=1, fatal=1)
    paper_pipeline.cmd_retry_check(slug)  # retry 1 -> phase=retry

    ws = tmp_root / f"projects/sci-writing/{slug}"
    paper_pipeline.cmd_gate_draft(slug)
    nonce = _nonce(slug)
    _seed_verification(ws, slug, "refuse", critical=1, nonce=nonce)
    paper_pipeline.cmd_collect_verification(slug)
    _seed_review(ws, slug, "refuse", fatal=1, nonce=nonce)
    paper_pipeline.cmd_collect_review(slug)
    paper_pipeline.cmd_retry_check(slug)  # budget exhausted -> phase=refused

    with pytest.raises(paper_pipeline.PipelineError, match="refused"):
        paper_pipeline.cmd_finalize(slug)


# ============================================================
# Tier 2 adversarial regression suite
# ============================================================


def test_reinit_refused_without_force(tmp_root):
    """T2.3: init must not overwrite existing state — retry budget reset
    was the old hole."""
    slug = "no-reinit"
    paper_pipeline.cmd_init(slug)
    with pytest.raises(paper_pipeline.PipelineError, match="Re-init is forbidden"):
        paper_pipeline.cmd_init(slug)


def test_reinit_with_force_appends_ledger(tmp_root, monkeypatch):
    """--force rotates the nonce and logs to the ledger outside the workspace."""
    slug = "force-reinit"
    ledger = tmp_root / "ledger.jsonl"
    monkeypatch.setenv("SCI_OS_LEDGER", str(ledger))

    first = paper_pipeline.cmd_init(slug)
    first_nonce = first["nonce"]

    second = paper_pipeline.cmd_init(slug, force=True)
    assert second["nonce"] != first_nonce

    assert ledger.exists()
    entries = [json.loads(line) for line in ledger.read_text().splitlines() if line]
    assert any(
        e.get("event") == "forced-reinit" and e.get("slug") == slug for e in entries
    )


def test_out_of_order_gate_draft_rejected(tmp_root):
    """T2.2: gate-draft cannot run before check-research."""
    slug = "out-of-order"
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    _seed_research(ws, slug)
    _seed_clean_draft(ws, slug)
    # Skip check-research → state is still phase='init'
    with pytest.raises(paper_pipeline.PipelineError, match="cannot run from phase='init'"):
        paper_pipeline.cmd_gate_draft(slug)


def test_out_of_order_finalize_before_retry_check(tmp_root):
    slug = "finalize-too-early"
    _run_through(slug, tmp_root, "clean", "ship")
    # Skip retry-check; phase is still 'reviewed'
    with pytest.raises(paper_pipeline.PipelineError):
        paper_pipeline.cmd_finalize(slug)


def test_forged_verification_report_rejected(tmp_root):
    """T2.6: a verification.json that doesn't echo the current nonce is
    treated as a forgery and refuses."""
    slug = "forged"
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    _seed_research(ws, slug)
    _seed_clean_draft(ws, slug)
    paper_pipeline.cmd_check_research(slug)
    paper_pipeline.cmd_gate_draft(slug)
    # Write a report with a bogus nonce
    _seed_verification(ws, slug, "clean", nonce="deadbeef" * 4)
    with pytest.raises(paper_pipeline.ForgeryError):
        paper_pipeline.cmd_collect_verification(slug)


def test_missing_verification_report_rejected(tmp_root):
    slug = "no-report"
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    _seed_research(ws, slug)
    _seed_clean_draft(ws, slug)
    paper_pipeline.cmd_check_research(slug)
    paper_pipeline.cmd_gate_draft(slug)
    with pytest.raises(paper_pipeline.PipelineError, match="Structured report missing"):
        paper_pipeline.cmd_collect_verification(slug)


def test_invalid_verdict_rejected(tmp_root):
    slug = "bad-verdict"
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    _seed_research(ws, slug)
    _seed_clean_draft(ws, slug)
    paper_pipeline.cmd_check_research(slug)
    paper_pipeline.cmd_gate_draft(slug)
    nonce = _nonce(slug)
    (ws / f"{slug}-verification.json").write_text(
        json.dumps({
            "version": 1,
            "nonce": nonce,
            "phase": "verification",
            "verdict": "shiplol",
            "counts": {"critical": 0, "major": 0, "minor": 0},
            "findings": [],
        })
    )
    with pytest.raises(paper_pipeline.PipelineError, match="invalid verdict"):
        paper_pipeline.cmd_collect_verification(slug)


def test_refused_state_is_terminal(tmp_root):
    """T2.4: once phase=refused, every command except status is rejected."""
    slug = "terminal"
    _run_through(slug, tmp_root, "refuse", "refuse", critical=1, fatal=1)
    paper_pipeline.cmd_retry_check(slug)  # retry 1

    ws = tmp_root / f"projects/sci-writing/{slug}"
    paper_pipeline.cmd_gate_draft(slug)
    nonce = _nonce(slug)
    _seed_verification(ws, slug, "refuse", critical=1, nonce=nonce)
    paper_pipeline.cmd_collect_verification(slug)
    _seed_review(ws, slug, "refuse", fatal=1, nonce=nonce)
    paper_pipeline.cmd_collect_review(slug)
    paper_pipeline.cmd_retry_check(slug)  # phase=refused

    # Every mutating command is locked
    for fn in (
        paper_pipeline.cmd_check_research,
        paper_pipeline.cmd_gate_draft,
        paper_pipeline.cmd_collect_verification,
        paper_pipeline.cmd_collect_review,
        paper_pipeline.cmd_retry_check,
        paper_pipeline.cmd_finalize,
    ):
        with pytest.raises(paper_pipeline.PipelineError, match="refused"):
            fn(slug)
    # Status still works
    assert paper_pipeline.cmd_status(slug)["phase"] == "refused"


def test_atomic_state_write_no_temp_leftover(tmp_root):
    """T2.5: after save_state, no .tmp.* shrapnel remains in the workspace."""
    slug = "atomic"
    paper_pipeline.cmd_init(slug)
    ws = tmp_root / f"projects/sci-writing/{slug}"
    leftovers = [p for p in ws.iterdir() if ".tmp." in p.name]
    assert leftovers == []
