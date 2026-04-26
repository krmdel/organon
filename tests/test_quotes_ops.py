"""Tests for the sci-literature-research quotes.json sidecar builder."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".claude/skills/sci-literature-research/scripts"))

import quotes_ops  # noqa: E402


def _bib(tmp_path, name="refs"):
    bp = tmp_path / f"{name}.bib"
    bp.write_text("@article{Stub, title={X}}")
    return str(bp)


def test_build_from_doi_abstract(tmp_path):
    bib = _bib(tmp_path)
    entries = [
        {
            "key": "Mali2013",
            "doi": "10.1038/nature12373",
            "title": "RNA-guided human genome engineering via Cas9",
            "abstract": (
                "RNA-guided Cas9 enables precise editing of the human genome. "
                "We demonstrate targeted cleavage at multiple loci with high efficiency. "
                "Off-target effects were measured and quantified."
            ),
        }
    ]
    path = quotes_ops.build_quotes_sidecar(entries, bib)
    data = json.loads(Path(path).read_text())

    assert data["version"] == 1
    assert data["source"] == "sci-literature-research cite mode"
    assert len(data["quotes"]) == 1
    q = data["quotes"][0]
    assert q["key"] == "Mali2013"
    assert q["doi"] == "10.1038/nature12373"
    assert len(q["candidate_quotes"]) >= 1
    first = q["candidate_quotes"][0]
    assert first["source_type"] == "doi"
    assert first["source_anchor"] == "10.1038/nature12373"
    assert first["confidence"] == "abstract"
    assert "Cas9" in first["text"]


def test_build_from_paperclip_lines(tmp_path):
    bib = _bib(tmp_path)
    entries = [
        {
            "key": "Chen2024",
            "doi": "10.1101/2024.01.01.000000",
            "doc_id": "PMC123456",
            "source": "paperclip",
            "content": {
                "lines": [
                    {"line": 45, "text": "We observed a significant reduction in tumor volume."},
                    {"line": 46, "text": "The effect persisted across all cohorts."},
                ]
            },
        }
    ]
    path = quotes_ops.build_quotes_sidecar(entries, bib)
    data = json.loads(Path(path).read_text())
    q = data["quotes"][0]
    cands = q["candidate_quotes"]
    assert cands[0]["source_type"] == "paperclip"
    assert cands[0]["source_anchor"] == "https://citations.gxl.ai/papers/PMC123456#L45"
    assert "tumor volume" in cands[0]["text"]
    assert cands[1]["source_anchor"] == "https://citations.gxl.ai/papers/PMC123456#L46"


def test_no_candidates_when_no_abstract(tmp_path):
    """Tier 3: title fallback is dead. An entry with only a title (no
    abstract, no Paperclip content) yields zero candidates and is
    dropped from the sidecar — never laundered as a 'supporting quote'."""
    bib = _bib(tmp_path)
    entries = [
        {
            "key": "NoAbs2020",
            "doi": "10.1000/no-abs",
            "title": "A paper with no abstract and no content body available",
        }
    ]
    path = quotes_ops.build_quotes_sidecar(entries, bib)
    data = json.loads(Path(path).read_text())
    assert data["quotes"] == []


def test_entries_without_keys_are_skipped(tmp_path):
    bib = _bib(tmp_path)
    entries = [{"doi": "10.1/x", "abstract": "text"}]
    path = quotes_ops.build_quotes_sidecar(entries, bib)
    data = json.loads(Path(path).read_text())
    assert data["quotes"] == []


def test_sidecar_path_matches_bib_stem(tmp_path):
    bib = _bib(tmp_path, name="project-refs")
    path = quotes_ops.build_quotes_sidecar([], bib)
    assert Path(path).name == "project-refs.quotes.json"
    assert Path(path).parent == Path(bib).parent


def test_requires_bib_extension(tmp_path):
    notbib = tmp_path / "refs.txt"
    notbib.write_text("")
    with pytest.raises(ValueError):
        quotes_ops.build_quotes_sidecar([], str(notbib))
