"""Shared fixtures for end-to-end Organon tests.

Per context/memory/organon_upgrade_final_handoff.md §3.0.

Two markers:
  @pytest.mark.slow               — wall-clock > 5s (PT-SA convergence, full polish, etc.)
  @pytest.mark.needs_arena_data   — needs a specific projects/einstein-arena-*/
                                    directory; pytest.skip cleanly when absent.

All tests in this tree must be LOCAL-ONLY. No einsteinarena.com, no PubMed,
no arXiv. Arena tests use cached problem.json + locally-evaluated solutions;
lit-research tests use stub backends.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
PROJECTS_DIR = REPO_ROOT / "projects"


# Ensure every E2E test can `from polish import ...` etc. without fiddling with
# per-test sys.path boilerplate. Each skill's scripts/ folder is prepended once.
for skill in (
    "ops-ulp-polish",
    "ops-parallel-tempering-sa",
    "sci-council",
    "sci-optimization-recipes",
    "sci-literature-research",
    "tool-arena-runner",
    "tool-einstein-arena",
):
    scripts_dir = SKILLS_DIR / skill / "scripts"
    if scripts_dir.is_dir():
        p = str(scripts_dir)
        if p not in sys.path:
            sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Marker registration (so `pytest -m slow` / `-m "not slow"` works cleanly)
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: tests taking more than ~5s wall-clock (convergence / real fixtures)",
    )
    config.addinivalue_line(
        "markers",
        "needs_arena_data: tests that need a projects/einstein-arena-*/ fixture",
    )


# ---------------------------------------------------------------------------
# Arena-project fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def arena_project_dirs() -> dict[str, Path]:
    """{slug: Path} for every projects/einstein-arena-*/ that exists on disk.

    projects/* is gitignored, so on a fresh clone this returns {} and
    arena-dependent tests should `pytest.skip` cleanly.
    """
    if not PROJECTS_DIR.is_dir():
        return {}
    return {
        p.name: p
        for p in sorted(PROJECTS_DIR.iterdir())
        if p.is_dir() and p.name.startswith("einstein-arena-")
    }


@pytest.fixture
def tmp_arena_project(tmp_path: Path) -> Path:
    """Scaffold a minimal arena project layout under tmp_path.

    Shape: {tmp}/problem.json + {tmp}/solutions/best.json + {tmp}/evaluator.py
    (no real arena data needed). For tests that exercise runner composition.
    """
    project = tmp_path / "arena-demo"
    (project / "solutions").mkdir(parents=True)
    (project / "problem.json").write_text(
        '{"id": 0, "title": "demo", "scoring": "minimize"}\n'
    )
    (project / "solutions" / "best.json").write_text('{"values": [1.0, 2.0, 3.0]}\n')
    (project / "evaluator.py").write_text(
        "def evaluate(data):\n    return float(sum(data.get('values', [])))\n"
    )
    return project


@pytest.fixture
def kissing_d11_fixture():
    """Return a (V, source_path) tuple from the first kissing-d11 warm-start
    we find on disk, or pytest.skip with a clear reason.

    Preference order (cheapest to load first):
      1. solutions_d11_594_flip.npy   — known valid (score 0 under exact check)
      2. v594_rotated.npy             — known valid
      3. solutions_d11_594_novel.npy  — known non-zero loss (heavier polish test)
      4. any other solutions_d11_594_*.npy

    All four live under projects/einstein-arena-kissing-d11/ (gitignored).
    """
    base = PROJECTS_DIR / "einstein-arena-kissing-d11"
    if not base.is_dir():
        pytest.skip("projects/einstein-arena-kissing-d11/ not present on disk")

    candidates = [
        base / "solutions_d11_594_flip.npy",
        base / "v594_rotated.npy",
        base / "solutions_d11_594_novel.npy",
    ]
    for p in candidates:
        if p.is_file():
            V = np.load(p).astype(np.float64)
            if V.shape == (594, 11):
                return V, p

    # Last-ditch: any 594x11 .npy under base/
    for p in sorted(base.glob("solutions_d11_594_*.npy")):
        try:
            V = np.load(p).astype(np.float64)
        except Exception:
            continue
        if V.shape == (594, 11):
            return V, p

    pytest.skip(f"no (594, 11) .npy warm-start found under {base}")


# ---------------------------------------------------------------------------
# Council response builders
# ---------------------------------------------------------------------------

_APPROACH_LINE_RE = (
    "{i}. {name} | P(BEAT): {p:.2f} | EFFORT: {effort} | REF: {ref}\n"
    "   Rationale: {rationale}\n"
)


def _build_response(approaches: list[tuple[str, float, str, str, str]], *,
                    dead_ends: str = "none", confidence: float = 0.80) -> str:
    """approaches = [(name, p_beat, effort, ref, rationale), ...]"""
    lines = ["APPROACHES:"]
    for i, (name, p, effort, ref, rationale) in enumerate(approaches, start=1):
        lines.append(
            _APPROACH_LINE_RE.format(i=i, name=name, p=p, effort=effort, ref=ref,
                                     rationale=rationale).rstrip()
        )
    lines.append(f"DEAD_ENDS: {dead_ends}")
    lines.append(f"CONFIDENCE: {confidence:.2f}")
    return "\n".join(lines)


@pytest.fixture
def council_mock_responses():
    """Factory for parametric persona responses.

    Usage:
        responses = council_mock_responses(mode="all_agree", names=["Singer"])
        responses = council_mock_responses(mode="2of3_plus_dissent")
        responses = council_mock_responses(mode="all_distinct")
    """

    def _factory(mode: str, names: list[str] | None = None) -> dict[str, str]:
        if mode == "all_agree":
            names = names or ["Singer construction"]
            common = names[0]
            approaches = [(common, 0.90, "medium", "Singer 1938",
                           "Algebraic difference set.")]
            return {p: _build_response(approaches) for p in ("Gauss", "Erdős", "Tao")}
        if mode == "2of3_plus_dissent":
            shared = [("Shared-approach", 0.80, "medium", "ref-shared",
                       "Both Gauss and Erdős propose this one.")]
            dissent = [("Dissenting-approach", 0.75, "high", "ref-dissent",
                        "Tao only proposes this one.")]
            return {
                "Gauss": _build_response(shared),
                "Erdős": _build_response(shared),
                "Tao": _build_response(dissent),
            }
        if mode == "all_distinct":
            per = {
                "Gauss": [("Alpha-A", 0.70, "medium", "g-a", "r"),
                          ("Alpha-B", 0.65, "medium", "g-b", "r"),
                          ("Alpha-C", 0.60, "medium", "g-c", "r")],
                "Erdős": [("Beta-A", 0.70, "medium", "e-a", "r"),
                          ("Beta-B", 0.65, "medium", "e-b", "r"),
                          ("Beta-C", 0.60, "medium", "e-c", "r")],
                "Tao": [("Gamma-A", 0.70, "medium", "t-a", "r"),
                         ("Gamma-B", 0.65, "medium", "t-b", "r"),
                         ("Gamma-C", 0.60, "medium", "t-c", "r")],
            }
            return {persona: _build_response(per[persona]) for persona in per}
        raise ValueError(f"unknown mode: {mode}")

    return _factory
