"""Real pytest coverage for the reviewer-schema validator + select-best fallback.

No network, no vision model — pure JSON / list logic.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from review_schema import (  # noqa: E402
    ReviewSchemaError,
    select_best,
    validate_review,
)


def _valid_audit(**overrides):
    base = {
        "iter": 2,
        "anchor": {
            "what_is_right": [
                "[L1] Aspect ratio within +/-10% (1.93 vs 1.95).",
                "[L1] Series palette matches the reference family.",
                "[L1+L2] Spines: left+bottom only.",
            ],
            "measurements": {"ref_aspect": 1.95, "draft_aspect": 1.93},
        },
        "quality_floor": {"passed": True, "violation_kinds": [], "summary": None},
        "fidelity": {"verdict": "close", "paragraph": "right family, one gap."},
        "focus_themes": ["[L2] Lighten the spine colour."],
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Valid input
# --------------------------------------------------------------------------- #

def test_valid_json_string_validates():
    out = validate_review(json.dumps(_valid_audit()))
    assert out["fidelity"]["verdict"] == "close"
    assert out["iter"] == 2


def test_valid_dict_validates():
    out = validate_review(_valid_audit())
    assert out["quality_floor"]["passed"] is True


def test_ship_verdict_with_empty_focus_themes_is_valid():
    audit = _valid_audit(
        fidelity={"verdict": "ship", "paragraph": "ships."},
        focus_themes=[],
    )
    out = validate_review(audit)
    assert out["focus_themes"] == []


# --------------------------------------------------------------------------- #
# Malformed / missing-field input raises
# --------------------------------------------------------------------------- #

def test_malformed_json_raises():
    with pytest.raises(ReviewSchemaError, match="not valid JSON"):
        validate_review("{ this is not json ")


def test_non_object_json_raises():
    with pytest.raises(ReviewSchemaError, match="must be a JSON object"):
        validate_review("[1, 2, 3]")


def test_missing_fidelity_raises():
    audit = _valid_audit()
    del audit["fidelity"]
    with pytest.raises(ReviewSchemaError, match="fidelity"):
        validate_review(audit)


def test_bad_verdict_raises():
    audit = _valid_audit(fidelity={"verdict": "maybe"})
    with pytest.raises(ReviewSchemaError, match="verdict"):
        validate_review(audit)


def test_too_few_anchor_items_raises():
    audit = _valid_audit()
    audit["anchor"]["what_is_right"] = ["[L1] only one item"]
    with pytest.raises(ReviewSchemaError, match="3-7 items"):
        validate_review(audit)


def test_too_many_anchor_items_raises():
    audit = _valid_audit()
    audit["anchor"]["what_is_right"] = [f"[L1] item {i}" for i in range(8)]
    with pytest.raises(ReviewSchemaError, match="3-7 items"):
        validate_review(audit)


def test_too_many_focus_themes_raises():
    audit = _valid_audit(focus_themes=[f"theme {i}" for i in range(6)])
    with pytest.raises(ReviewSchemaError, match="<= 5"):
        validate_review(audit)


def test_missing_quality_floor_passed_raises():
    audit = _valid_audit()
    del audit["quality_floor"]["passed"]
    with pytest.raises(ReviewSchemaError, match="quality_floor.passed"):
        validate_review(audit)


def test_iter_must_be_int_not_bool():
    audit = _valid_audit(iter=True)
    with pytest.raises(ReviewSchemaError, match="iter"):
        validate_review(audit)


# --------------------------------------------------------------------------- #
# select_best
# --------------------------------------------------------------------------- #

def _iter(passed, verdict, aspect_drift=None, spine_count_drift=None):
    it = {
        "quality_floor": {"passed": passed, "violation_kinds": []},
        "fidelity": {"verdict": verdict},
        "anchor": {"what_is_right": ["a", "b", "c"], "measurements": {}},
    }
    if aspect_drift is not None:
        it["anchor"]["measurements"]["aspect_drift"] = aspect_drift
    if spine_count_drift is not None:
        it["anchor"]["measurements"]["spine_count_drift"] = spine_count_drift
    return it


def test_select_best_picks_lowest_drift_close_iter():
    iters = [
        _iter(True, "close", aspect_drift=0.07, spine_count_drift=0),   # idx 0
        _iter(True, "off", aspect_drift=0.01),                          # idx 1 (off)
        _iter(True, "close", aspect_drift=0.21, spine_count_drift=2),   # idx 2
        _iter(False, "close", aspect_drift=0.0),                        # idx 3 (floor fail)
    ]
    # Among floor-passing close iters (0 and 2), idx 0 has lower drift (0.07 < 0.23).
    assert select_best(iters) == 0


def test_select_best_ignores_more_recent_when_more_drifted():
    iters = [
        _iter(True, "close", aspect_drift=0.05),  # earlier, low drift
        _iter(True, "close", aspect_drift=0.30),  # most recent, high drift
    ]
    assert select_best(iters) == 0  # NOT the most recent


def test_select_best_falls_back_to_floor_passing_when_no_close():
    iters = [
        _iter(False, "off"),
        _iter(True, "off", aspect_drift=0.10),
        _iter(True, "off", aspect_drift=0.40),
    ]
    assert select_best(iters) == 1  # only floor-passing, lowest drift


def test_select_best_falls_back_to_least_bad_when_nothing_passes():
    iters = [
        _iter(False, "off", aspect_drift=0.50),
        _iter(False, "off", aspect_drift=0.10),
    ]
    assert select_best(iters) == 1


def test_select_best_index_tiebreak_when_no_drift_signal():
    # No drift signals at all -> drift falls back to index, earliest wins.
    iters = [_iter(True, "close"), _iter(True, "close"), _iter(True, "close")]
    assert select_best(iters) == 0


def test_select_best_empty_raises():
    with pytest.raises(ValueError):
        select_best([])
