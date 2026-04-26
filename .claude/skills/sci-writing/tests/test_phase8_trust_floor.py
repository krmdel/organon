"""test_phase8_trust_floor.py — Phase 8 trust-floor regressions.

Phase 8 closed five concrete bypass vectors found by the 2026-04-26 deep audit:

  1. unverifiable={approved} reason+date hardening   → test_tier_a_hardening.py
  2. Network ConnectionError → CRITICAL fail-closed  → here
  3. verify_ops ImportError → fail-closed gates      → test_publish_gates.py
  4. <!-- no-cite --> scope tighten + density NOTE   → here + test_tier_a_hardening.py
  5. Scope-mismatch escalation patterns              → here

Each test asserts the new contract. If a future change reverts the Phase 8
hardening, these regressions fire so the trust floor is preserved.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = REPO_ROOT / ".claude" / "skills" / "sci-writing" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT))


# ===========================================================================
# Item 2 — Network ConnectionError → CRITICAL (was MAJOR)
# ===========================================================================


class TestNetworkFailClosed:
    """A flaky network used to silently pass (MAJOR + blocked-on-CRITICAL).
    Phase 8: ConnectionError surfaces CRITICAL so blocked=True."""

    def _entry(self, **overrides) -> dict:
        base = {
            "key": "testkey",
            "entry_type": "article",
            "title": "Some Real Sounding Title",
            "author": "Smith, J.",
            "year": "2024",
            "doi": "10.1234/example",
        }
        base.update(overrides)
        return base

    def test_connection_error_in_bib_lookup_is_critical(self, monkeypatch):
        from verify_ops import check_bib_integrity, _LIVE_METADATA_CACHE
        import verify_ops as vo

        _LIVE_METADATA_CACHE.clear()

        def boom(entry):
            raise ConnectionError("simulated DNS failure")

        monkeypatch.setattr(vo, "verify_citation", boom)
        entry = self._entry()
        findings = check_bib_integrity({"testkey"}, [entry])
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits, "Phase 8: network outage must surface CRITICAL"
        assert "network" in crits[0]["criterion"].lower()

    def test_connection_error_on_inline_doi_is_critical(self, monkeypatch):
        from verify_ops import check_inline_links

        def boom(doi):
            raise ConnectionError("simulated DNS failure")

        # Patch the local rebinding in check_inline_links.
        import repro.citation_verify as cv
        monkeypatch.setattr(cv, "verify_doi", boom)
        text = "[Some paper](https://doi.org/10.1234/example)"
        findings = check_inline_links(text, [])
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits
        assert "network" in crits[0]["criterion"].lower()


# ===========================================================================
# Item 4 — no-cite density NOTE for unanchored factual claims
# ===========================================================================


class TestNoCiteDensityNote:
    """Phase 8: even a valid <!-- no-cite --> emits an info-level NOTE
    when the body still contains unanchored factual-claim patterns."""

    def test_density_note_on_factual_claims_inside_no_cite(self):
        from verify_ops import check_inline_attributions
        text = (
            "<!-- no-cite: Personal essay on lab onboarding; no published "
            "claims, all examples first-person observations -->\n"
            "We measured a 37% reduction in the cohort. "
            "Researchers reported similar effects last year. "
            "The result was significant at p < 0.05."
        )
        findings = check_inline_attributions(text, set())
        info = [f for f in findings if f["severity"] == "info"]
        assert info, (
            "Phase 8: factual-claim density inside no-cite must surface "
            "an info-level NOTE"
        )
        assert "density" in info[0]["criterion"].lower()

    def test_no_density_note_when_body_clean(self):
        """If the body has zero unanchored factual-claim patterns, no NOTE."""
        from verify_ops import check_inline_attributions
        text = (
            "<!-- no-cite: Personal essay on lab onboarding; no published "
            "claims, all examples first-person observations -->\n"
            "I started in the new lab on Monday. The bench was empty."
        )
        findings = check_inline_attributions(text, set())
        info = [f for f in findings if f["severity"] == "info"]
        assert not info


# ===========================================================================
# Item 5 — Scope escalation between sidecar quote and claim sentence
# ===========================================================================


class TestScopeEscalation:
    """Phase 8: a sidecar quote scoped to mice / in vitro / pilot must NOT
    be cited from a manuscript sentence that generalises to patients /
    in vivo / definitive."""

    def _setup(self, tmp_path: Path, manuscript: str, sidecar_quote: str):
        md = tmp_path / "draft.md"
        sidecar = tmp_path / "draft.md.citations.json"
        quotes = tmp_path / "draft.quotes.json"
        md.write_text(manuscript, encoding="utf-8")
        sidecar.write_text(json.dumps({
            "claims": [{"key": "smith2024", "quote": sidecar_quote}]
        }), encoding="utf-8")
        quotes.write_text(json.dumps({
            "smith2024": {"candidates": [{"text": sidecar_quote}]}
        }), encoding="utf-8")
        return md, quotes

    def test_animal_to_human_escalation_flagged(self, tmp_path):
        from verify_ops import check_scope_escalation
        md, quotes = self._setup(
            tmp_path,
            manuscript="The drug halves tumour volume in patients [@smith2024].",
            sidecar_quote=(
                "We administered the compound to mice in a controlled "
                "preclinical study and observed a tumour volume reduction "
                "after 28 days of dosing."
            ),
        )
        findings = check_scope_escalation(
            md.read_text(), {"smith2024"}, quotes, str(md)
        )
        assert findings, "mice → patients must be flagged"
        assert "Scope Escalation" in findings[0]["criterion"]

    def test_in_vitro_to_in_vivo_escalation_flagged(self, tmp_path):
        from verify_ops import check_scope_escalation
        md, quotes = self._setup(
            tmp_path,
            manuscript="Compound X works in vivo at the same dose [@smith2024].",
            sidecar_quote=(
                "We performed our experiments entirely in vitro using "
                "primary fibroblast cell lines and observed a dose-response "
                "between 1 and 10 micromolar."
            ),
        )
        findings = check_scope_escalation(
            md.read_text(), {"smith2024"}, quotes, str(md)
        )
        assert findings
        assert "Scope Escalation" in findings[0]["criterion"]

    def test_pilot_to_definitive_escalation_flagged(self, tmp_path):
        from verify_ops import check_scope_escalation
        md, quotes = self._setup(
            tmp_path,
            manuscript="The intervention is proven to reduce mortality [@smith2024].",
            sidecar_quote=(
                "This pilot study with 12 patients suggests a possible "
                "trend toward reduced 30-day mortality, but the effect "
                "size was small and the confidence interval crossed unity."
            ),
        )
        findings = check_scope_escalation(
            md.read_text(), {"smith2024"}, quotes, str(md)
        )
        assert findings

    def test_qualifier_retained_does_not_fire(self, tmp_path):
        """When the writer keeps the narrow qualifier in the sentence,
        no scope escalation is reported."""
        from verify_ops import check_scope_escalation
        md, quotes = self._setup(
            tmp_path,
            manuscript=(
                "In mice, the drug halves tumour volume after 28 days "
                "[@smith2024]."
            ),
            sidecar_quote=(
                "We administered the compound to mice in a controlled "
                "preclinical study and observed a tumour volume reduction "
                "after 28 days of dosing."
            ),
        )
        findings = check_scope_escalation(
            md.read_text(), {"smith2024"}, quotes, str(md)
        )
        assert not findings

    def test_quote_already_generalised_does_not_fire(self, tmp_path):
        """If the SOURCE itself generalises ('in mice and in patients'),
        the writer is faithfully repeating, not escalating."""
        from verify_ops import check_scope_escalation
        md, quotes = self._setup(
            tmp_path,
            manuscript="The drug halves tumour volume in patients [@smith2024].",
            sidecar_quote=(
                "We tested the compound in mice and confirmed comparable "
                "responses in patients across two clinical centres, with "
                "tumour volume halving after 28 days of dosing."
            ),
        )
        findings = check_scope_escalation(
            md.read_text(), {"smith2024"}, quotes, str(md)
        )
        assert not findings


# ===========================================================================
# Item 1 — Phase 8 unverifiable contract (positive smoke test, full suite
# in test_tier_a_hardening.py)
# ===========================================================================


class TestUnverifiableStatusHelper:
    """The internal _unverifiable_status helper is the single source of truth
    for the Phase 8 contract — exercise its boundaries directly."""

    def _status(self, **fields):
        from verify_ops import _unverifiable_status
        return _unverifiable_status(fields)

    def test_none_when_field_absent(self):
        assert self._status() == ("none", "")

    def test_none_when_field_not_approved(self):
        assert self._status(unverifiable="pending")[0] == "none"

    def test_incomplete_on_bare_approval(self):
        status, problem = self._status(unverifiable="approved")
        assert status == "incomplete"
        assert "reason" in problem and "date" in problem

    def test_incomplete_on_short_reason(self):
        status, _ = self._status(
            unverifiable="approved",
            unverifiable_reason="too short",
            unverifiable_date="2026-04-26",
        )
        assert status == "incomplete"

    def test_incomplete_on_template_reason(self):
        status, _ = self._status(
            unverifiable="approved",
            unverifiable_reason="approved",
            unverifiable_date="2026-04-26",
        )
        assert status == "incomplete"

    def test_incomplete_on_bad_date_format(self):
        status, _ = self._status(
            unverifiable="approved",
            unverifiable_reason=(
                "Personal communication on 2025-11-11 with the original "
                "author; no preprint planned for 12 months."
            ),
            unverifiable_date="April 26 2026",
        )
        assert status == "incomplete"

    def test_approved_on_full_contract(self):
        status, problem = self._status(
            unverifiable="approved",
            unverifiable_reason=(
                "Personal communication with the original author; no "
                "preprint planned for the next 12 months."
            ),
            unverifiable_date="2026-04-26",
        )
        assert status == "approved"
        assert problem == ""
