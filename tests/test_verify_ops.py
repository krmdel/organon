"""Pytest coverage for the sci-writing mechanical verification gate.

Locks in the 9 end-to-end behaviors validated in the fabrication-guardrails
session. All tests mock `verify_ops.verify_doi` so no network is required.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".claude/skills/sci-writing/scripts"))

import verify_ops  # noqa: E402


MOCK_DB = {
    "10.1038/nature12373": {
        "doi": "10.1038/nature12373",
        "title": "RNA-guided human genome engineering via Cas9",
        "authors": ["Mali"],
        "published": {},
        "journal": "Science",
        "is_retracted": False,
        "retraction_info": None,
        "type": "journal-article",
    },
    "10.1038/retracted-paper": {
        "doi": "10.1038/retracted-paper",
        "title": "Some fake finding",
        "authors": ["X"],
        "published": {},
        "journal": "X",
        "is_retracted": True,
        "retraction_info": {"type": "retraction"},
        "type": "journal-article",
    },
}


def mock_verify_doi(doi):
    if doi not in MOCK_DB:
        raise ValueError(f"DOI '{doi}' not found in CrossRef.")
    return MOCK_DB[doi]


def mock_verify_citation(entry):
    """MOCK_DB lookup dispatched by identifier — mirrors the dispatch
    behavior of repro.citation_verify.verify_citation."""
    doi = (entry.get("doi") or "").strip().lower()
    if doi in MOCK_DB:
        return MOCK_DB[doi]
    raise ValueError(f"DOI '{doi}' not found in CrossRef.")


@pytest.fixture(autouse=True)
def patch_crossref(monkeypatch):
    """Override the conftest entry-mirroring stub with the MOCK_DB-driven
    lookup so tests like test_retracted_doi_blocked and
    test_fabricated_title_blocked see the metadata they expect."""
    from repro import citation_verify
    monkeypatch.setattr(verify_ops, "verify_doi", mock_verify_doi)
    monkeypatch.setattr(verify_ops, "verify_citation", mock_verify_citation)
    monkeypatch.setattr(citation_verify, "verify_doi", mock_verify_doi)
    monkeypatch.setattr(citation_verify, "verify_citation", mock_verify_citation)


def make_bib(key, title, doi):
    return (
        f"@article{{{key},\n"
        f"  title = {{{title}}},\n"
        f"  author = {{Mali, L}},\n"
        f"  year = {{2013}},\n"
        f"  doi = {{{doi}}}\n"
        f"}}\n"
    )


def write_case(tmp_path, name, manuscript, bib, sidecar=None, source=None):
    mp = tmp_path / f"{name}.md"
    bp = tmp_path / f"{name}.bib"
    mp.write_text(manuscript)
    bp.write_text(bib)
    if sidecar is not None:
        (tmp_path / f"{name}.md.citations.json").write_text(json.dumps(sidecar))
    sp = None
    if source is not None:
        sp = tmp_path / f"{name}_source.md"
        sp.write_text(source)
    return str(mp), str(bp), str(sp) if sp else None


def test_clean_pass(tmp_path):
    mp, bp, _ = write_case(
        tmp_path,
        "clean",
        "Cas9 enables editing [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Mali2013",
                    "quote": "RNA-guided human genome engineering via Cas9 is a thing",
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert r["blocked"] is False
    assert r["summary"]["critical"] == 0


def test_fabricated_title_blocked(tmp_path):
    mp, bp, _ = write_case(
        tmp_path,
        "fab",
        "Wrong title [@Fake2024].",
        make_bib("Fake2024", "Quantum gravity in four dimensions", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Fake2024",
                    "quote": "Quantum gravity in four dimensions blah blah padding",
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert r["blocked"] is True
    assert any("Title mismatch" in f["finding"] for f in r["findings"])


def test_retracted_doi_blocked(tmp_path):
    mp, bp, _ = write_case(
        tmp_path,
        "retracted",
        "From retracted paper [@Bad2020].",
        make_bib("Bad2020", "Some fake finding", "10.1038/retracted-paper"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Bad2020",
                    "quote": "Some fake finding from this paper is padding",
                    "source_anchor": "10.1038/retracted-paper",
                    "source_type": "doi",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert r["blocked"] is True
    assert any("RETRACTED" in f["finding"] for f in r["findings"])


def test_missing_sidecar_blocked(tmp_path):
    mp, bp, _ = write_case(
        tmp_path,
        "nosc",
        "Claim with citation [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert r["blocked"] is True
    assert any("no sidecar" in f["finding"] for f in r["findings"])


def test_fabricated_quote_blocked(tmp_path):
    mp, bp, sp = write_case(
        tmp_path,
        "fabquote",
        "Statement [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Mali2013",
                    "quote": "This quote was completely invented by the writer",
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                }
            ],
        },
        source="RNA-guided genome engineering via Cas9 enables precise editing.",
    )
    r = verify_ops.run_verification(mp, bib_path=bp, source_path=sp, apply_fixes=False)
    assert r["blocked"] is True
    assert any("NOT found in the" in f["finding"] for f in r["findings"])


def test_bad_paperclip_anchor_blocked(tmp_path):
    mp, bp, _ = write_case(
        tmp_path,
        "pc",
        "Biomedical finding [@Chen2024].",
        make_bib("Chen2024", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Chen2024",
                    "quote": "RNA-guided human genome engineering via Cas9 long enough",
                    "source_anchor": "https://citations.gxl.ai/papers/PMC123",
                    "source_type": "paperclip",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert r["blocked"] is True
    assert any("does not match" in f["finding"] for f in r["findings"])


def test_dead_doi_flagged_not_blocked(tmp_path):
    mp, bp, _ = write_case(
        tmp_path,
        "dead",
        "Claim with dead doi [@Dead2023].",
        make_bib("Dead2023", "RNA-guided human genome engineering via Cas9", "10.1038/does-not-exist"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Dead2023",
                    "quote": "RNA-guided human genome engineering via Cas9 padding",
                    "source_anchor": "10.1038/does-not-exist",
                    "source_type": "doi",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert r["blocked"] is False
    assert r["summary"]["major"] >= 1


def test_no_bib_refused_when_cited(tmp_path):
    """Cited content (has [@Key] markers) without a bib must still be refused.
    The pure-expertise escape hatch ONLY applies to zero-marker drafts."""
    manuscript = tmp_path / "cited.md"
    manuscript.write_text("# Draft\n\nThis cites [@Smith2023] without a bib.\n")
    with pytest.raises(verify_ops.VerificationError):
        verify_ops.run_verification(str(manuscript), bib_path=None, apply_fixes=False)


def test_pure_expertise_no_bib_allowed(tmp_path):
    """Pure-expertise content (zero [@Key] markers) runs without a bib.
    Phases B, D, E still fire; C, G, H are skipped."""
    manuscript = tmp_path / "explainer.md"
    manuscript.write_text("# Explainer\n\nThis has no citations at all.\n")
    report = verify_ops.run_verification(str(manuscript), bib_path=None, apply_fixes=False)
    assert report["pure_expertise"] is True
    assert report["blocked"] is False


def test_empty_bib_with_markers_refused(tmp_path):
    mp = tmp_path / "m.md"
    mp.write_text("Claim [@Key].")
    bp = tmp_path / "empty.bib"
    bp.write_text("")
    with pytest.raises(verify_ops.VerificationError):
        verify_ops.run_verification(str(mp), bib_path=str(bp), apply_fixes=False)


# ============================================================
# Tier 1 adversarial regression suite
# ============================================================


LONG_QUOTE = (
    "RNA-guided human genome engineering via Cas9 enables precise, "
    "efficient editing across a wide range of eukaryotic cell lines."
)  # >= 80 chars


def test_short_quote_flagged_major(tmp_path):
    """MIN_QUOTE_CHARS raised to 80: a 55-char quote must flag MAJOR."""
    mp, bp, _ = write_case(
        tmp_path,
        "short",
        "Claim [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Mali2013",
                    "quote": "RNA-guided human genome engineering via Cas9 short",
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert any(
        f["severity"] == "major" and "minimum" in f["finding"]
        for f in r["findings"]
    ), "quote < 80 chars must surface as MAJOR"


def test_smart_quote_bypass_blocked(tmp_path):
    """Smart quotes / em-dashes / NBSP in the sidecar quote must NOT pass
    as verbatim when the source uses straight ASCII equivalents — the
    quote was never actually in the source."""
    source = "Cas9 is a programmable nuclease that enables precise editing of the genome."
    fabricated = (
        "Cas9 is a \u201cprogrammable nuclease\u201d \u2014 it enables precise editing of the genome "
        "and rewrites the future of medicine forever."
    )
    mp, bp, sp = write_case(
        tmp_path,
        "smart",
        "Statement [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Mali2013",
                    "quote": fabricated,
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                }
            ],
        },
        source=source,
    )
    r = verify_ops.run_verification(mp, bib_path=bp, source_path=sp, apply_fixes=False)
    assert r["blocked"] is True
    assert any(
        "NOT found in the" in f["finding"] for f in r["findings"]
    ), "smart-quote + em-dash text not in source must block"


def test_straight_to_smart_source_still_matches(tmp_path):
    """Inverse case: source uses smart quotes, sidecar uses straight.
    NFKC fold should let genuine verbatim matches through."""
    source = (
        "RNA-guided human genome engineering via Cas9 enables precise, "
        "efficient editing across a wide range of eukaryotic cell lines."
    )
    straight_quote = LONG_QUOTE
    mp, bp, sp = write_case(
        tmp_path,
        "fold",
        "Statement [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Mali2013",
                    "quote": straight_quote,
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                }
            ],
        },
        source=source,
    )
    r = verify_ops.run_verification(mp, bib_path=bp, source_path=sp, apply_fixes=False)
    assert not any(
        "NOT found in the" in f["finding"] for f in r["findings"]
    ), "genuine verbatim (straight vs smart) must pass the substring check"


def test_title_near_match_bypass_blocked(monkeypatch, tmp_path):
    """Near-match title laundering: 'The Role of A in B' vs
    'The Role of A in B and C'. Old 0.75 alphanumeric SequenceMatcher
    let these slip; 0.95 + token-set Jaccard must catch it."""
    near_match_record = {
        "doi": "10.1234/near",
        "title": "The Role of A in B and C and D and E",
        "authors": ["X"],
        "published": {},
        "journal": "X",
        "is_retracted": False,
        "retraction_info": None,
        "type": "journal-article",
        "source": "crossref",
        "dual_id_conflict": None,
    }
    # check_bib_integrity dispatches via verify_citation; patch both the
    # source module and the verify_ops binding so the override survives
    # the conftest stub.
    from repro import citation_verify
    monkeypatch.setattr(
        citation_verify, "verify_citation", lambda entry: near_match_record
    )
    monkeypatch.setattr(
        verify_ops, "verify_citation", lambda entry: near_match_record
    )
    mp, bp, _ = write_case(
        tmp_path,
        "near",
        "Claim [@Near2024].",
        make_bib("Near2024", "The Role of A in B", "10.1234/near"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Near2024",
                    "quote": LONG_QUOTE,
                    "source_anchor": "10.1234/near",
                    "source_type": "doi",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert r["blocked"] is True
    assert any("Title mismatch" in f["finding"] for f in r["findings"])


def test_title_similarity_threshold_constant():
    """Lock in the Tier 5 threshold (raised 0.90 -> 0.95 in Phase 8) so a
    future loosening triggers this test rather than silently reopening
    the bypass."""
    assert verify_ops.TITLE_MATCH_THRESHOLD == 0.95
    assert verify_ops.MIN_QUOTE_CHARS == 80


def test_title_similarity_identical():
    """Exact match must still score 1.0 — regression on over-tightening."""
    ratio = verify_ops.title_similarity(
        "RNA-guided human genome engineering via Cas9",
        "RNA-guided human genome engineering via Cas9",
    )
    assert ratio == 1.0


def test_title_similarity_subtitle_tail_below_threshold():
    """A clearly different tail should land below 0.90."""
    ratio = verify_ops.title_similarity(
        "The Role of A in B",
        "The Role of A in B and C and D and E",
    )
    assert ratio < 0.90


# ============================================================
# Tier 1 PreToolUse gate simulation tests
# ============================================================


def test_verify_gate_simulate_write(tmp_path, monkeypatch):
    """PreToolUse Write simulation must run verify_ops on the proposed
    content without touching any real file."""
    import importlib.util
    gate_path = ROOT / ".claude/hooks_info/verify_gate.py"
    spec = importlib.util.spec_from_file_location("verify_gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    target = tmp_path / "fresh.md"
    # Never written on disk — simulation builds from tool_input.content
    content = gate._simulate_content(
        "Write", {"content": "hello world"}, target
    )
    assert content == "hello world"
    assert not target.exists()


def test_verify_gate_simulate_edit_applies_replacement(tmp_path):
    import importlib.util
    gate_path = ROOT / ".claude/hooks_info/verify_gate.py"
    spec = importlib.util.spec_from_file_location("verify_gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    target = tmp_path / "orig.md"
    target.write_text("Alpha Beta Gamma")
    result = gate._simulate_content(
        "Edit",
        {"old_string": "Beta", "new_string": "Delta"},
        target,
    )
    assert result == "Alpha Delta Gamma"
    # Source file is untouched
    assert target.read_text() == "Alpha Beta Gamma"


def test_verify_gate_simulate_edit_missing_string_refuses(tmp_path):
    import importlib.util
    gate_path = ROOT / ".claude/hooks_info/verify_gate.py"
    spec = importlib.util.spec_from_file_location("verify_gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    target = tmp_path / "orig.md"
    target.write_text("Alpha Beta Gamma")
    with pytest.raises(gate.SimulationError):
        gate._simulate_content(
            "Edit",
            {"old_string": "NotThere", "new_string": "X"},
            target,
        )


def test_verify_gate_simulate_multiedit_sequence(tmp_path):
    import importlib.util
    gate_path = ROOT / ".claude/hooks_info/verify_gate.py"
    spec = importlib.util.spec_from_file_location("verify_gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    target = tmp_path / "orig.md"
    target.write_text("one two three")
    result = gate._simulate_content(
        "MultiEdit",
        {
            "edits": [
                {"old_string": "one", "new_string": "ONE"},
                {"old_string": "three", "new_string": "THREE"},
            ]
        },
        target,
    )
    assert result == "ONE two THREE"
    assert target.read_text() == "one two three"


# ============================================================
# Tier 3 provenance + gray-lit tests
# ============================================================


def test_abstract_sourced_quote_flagged_major(tmp_path):
    """T3.2: source_confidence='abstract' must surface as MAJOR."""
    mp, bp, _ = write_case(
        tmp_path,
        "abs",
        "Finding [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Mali2013",
                    "quote": LONG_QUOTE,
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                    "source_confidence": "abstract",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert any(
        f["severity"] == "major" and "abstract-sourced" in f["finding"]
        for f in r["findings"]
    )


def test_title_tier_quote_blocked_critical(tmp_path):
    """T3.1: the legacy 'title' provenance tier is CRITICAL — blocks."""
    mp, bp, _ = write_case(
        tmp_path,
        "legacy-title",
        "Finding [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Mali2013",
                    "quote": LONG_QUOTE,
                    "source_anchor": "10.1038/nature12373",
                    "source_type": "doi",
                    "source_confidence": "title",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert r["blocked"] is True
    assert any("title" in f["finding"] and f["severity"] == "critical" for f in r["findings"])


def test_full_text_confidence_passes(tmp_path):
    """Full-text confidence is the only provenance tier that passes
    cleanly through the sidecar check."""
    mp, bp, _ = write_case(
        tmp_path,
        "full-text",
        "Finding [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [
                {
                    "key": "Mali2013",
                    "quote": LONG_QUOTE,
                    "source_anchor": "https://citations.gxl.ai/papers/PMC123#L45",
                    "source_type": "paperclip",
                    "source_confidence": "full-text",
                }
            ],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    assert not any(
        "abstract-sourced" in f["finding"] or "legacy 'title'" in f["finding"]
        for f in r["findings"]
    )


def _arxiv_bib(key: str, title: str, eprint: str = "2404.00123") -> str:
    return (
        f"@article{{{key},\n"
        f"  title = {{{title}}},\n"
        f"  author = {{A, X}},\n"
        f"  year = {{2024}},\n"
        f"  eprint = {{{eprint}}},\n"
        f"  archivePrefix = {{arXiv}}\n"
        "}\n"
    )


def test_arxiv_preprint_flagged_major(tmp_path):
    """T3.4: arXiv preprints are flagged MAJOR by default."""
    mp = tmp_path / "px.md"
    bp = tmp_path / "px.bib"
    mp.write_text("Claim [@Pre2024].")
    bp.write_text(_arxiv_bib("Pre2024", "A preprint about some finding"))
    (tmp_path / "px.md.citations.json").write_text(
        json.dumps({
            "version": 1,
            "claims": [{
                "key": "Pre2024",
                "quote": LONG_QUOTE,
                "source_anchor": "arXiv:2404.00123",
                "source_type": "url",
                "source_confidence": "full-text",
            }],
        })
    )
    r = verify_ops.run_verification(str(mp), bib_path=str(bp), apply_fixes=False)
    assert any(
        f["severity"] == "major" and "preprint" in f["finding"].lower()
        for f in r["findings"]
    )


def test_arxiv_preprint_gray_lit_approved_passes(tmp_path):
    """T3.4: `gray_lit = {approved}` opt-in lets a preprint through."""
    mp = tmp_path / "pa.md"
    bp = tmp_path / "pa.bib"
    mp.write_text("Claim [@PreOk2024].")
    bp.write_text(
        "@article{PreOk2024,\n"
        "  title = {A preprint},\n"
        "  author = {A, X},\n"
        "  year = {2024},\n"
        "  eprint = {2404.00456},\n"
        "  archivePrefix = {arXiv},\n"
        "  gray_lit = {approved}\n"
        "}\n"
    )
    (tmp_path / "pa.md.citations.json").write_text(
        json.dumps({
            "version": 1,
            "claims": [{
                "key": "PreOk2024",
                "quote": LONG_QUOTE,
                "source_anchor": "arXiv:2404.00456",
                "source_type": "url",
                "source_confidence": "full-text",
            }],
        })
    )
    r = verify_ops.run_verification(str(mp), bib_path=str(bp), apply_fixes=False)
    assert not any(
        "preprint" in f["finding"].lower() and f["severity"] == "major"
        for f in r["findings"]
    )


def test_unpublished_entry_type_flagged_major(tmp_path):
    """T3.4: @unpublished entries are gray-lit regardless of DOI."""
    mp = tmp_path / "un.md"
    bp = tmp_path / "un.bib"
    mp.write_text("Claim [@Unpub2024].")
    bp.write_text(
        "@unpublished{Unpub2024,\n"
        "  title = {An unpublished note},\n"
        "  author = {X},\n"
        "  year = {2024}\n"
        "}\n"
    )
    (tmp_path / "un.md.citations.json").write_text(
        json.dumps({
            "version": 1,
            "claims": [{
                "key": "Unpub2024",
                "quote": LONG_QUOTE,
                "source_anchor": "local",
                "source_type": "url",
                "source_confidence": "full-text",
            }],
        })
    )
    r = verify_ops.run_verification(str(mp), bib_path=str(bp), apply_fixes=False)
    assert any(
        f["severity"] == "major" and "preprint or gray-literature" in f["finding"]
        for f in r["findings"]
    )


def test_crossref_connection_error_fails_closed(monkeypatch, tmp_path):
    """Phase 8: ConnectionError must be CRITICAL (network fail-closed),
    not MAJOR — a flaky lookup can no longer pass silently."""
    def _boom(*args, **kwargs):
        raise ConnectionError("simulated network failure")
    # check_bib_integrity dispatches via verify_citation; patch both the
    # source module and the verify_ops binding so the override survives
    # the conftest stub.
    from repro import citation_verify
    monkeypatch.setattr(citation_verify, "verify_citation", _boom)
    monkeypatch.setattr(verify_ops, "verify_citation", _boom)

    mp, bp, _ = write_case(
        tmp_path,
        "offline",
        "Claim [@Mali2013].",
        make_bib("Mali2013", "RNA-guided human genome engineering via Cas9", "10.1038/nature12373"),
        sidecar={
            "version": 1,
            "claims": [{
                "key": "Mali2013",
                "quote": LONG_QUOTE,
                "source_anchor": "10.1038/nature12373",
                "source_type": "doi",
                "source_confidence": "full-text",
            }],
        },
    )
    r = verify_ops.run_verification(mp, bib_path=bp, apply_fixes=False)
    conn_findings = [
        f for f in r["findings"] if "Could not reach crossref" in f["finding"]
    ]
    assert conn_findings
    assert all(f["severity"] == "critical" for f in conn_findings)
