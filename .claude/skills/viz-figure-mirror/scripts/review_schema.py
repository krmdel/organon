"""Strict reviewer-output validation + select-best fallback for viz-figure-mirror.

The Reviewer (a fresh-context vision audit) must emit exactly one JSON object and
nothing else, because the loop parses it with `json.loads`. This module is the
guard rail: it parses that string, enforces the schema, and raises a clear,
specific error the moment the JSON is malformed or a required field is missing or
out of range. If validation passes, the caller can trust every field.

It also implements `select_best`, the fallback the orchestrator uses when the loop
exhausts its iteration budget without ever earning a `ship` verdict: among the
iterations that cleared the floor and were judged `close`, pick the one that
drifted least from the reference.

Clean-room. The schema shape (anchor / quality_floor / fidelity / focus_themes) and
the select-best policy are reimplemented from the FigMirror technique description;
no source was copied.
"""

from __future__ import annotations

import json
from typing import Any


# Allowed fidelity verdicts. The loop's decision rule keys off these exact strings.
_VALID_VERDICTS = {"ship", "close", "off"}


class ReviewSchemaError(ValueError):
    """Raised when reviewer JSON is unparseable or violates the schema."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewSchemaError(message)


def validate_review(raw: str | dict) -> dict:
    """Parse + validate one reviewer audit.

    Accepts either a JSON string (the normal case — the Reviewer's stdout) or an
    already-decoded dict (convenience for tests / programmatic callers). Returns the
    validated dict. Raises ``ReviewSchemaError`` with a specific message on any
    problem.

    Enforced schema::

        {
          "iter": int,
          "anchor": {
            "what_is_right": [str, ...]   # 3-7 items
          },
          "quality_floor": {
            "passed": bool,
            "violation_kinds": [str, ...]  # may be empty
          },
          "fidelity": {
            "verdict": "ship" | "close" | "off"
          },
          "focus_themes": [str, ...]       # <= 5 items
        }

    Extra keys (e.g. anchor.measurements, fidelity.paragraph,
    quality_floor.summary) are allowed and ignored — they carry useful context but
    are not load-bearing for the loop.
    """
    if isinstance(raw, dict):
        data: Any = raw
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ReviewSchemaError(
                f"reviewer output is not valid JSON: {exc.msg} "
                f"(line {exc.lineno}, col {exc.colno})"
            ) from exc

    _require(isinstance(data, dict), "reviewer output must be a JSON object")

    # --- iter ------------------------------------------------------------- #
    _require("iter" in data, "missing required field: iter")
    _require(
        isinstance(data["iter"], int) and not isinstance(data["iter"], bool),
        "field 'iter' must be an integer",
    )

    # --- anchor.what_is_right (3-7 items) --------------------------------- #
    _require("anchor" in data, "missing required field: anchor")
    anchor = data["anchor"]
    _require(isinstance(anchor, dict), "field 'anchor' must be an object")
    _require(
        "what_is_right" in anchor,
        "missing required field: anchor.what_is_right",
    )
    wir = anchor["what_is_right"]
    _require(
        isinstance(wir, list) and all(isinstance(x, str) for x in wir),
        "anchor.what_is_right must be a list of strings",
    )
    _require(
        3 <= len(wir) <= 7,
        f"anchor.what_is_right must have 3-7 items, got {len(wir)}",
    )

    # --- quality_floor ---------------------------------------------------- #
    _require("quality_floor" in data, "missing required field: quality_floor")
    qf = data["quality_floor"]
    _require(isinstance(qf, dict), "field 'quality_floor' must be an object")
    _require(
        "passed" in qf and isinstance(qf["passed"], bool),
        "quality_floor.passed must be a boolean",
    )
    _require(
        "violation_kinds" in qf,
        "missing required field: quality_floor.violation_kinds",
    )
    vk = qf["violation_kinds"]
    _require(
        isinstance(vk, list) and all(isinstance(x, str) for x in vk),
        "quality_floor.violation_kinds must be a list of strings",
    )

    # --- fidelity.verdict ------------------------------------------------- #
    _require("fidelity" in data, "missing required field: fidelity")
    fid = data["fidelity"]
    _require(isinstance(fid, dict), "field 'fidelity' must be an object")
    _require("verdict" in fid, "missing required field: fidelity.verdict")
    _require(
        fid["verdict"] in _VALID_VERDICTS,
        f"fidelity.verdict must be one of {sorted(_VALID_VERDICTS)}, "
        f"got {fid['verdict']!r}",
    )

    # --- focus_themes (<= 5) ---------------------------------------------- #
    _require("focus_themes" in data, "missing required field: focus_themes")
    ft = data["focus_themes"]
    _require(
        isinstance(ft, list) and all(isinstance(x, str) for x in ft),
        "focus_themes must be a list of strings",
    )
    _require(len(ft) <= 5, f"focus_themes must have <= 5 items, got {len(ft)}")

    return data


def _drift(iteration: dict, index: int) -> float:
    """Compute an iteration's drift-from-reference score.

    When the audit carries explicit drift signals we sum their magnitudes::

        drift = |aspect_drift| + |spine_count_drift|

    These may live either at the top level of the iteration dict or nested under
    ``anchor.measurements`` (where the Reviewer records PIL measurements). When no
    drift signal is present at all, fall back to the iteration index so that, all
    else equal, an earlier (less-drifted-by-construction) iteration is preferred —
    matching the policy that the most recent iteration is NOT automatically best.
    """
    measurements = {}
    anchor = iteration.get("anchor")
    if isinstance(anchor, dict) and isinstance(anchor.get("measurements"), dict):
        measurements = anchor["measurements"]

    aspect = iteration.get("aspect_drift", measurements.get("aspect_drift"))
    spine = iteration.get("spine_count_drift", measurements.get("spine_count_drift"))

    if aspect is None and spine is None:
        return float(index)
    return abs(aspect or 0.0) + abs(spine or 0.0)


def select_best(iterations: list[dict]) -> int:
    """Pick the index of the best iteration when no `ship` ever fired.

    Policy:
      1. Candidate set = iterations whose floor passed AND verdict == "close".
      2. Among candidates, pick the lowest drift (see ``_drift``); ties break
         toward the earliest index.
      3. If no `close` candidate exists, fall back to any floor-passing iteration
         with the lowest drift.
      4. If nothing passed the floor, fall back to the lowest-drift iteration
         overall (least-bad).

    Returns the integer index into ``iterations``. Raises ValueError on empty input.
    """
    if not iterations:
        raise ValueError("select_best requires at least one iteration")

    def floor_passed(it: dict) -> bool:
        qf = it.get("quality_floor", {})
        return bool(isinstance(qf, dict) and qf.get("passed"))

    def verdict(it: dict) -> str | None:
        fid = it.get("fidelity", {})
        return fid.get("verdict") if isinstance(fid, dict) else None

    indexed = list(enumerate(iterations))

    close_passing = [
        (i, it) for i, it in indexed if floor_passed(it) and verdict(it) == "close"
    ]
    if close_passing:
        return min(close_passing, key=lambda pair: (_drift(pair[1], pair[0]), pair[0]))[0]

    any_passing = [(i, it) for i, it in indexed if floor_passed(it)]
    if any_passing:
        return min(any_passing, key=lambda pair: (_drift(pair[1], pair[0]), pair[0]))[0]

    return min(indexed, key=lambda pair: (_drift(pair[1], pair[0]), pair[0]))[0]


__all__ = [
    "ReviewSchemaError",
    "validate_review",
    "select_best",
]
