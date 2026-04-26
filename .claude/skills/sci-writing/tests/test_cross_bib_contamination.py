"""Tier G — cross-bib contamination tests.

Covers:
  G1 — check_cross_bib_contamination: MAJOR when a sidecar quote for [@KeyA]
       also appears verbatim in the upstream seed for some other [@KeyB]
  G2 — check_quote_attributable_to_one_source: returns False when quote
       appears in a seed belonging to a different key

All tests are offline (no network calls).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from verify_ops import (
    check_cross_bib_contamination,
    check_quote_attributable_to_one_source,
    _normalize_for_quote_match,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quotes_json(entries: list[dict], tmp_path: Path) -> Path:
    data = {"quotes": entries}
    p = tmp_path / "test.quotes.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _make_sidecar(claims: list[dict], tmp_path: Path, name: str = "draft.md") -> Path:
    ms = tmp_path / name
    ms.write_text("placeholder", encoding="utf-8")
    sidecar = tmp_path / f"{name}.citations.json"
    sidecar.write_text(json.dumps({"version": 1, "claims": claims}), encoding="utf-8")
    return ms


def _seeds_from_entries(entries: list[dict]) -> dict[str, list[str]]:
    """Build the all_seeds dict the same way _collect_upstream_seeds does."""
    result: dict[str, list[str]] = {}
    for e in entries:
        key = (e.get("key") or "").strip().lower()
        bucket = [
            _normalize_for_quote_match(c["text"])
            for c in (e.get("candidate_quotes") or [])
            if c.get("text", "").strip()
        ]
        if bucket:
            result[key] = bucket
    return result


# ---------------------------------------------------------------------------
# G2: check_quote_attributable_to_one_source
# ---------------------------------------------------------------------------

class TestCheckQuoteAttributableToOneSource:
    """Unit tests for the G2 helper."""

    def test_empty_quote_is_vacuously_attributable(self):
        seeds = {"keya": ["some text"], "keyb": ["other text"]}
        assert check_quote_attributable_to_one_source("", seeds, "keya") is True

    def test_quote_only_in_own_key(self):
        seeds = {
            "keya": [_normalize_for_quote_match("unique passage for A")],
            "keyb": [_normalize_for_quote_match("different passage for B")],
        }
        assert check_quote_attributable_to_one_source(
            _normalize_for_quote_match("unique passage for A"), seeds, "keya"
        ) is True

    def test_quote_in_another_key_returns_false(self):
        shared = _normalize_for_quote_match("shared passage in both papers")
        seeds = {
            "keya": [shared],
            "keyb": [shared],
        }
        assert check_quote_attributable_to_one_source(shared, seeds, "keya") is False

    def test_quote_not_in_own_key_but_in_another(self):
        """Quote doesn't appear in own seed but appears in other — still False."""
        seeds = {
            "keya": [_normalize_for_quote_match("something else entirely")],
            "keyb": [_normalize_for_quote_match("shared passage in both papers")],
        }
        assert check_quote_attributable_to_one_source(
            _normalize_for_quote_match("shared passage in both papers"), seeds, "keya"
        ) is False

    def test_no_other_keys_always_true(self):
        seeds = {"keya": [_normalize_for_quote_match("only paper")]}
        assert check_quote_attributable_to_one_source(
            _normalize_for_quote_match("only paper"), seeds, "keya"
        ) is True

    def test_substring_match_triggers(self):
        """Sub-span of a longer seed in another key counts as contamination."""
        short = _normalize_for_quote_match("CRISPR enables editing")
        long_seed = _normalize_for_quote_match(
            "The study showed that CRISPR enables editing of the genome precisely."
        )
        seeds = {
            "keya": [_normalize_for_quote_match("unique to A")],
            "keyb": [long_seed],
        }
        assert check_quote_attributable_to_one_source(short, seeds, "keya") is False

    def test_empty_seeds_dict_is_attributable(self):
        assert check_quote_attributable_to_one_source("some text", {}, "keya") is True

    def test_own_key_not_in_seeds(self):
        """own_key absent from seeds — still checks other keys."""
        seeds = {"keyb": [_normalize_for_quote_match("shared text")]}
        assert check_quote_attributable_to_one_source(
            _normalize_for_quote_match("shared text"), seeds, "keya"
        ) is False


# ---------------------------------------------------------------------------
# G1: check_cross_bib_contamination
# ---------------------------------------------------------------------------

class TestCheckCrossBibContamination:

    def test_no_contamination_clean_passage(self, tmp_path):
        """Unique quotes per key — no findings."""
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": "passage unique to paper A"}]},
            {"key": "keyb", "candidate_quotes": [{"text": "passage unique to paper B"}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar(
            [
                {"key": "keya", "quote": "passage unique to paper A"},
                {"key": "keyb", "quote": "passage unique to paper B"},
            ],
            tmp_path,
        )
        result = check_cross_bib_contamination(str(ms), {"keya", "keyb"}, qp)
        assert result == []

    def test_shared_passage_fires_major(self, tmp_path):
        """Same passage in both seeds — MAJOR for the attributed key."""
        shared = "CRISPR enables precise genome editing"
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": shared}]},
            {"key": "keyb", "candidate_quotes": [{"text": shared}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar(
            [{"key": "keya", "quote": shared}],
            tmp_path,
        )
        result = check_cross_bib_contamination(str(ms), {"keya"}, qp)
        assert len(result) == 1
        f = result[0]
        assert f["severity"] == "major"
        assert "keya" in f["finding"]
        assert "keyb" in f["finding"]
        assert "Cross-Bib Contamination" in f["criterion"]

    def test_both_keys_contaminated_both_flagged(self, tmp_path):
        """When both keys use the shared quote, both should fire."""
        shared = "the algorithm converges in O(n log n) time"
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": shared}]},
            {"key": "keyb", "candidate_quotes": [{"text": shared}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar(
            [
                {"key": "keya", "quote": shared},
                {"key": "keyb", "quote": shared},
            ],
            tmp_path,
        )
        result = check_cross_bib_contamination(str(ms), {"keya", "keyb"}, qp)
        keys_flagged = {f["finding"].split("'[@")[1].split("]'")[0] for f in result}
        assert keys_flagged == {"keya", "keyb"}

    def test_quote_not_in_own_seed_skipped(self, tmp_path):
        """If the quote is absent from own seed, upstream provenance already fires.
        cross-bib check should NOT add a second finding for the same quote."""
        shared = "shared passage"
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": "something different"}]},
            {"key": "keyb", "candidate_quotes": [{"text": shared}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        # keya's sidecar quote is NOT in keya's own seed (provenance gap),
        # but IS in keyb's seed.
        ms = _make_sidecar(
            [{"key": "keya", "quote": shared}],
            tmp_path,
        )
        result = check_cross_bib_contamination(str(ms), {"keya"}, qp)
        # Should be empty — provenance check handles this; contamination check skips.
        assert result == []

    def test_quotes_path_none_returns_empty(self, tmp_path):
        ms = _make_sidecar([{"key": "keya", "quote": "text"}], tmp_path)
        result = check_cross_bib_contamination(str(ms), {"keya"}, None)
        assert result == []

    def test_quotes_path_missing_file_returns_empty(self, tmp_path):
        ms = _make_sidecar([{"key": "keya", "quote": "text"}], tmp_path)
        result = check_cross_bib_contamination(
            str(ms), {"keya"}, tmp_path / "nonexistent.json"
        )
        assert result == []

    def test_empty_used_keys_returns_empty(self, tmp_path):
        entries = [{"key": "keya", "candidate_quotes": [{"text": "anything"}]}]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar([], tmp_path)
        result = check_cross_bib_contamination(str(ms), set(), qp)
        assert result == []

    def test_no_sidecar_file_returns_empty(self, tmp_path):
        entries = [{"key": "keya", "candidate_quotes": [{"text": "anything"}]}]
        qp = _make_quotes_json(entries, tmp_path)
        ms = tmp_path / "nodraft.md"
        ms.write_text("placeholder", encoding="utf-8")
        # No .citations.json written alongside — sidecar is absent.
        result = check_cross_bib_contamination(str(ms), {"keya"}, qp)
        assert result == []

    def test_key_with_no_sidecar_claim_skipped(self, tmp_path):
        """Used key has no matching sidecar claim — gate already flagged it; skip."""
        shared = "shared text"
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": shared}]},
            {"key": "keyb", "candidate_quotes": [{"text": shared}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        # Sidecar has keyb but not keya.
        ms = _make_sidecar([{"key": "keyb", "quote": shared}], tmp_path)
        result = check_cross_bib_contamination(str(ms), {"keya", "keyb"}, qp)
        # Only keyb fires; keya has no sidecar entry to check.
        keys_flagged = {f["finding"].split("'[@")[1].split("]'")[0] for f in result}
        assert "keya" not in keys_flagged
        assert "keyb" in keys_flagged

    def test_empty_quote_in_sidecar_skipped(self, tmp_path):
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": "something"}]},
            {"key": "keyb", "candidate_quotes": [{"text": "something"}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar([{"key": "keya", "quote": ""}], tmp_path)
        result = check_cross_bib_contamination(str(ms), {"keya"}, qp)
        assert result == []

    def test_three_keys_one_shared_among_two(self, tmp_path):
        """keya and keyb share a passage; keyc is clean. Only keya fires."""
        shared = "shared passage between a and b"
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": shared}]},
            {"key": "keyb", "candidate_quotes": [{"text": shared}]},
            {"key": "keyc", "candidate_quotes": [{"text": "unique to c"}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar(
            [
                {"key": "keya", "quote": shared},
                {"key": "keyc", "quote": "unique to c"},
            ],
            tmp_path,
        )
        result = check_cross_bib_contamination(str(ms), {"keya", "keyc"}, qp)
        assert len(result) == 1
        assert "keya" in result[0]["finding"]
        assert "keyc" not in result[0]["finding"]

    def test_finding_mentions_all_matching_others(self, tmp_path):
        """When a quote appears in three other keys, all three are named."""
        shared = "ubiquitous phrase"
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": shared}]},
            {"key": "keyb", "candidate_quotes": [{"text": shared}]},
            {"key": "keyc", "candidate_quotes": [{"text": shared}]},
            {"key": "keyd", "candidate_quotes": [{"text": shared}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar([{"key": "keya", "quote": shared}], tmp_path)
        result = check_cross_bib_contamination(str(ms), {"keya"}, qp)
        assert len(result) == 1
        finding_text = result[0]["finding"]
        assert "keyb" in finding_text
        assert "keyc" in finding_text
        assert "keyd" in finding_text

    def test_suggestion_mentions_source_anchor(self, tmp_path):
        shared = "ambiguous shared claim"
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": shared}]},
            {"key": "keyb", "candidate_quotes": [{"text": shared}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar([{"key": "keya", "quote": shared}], tmp_path)
        result = check_cross_bib_contamination(str(ms), {"keya"}, qp)
        assert "source_anchor" in result[0]["suggestion"]

    def test_case_insensitive_key_matching(self, tmp_path):
        """Keys in used_keys may be uppercase; sidecar keys lowercase."""
        shared = "some important result"
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": shared}]},
            {"key": "keyb", "candidate_quotes": [{"text": shared}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar([{"key": "keya", "quote": shared}], tmp_path)
        # Pass uppercase key in used_keys
        result = check_cross_bib_contamination(str(ms), {"KeyA"}, qp)
        assert len(result) == 1

    def test_substring_quote_fires(self, tmp_path):
        """A shorter quote that is a sub-span of a shared seed triggers contamination."""
        long_seed = "The framework achieves state-of-the-art results on all benchmarks tested."
        sub_quote = "state-of-the-art results on all benchmarks"
        entries = [
            {"key": "keya", "candidate_quotes": [{"text": long_seed}]},
            {"key": "keyb", "candidate_quotes": [{"text": long_seed}]},
        ]
        qp = _make_quotes_json(entries, tmp_path)
        ms = _make_sidecar([{"key": "keya", "quote": sub_quote}], tmp_path)
        result = check_cross_bib_contamination(str(ms), {"keya"}, qp)
        assert len(result) == 1
        assert result[0]["severity"] == "major"
