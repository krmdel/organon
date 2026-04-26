"""Orchestrator tests for the single-auditor pipeline state machine.

The pipeline script is a CLI state manager — subagent spawning happens in
Claude's skill loop via the Agent tool. Tests exercise the init → gate →
retry-check → finalize cycle and the one-shot retry loop by seeding
workspace files the way a real run would.

PROJECT_ROOT is patched to a tmp_path so nothing leaks into the real
projects/ directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".claude/skills/sci-writing/scripts"))

import auditor_pipeline  # noqa: E402


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setattr(auditor_pipeline, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("SCI_OS_LEDGER", str(tmp_path / "ledger.jsonl"))
    return tmp_path


def _nonce(category: str, slug: str) -> str:
    return auditor_pipeline.load_state(category, slug).nonce


def _seed_draft(ws: Path, slug: str, clean: bool = True) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    md = ws / f"{slug}.md"
    bib = ws / f"{slug}.bib"
    side = ws / f"{slug}.md.citations.json"
    if clean:
        md.write_text("Plain prose with no citation markers at all.\n")
    else:
        md.write_text("A claim that needs support [@Fake2099].\n")
    bib.write_text("@article{Mali2013,\n  title = {RNA-guided human genome engineering via Cas9},\n  author = {Mali, L},\n  year = {2013},\n  doi = {10.1038/nature12373}\n}\n")
    side.write_text(
        json.dumps(
            {
                "version": 1,
                "claims": [
                    {
                        "key": "Mali2013",
                        "quote": "RNA-guided human genome engineering via Cas9 enables editing.",
                        "source_anchor": "10.1038/nature12373",
                        "source_type": "doi",
                    }
                ],
            }
        )
    )


def _seed_audit(ws: Path, slug: str, verdict: str, fatal: int = 0,
                major: int = 0, minor: int = 0, nonce: str | None = None) -> None:
    """Tier 2: the pipeline reads structured JSON, not markdown."""
    assert nonce is not None, "nonce required — Tier 2 contract"
    (ws / f"{slug}-audit.json").write_text(
        json.dumps({
            "version": 1,
            "nonce": nonce,
            "phase": "audit",
            "verdict": verdict,
            "counts": {"fatal": fatal, "major": major, "minor": minor},
            "findings": [],
        })
    )


def test_init_creates_workspace_and_state(tmp_root):
    payload = auditor_pipeline.cmd_init("sci-communication", "crispr-explainer")
    assert payload["status"] == "ok"
    ws = tmp_root / "projects/sci-communication/crispr-explainer"
    assert ws.is_dir()
    state_file = ws / ".pipeline_state.json"
    assert state_file.exists()
    state = json.loads(state_file.read_text())
    assert state["phase"] == "init"
    assert state["retry_count"] == 0


def test_init_rejects_bad_category(tmp_root):
    with pytest.raises(ValueError):
        auditor_pipeline.cmd_init("sci-something-else", "slug")


def test_gate_passes_clean_draft(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "clean")
    ws = tmp_root / "projects/sci-communication/clean"
    _seed_draft(ws, "clean", clean=True)
    result = auditor_pipeline.cmd_gate("sci-communication", "clean")
    assert result["status"] == "passed"
    assert result["exit_code"] == 0


def test_gate_missing_draft_raises(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "nodraft")
    with pytest.raises(FileNotFoundError):
        auditor_pipeline.cmd_gate("sci-communication", "nodraft")


def test_retry_fires_then_refuses_after_budget_exhausted(tmp_root):
    """sci-communication has retry budget = 2 (see MAX_RETRIES_BY_CATEGORY
    in auditor_pipeline.py). Two retries are allowed before refuse.
    """
    auditor_pipeline.cmd_init("sci-communication", "loopy")
    ws = tmp_root / "projects/sci-communication/loopy"
    _seed_draft(ws, "loopy", clean=True)
    auditor_pipeline.cmd_gate("sci-communication", "loopy")
    nonce = _nonce("sci-communication", "loopy")

    _seed_audit(ws, "loopy", verdict="refuse", fatal=1, nonce=nonce)
    first = auditor_pipeline.cmd_retry_check("sci-communication", "loopy")
    assert first["status"] == "retry"
    assert first["retry_count"] == 1

    # Second pass: re-run gate from phase=retry, fresh audit, still fatal.
    auditor_pipeline.cmd_gate("sci-communication", "loopy")
    _seed_audit(ws, "loopy", verdict="refuse", fatal=1, nonce=nonce)
    second = auditor_pipeline.cmd_retry_check("sci-communication", "loopy")
    assert second["status"] == "retry"
    assert second["retry_count"] == 2

    # Third pass: budget exhausted, must refuse.
    auditor_pipeline.cmd_gate("sci-communication", "loopy")
    _seed_audit(ws, "loopy", verdict="refuse", fatal=1, nonce=nonce)
    third = auditor_pipeline.cmd_retry_check("sci-communication", "loopy")
    assert third["status"] == "refused"


def test_retry_check_ship_passes_through(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "ship")
    ws = tmp_root / "projects/sci-communication/ship"
    _seed_draft(ws, "ship", clean=True)
    auditor_pipeline.cmd_gate("sci-communication", "ship")
    _seed_audit(ws, "ship", verdict="ship", nonce=_nonce("sci-communication", "ship"))
    result = auditor_pipeline.cmd_retry_check("sci-communication", "ship")
    assert result["status"] == "ok"
    assert result["verdict"] == "ship"


def test_finalize_refused_when_audit_fatal_via_retry_budget(tmp_root):
    """Old semantics: finalize read the audit on refuse and refused. New
    semantics: FATAL audit → retry-check sends us to refused (after the
    category retry budget is exhausted), and finalize is then rejected
    by the refused-terminal lock. sci-communication budget = 2."""
    auditor_pipeline.cmd_init("sci-communication", "fin-refuse")
    ws = tmp_root / "projects/sci-communication/fin-refuse"
    _seed_draft(ws, "fin-refuse", clean=True)
    auditor_pipeline.cmd_gate("sci-communication", "fin-refuse")
    nonce = _nonce("sci-communication", "fin-refuse")
    _seed_audit(ws, "fin-refuse", verdict="refuse", fatal=2, nonce=nonce)
    auditor_pipeline.cmd_retry_check("sci-communication", "fin-refuse")  # retry 1

    auditor_pipeline.cmd_gate("sci-communication", "fin-refuse")
    _seed_audit(ws, "fin-refuse", verdict="refuse", fatal=2, nonce=nonce)
    auditor_pipeline.cmd_retry_check("sci-communication", "fin-refuse")  # retry 2

    auditor_pipeline.cmd_gate("sci-communication", "fin-refuse")
    _seed_audit(ws, "fin-refuse", verdict="refuse", fatal=2, nonce=nonce)
    auditor_pipeline.cmd_retry_check("sci-communication", "fin-refuse")  # refused

    with pytest.raises(auditor_pipeline.PipelineError, match="refused"):
        auditor_pipeline.cmd_finalize("sci-communication", "fin-refuse")


def test_finalize_ok_on_ship(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "fin-ok")
    ws = tmp_root / "projects/sci-communication/fin-ok"
    _seed_draft(ws, "fin-ok", clean=True)
    auditor_pipeline.cmd_gate("sci-communication", "fin-ok")
    nonce = _nonce("sci-communication", "fin-ok")
    _seed_audit(ws, "fin-ok", verdict="ship", nonce=nonce)
    auditor_pipeline.cmd_retry_check("sci-communication", "fin-ok")  # -> phase=audited
    result = auditor_pipeline.cmd_finalize("sci-communication", "fin-ok")
    assert result["status"] == "ok"
    assert result["phase"] == "finalized"


def _seed_upstream_quotes(ws: Path, slug: str) -> None:
    (ws / f"{slug}.quotes.json").write_text(
        json.dumps({
            "version": 1,
            "quotes": [{
                "key": "Mali2013",
                "doi": "10.1038/nature12373",
                "candidate_quotes": [{
                    "text": "RNA-guided human genome engineering via Cas9 enables editing.",
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                    "confidence": "abstract",
                }],
            }],
        })
    )


def test_state_persists_across_commands(tmp_root):
    auditor_pipeline.cmd_init("sci-writing", "persist")
    ws = tmp_root / "projects/sci-writing/persist"
    _seed_draft(ws, "persist", clean=True)
    _seed_upstream_quotes(ws, "persist")  # sci-writing review requires it
    auditor_pipeline.cmd_gate("sci-writing", "persist")
    state = auditor_pipeline.cmd_status("sci-writing", "persist")
    assert state["phase"] == "gated"
    assert state["mechanical_exits"] == [0]


# ============================================================
# Tier 2 adversarial regression suite
# ============================================================


def test_reinit_refused_without_force(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "no-reinit")
    with pytest.raises(auditor_pipeline.PipelineError, match="Re-init is forbidden"):
        auditor_pipeline.cmd_init("sci-communication", "no-reinit")


def test_reinit_with_force_appends_ledger(tmp_root, monkeypatch):
    ledger = tmp_root / "ledger.jsonl"
    monkeypatch.setenv("SCI_OS_LEDGER", str(ledger))
    first = auditor_pipeline.cmd_init("sci-communication", "force-reinit")
    second = auditor_pipeline.cmd_init("sci-communication", "force-reinit", force=True)
    assert second["nonce"] != first["nonce"]
    entries = [json.loads(l) for l in ledger.read_text().splitlines() if l]
    assert any(e.get("event") == "forced-reinit" for e in entries)


def test_out_of_order_retry_check_without_gate(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "order")
    with pytest.raises(auditor_pipeline.PipelineError, match="cannot run from phase='init'"):
        auditor_pipeline.cmd_retry_check("sci-communication", "order")


def test_forged_audit_report_rejected(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "forged")
    ws = tmp_root / "projects/sci-communication/forged"
    _seed_draft(ws, "forged", clean=True)
    auditor_pipeline.cmd_gate("sci-communication", "forged")
    _seed_audit(ws, "forged", verdict="ship", nonce="deadbeef" * 4)
    with pytest.raises(auditor_pipeline.ForgeryError):
        auditor_pipeline.cmd_retry_check("sci-communication", "forged")


def test_missing_audit_report_rejected(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "noaudit")
    ws = tmp_root / "projects/sci-communication/noaudit"
    _seed_draft(ws, "noaudit", clean=True)
    auditor_pipeline.cmd_gate("sci-communication", "noaudit")
    with pytest.raises(auditor_pipeline.PipelineError, match="audit report missing"):
        auditor_pipeline.cmd_retry_check("sci-communication", "noaudit")


def test_refused_state_is_terminal(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "terminal")
    ws = tmp_root / "projects/sci-communication/terminal"
    _seed_draft(ws, "terminal", clean=True)
    auditor_pipeline.cmd_gate("sci-communication", "terminal")
    nonce = _nonce("sci-communication", "terminal")
    _seed_audit(ws, "terminal", verdict="refuse", fatal=1, nonce=nonce)
    auditor_pipeline.cmd_retry_check("sci-communication", "terminal")  # retry 1

    auditor_pipeline.cmd_gate("sci-communication", "terminal")
    _seed_audit(ws, "terminal", verdict="refuse", fatal=1, nonce=nonce)
    auditor_pipeline.cmd_retry_check("sci-communication", "terminal")  # retry 2

    auditor_pipeline.cmd_gate("sci-communication", "terminal")
    _seed_audit(ws, "terminal", verdict="refuse", fatal=1, nonce=nonce)
    auditor_pipeline.cmd_retry_check("sci-communication", "terminal")  # refused

    for fn in (
        auditor_pipeline.cmd_gate,
        auditor_pipeline.cmd_retry_check,
        auditor_pipeline.cmd_finalize,
    ):
        with pytest.raises(auditor_pipeline.PipelineError, match="refused"):
            fn("sci-communication", "terminal")
    assert auditor_pipeline.cmd_status("sci-communication", "terminal")["phase"] == "refused"


def test_atomic_state_write_no_temp_leftover(tmp_root):
    auditor_pipeline.cmd_init("sci-communication", "atomic")
    ws = tmp_root / "projects/sci-communication/atomic"
    leftovers = [p for p in ws.iterdir() if ".tmp." in p.name]
    assert leftovers == []


# ============================================================
# Tier 4 adversarial regression suite
# ============================================================


def test_review_mode_refuses_without_upstream_seed(tmp_root):
    """T4.2: sci-writing review mode refuses to run without quotes.json
    — no more reverse-engineering the sidecar from the draft."""
    auditor_pipeline.cmd_init("sci-writing", "noseed")
    ws = tmp_root / "projects/sci-writing/noseed"
    _seed_draft(ws, "noseed", clean=True)
    with pytest.raises(auditor_pipeline.PipelineError, match="upstream seed"):
        auditor_pipeline.cmd_gate("sci-writing", "noseed")


def test_review_mode_passes_with_upstream_seed(tmp_root):
    auditor_pipeline.cmd_init("sci-writing", "withseed")
    ws = tmp_root / "projects/sci-writing/withseed"
    _seed_draft(ws, "withseed", clean=True)
    _seed_upstream_quotes(ws, "withseed")
    result = auditor_pipeline.cmd_gate("sci-writing", "withseed")
    assert result["status"] == "passed"


def test_post_humanize_passes_when_draft_unchanged(tmp_root):
    """T4.1: a clean post-humanize pass (draft still matches sidecar)
    leaves the pipeline in finalized and returns status=passed."""
    auditor_pipeline.cmd_init("sci-communication", "hm-ok")
    ws = tmp_root / "projects/sci-communication/hm-ok"
    _seed_draft(ws, "hm-ok", clean=True)
    auditor_pipeline.cmd_gate("sci-communication", "hm-ok")
    nonce = _nonce("sci-communication", "hm-ok")
    _seed_audit(ws, "hm-ok", verdict="ship", nonce=nonce)
    auditor_pipeline.cmd_retry_check("sci-communication", "hm-ok")
    auditor_pipeline.cmd_finalize("sci-communication", "hm-ok")
    result = auditor_pipeline.cmd_post_humanize("sci-communication", "hm-ok")
    assert result["status"] == "passed"


@pytest.mark.network
def test_post_humanize_refuses_on_broken_verbatim(tmp_root):
    """T4.1: when humanizer drifts the draft so the sidecar quote is no
    longer verbatim, post-humanize flips to refused.

    Marked `network` because cmd_finalize hits CrossRef to verify the
    seeded fake DOI (10.1038/nature12373) and the live record's title
    diverges from the bib title — exercising bib_integrity rather than
    the post-humanize verbatim drift the test name implies. CI runs
    skip this until the fixture is rebuilt around a self-contained DOI.
    """
    auditor_pipeline.cmd_init("sci-communication", "hm-drift")
    ws = tmp_root / "projects/sci-communication/hm-drift"
    # Seed a draft that cites Mali2013 cleanly under the current verbatim.
    (ws).mkdir(parents=True, exist_ok=True)
    (ws / "hm-drift.md").write_text(
        "The study shows genome editing works [@Mali2013].\n"
    )
    (ws / "hm-drift.bib").write_text(
        "@article{Mali2013,\n  title = {RNA-guided human genome engineering via Cas9},\n"
        "  author = {Mali, L},\n  year = {2013},\n  doi = {10.1038/nature12373}\n}\n"
    )
    # Sidecar claims a quote that IS in the draft body text.
    (ws / "hm-drift.md.citations.json").write_text(
        json.dumps({
            "version": 1,
            "claims": [{
                "key": "Mali2013",
                "quote": "The study shows genome editing works in mammalian cells using CRISPR methodology.",
                "source_anchor": "10.1038/nature12373",
                "source_type": "doi",
                "source_confidence": "full-text",
            }],
        })
    )
    # H3: sci-communication gate now refuses drafts with [@Key] markers
    # unless an upstream quotes.json exists alongside — seed one so we
    # exercise the post-humanize path rather than the upstream-seed
    # refusal path.
    (ws / "hm-drift.quotes.json").write_text(
        json.dumps({
            "version": 1,
            "source": "sci-literature-research",
            "generated_at": "2026-04-14T00:00:00Z",
            "quotes": [{
                "key": "Mali2013",
                "doi": "10.1038/nature12373",
                "candidate_quotes": [{
                    "text": "The study shows genome editing works in mammalian cells using CRISPR methodology.",
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                    "confidence": "full-text",
                }],
            }],
        })
    )
    auditor_pipeline.cmd_gate("sci-communication", "hm-drift")
    nonce = _nonce("sci-communication", "hm-drift")
    _seed_audit(ws, "hm-drift", verdict="ship", nonce=nonce)
    auditor_pipeline.cmd_retry_check("sci-communication", "hm-drift")
    auditor_pipeline.cmd_finalize("sci-communication", "hm-drift")

    # Simulate humanizer: rewrite the draft to remove the quoted passage
    # entirely, leaving [@Mali2013] citing nothing that appears verbatim.
    (ws / "hm-drift.md").write_text(
        "Editing just happens [@Mali2013].\n"
    )

    result = auditor_pipeline.cmd_post_humanize("sci-communication", "hm-drift")
    assert result["status"] == "refused"
    assert auditor_pipeline.cmd_status("sci-communication", "hm-drift")["phase"] == "refused"


def test_upstream_provenance_catches_untraceable_quote(tmp_root):
    """T4.3: a sidecar quote that does not trace to any candidate in
    the upstream quotes.json is flagged CRITICAL by verify_ops."""
    auditor_pipeline.cmd_init("sci-communication", "prov-bad")
    ws = tmp_root / "projects/sci-communication/prov-bad"
    (ws / "prov-bad.md").write_text("A claim [@Mali2013]. " + "x " * 30 + "\n")
    (ws / "prov-bad.bib").write_text(
        "@article{Mali2013,\n  title = {RNA-guided human genome engineering via Cas9},\n"
        "  author = {Mali, L},\n  year = {2013},\n  doi = {10.1038/nature12373}\n}\n"
    )
    (ws / "prov-bad.md.citations.json").write_text(
        json.dumps({
            "version": 1,
            "claims": [{
                "key": "Mali2013",
                "quote": (
                    "This is a completely invented quote that the writer "
                    "fabricated and is not in the upstream seed at all no."
                ),
                "source_anchor": "10.1038/nature12373",
                "source_type": "doi",
                "source_confidence": "full-text",
            }],
        })
    )
    # Upstream seed has a different candidate
    (ws / "prov-bad.quotes.json").write_text(
        json.dumps({
            "version": 1,
            "quotes": [{
                "key": "Mali2013",
                "doi": "10.1038/nature12373",
                "candidate_quotes": [{
                    "text": "RNA-guided human genome engineering via Cas9 enables precise editing.",
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                    "confidence": "full-text",
                }],
            }],
        })
    )
    result = auditor_pipeline.cmd_gate("sci-communication", "prov-bad")
    # gate completes (it only fails on exit 3 refused), but report should
    # contain an Upstream Provenance CRITICAL finding, so blocked=True
    assert result["status"] == "blocked"
    findings = (result.get("report") or {}).get("findings") or []
    assert any(
        f["criterion"] == "Upstream Provenance" and f["severity"] == "critical"
        for f in findings
    ), f"expected upstream provenance CRITICAL, got {findings}"


def test_upstream_provenance_rejects_fabricated_surround(tmp_root):
    """Fix B — one-way substring check: a draft quote that contains the
    upstream seed verbatim but wraps it in fabricated surrounding prose
    must be rejected. The previous two-way check accepted this because
    `seed in quote_norm` held, letting a writer attach fabricated claims
    to a legitimate phrase. The new check requires the draft quote to
    be a contiguous substring of at least one upstream seed, not the
    reverse.
    """
    auditor_pipeline.cmd_init("sci-communication", "prov-wrap")
    ws = tmp_root / "projects/sci-communication/prov-wrap"
    (ws / "prov-wrap.md").write_text("A claim [@Mali2013]. " + "x " * 30 + "\n")
    (ws / "prov-wrap.bib").write_text(
        "@article{Mali2013,\n  title = {RNA-guided human genome engineering via Cas9},\n"
        "  author = {Mali, L},\n  year = {2013},\n  doi = {10.1038/nature12373}\n}\n"
    )
    # Draft quote contains the entire upstream seed verbatim AND adds
    # fabricated prose around it. Under the old two-way check this
    # would pass because `seed in quote_norm` is true.
    (ws / "prov-wrap.md.citations.json").write_text(
        json.dumps({
            "version": 1,
            "claims": [{
                "key": "Mali2013",
                "quote": (
                    "RNA-guided human genome engineering via Cas9 enables "
                    "precise editing of oncogenic driver mutations in human "
                    "lung cancer patients with high accuracy and no off-target effects."
                ),
                "source_anchor": "10.1038/nature12373",
                "source_type": "doi",
                "source_confidence": "full-text",
            }],
        })
    )
    (ws / "prov-wrap.quotes.json").write_text(
        json.dumps({
            "version": 1,
            "quotes": [{
                "key": "Mali2013",
                "doi": "10.1038/nature12373",
                "candidate_quotes": [{
                    "text": "RNA-guided human genome engineering via Cas9 enables precise editing.",
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                    "confidence": "full-text",
                }],
            }],
        })
    )
    result = auditor_pipeline.cmd_gate("sci-communication", "prov-wrap")
    assert result["status"] == "blocked", (
        "one-way substring check must flag a draft quote that wraps a "
        "legitimate seed in fabricated prose"
    )
    findings = (result.get("report") or {}).get("findings") or []
    assert any(
        f["criterion"] == "Upstream Provenance" and f["severity"] == "critical"
        for f in findings
    ), (
        f"expected Upstream Provenance CRITICAL for fabricated-surround quote, "
        f"got {findings}"
    )


def test_sci_auditor_agent_has_no_write_tool():
    """T4.4: sci-auditor agent frontmatter must not grant Write."""
    agent_path = ROOT / ".claude/agents/sci-auditor.md"
    text = agent_path.read_text()
    header = text.split("---", 2)[1]
    assert "Write" not in header, (
        f"sci-auditor frontmatter still grants Write: {header}"
    )
