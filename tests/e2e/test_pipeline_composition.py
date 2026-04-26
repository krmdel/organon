"""E.8 — Cross-skill composition pipelines.

Per context/memory/organon_upgrade_final_handoff.md §3.8. The ULTIMATE
integrity test: does a real user workflow compose correctly across
multiple new skills? Each case wires 2-3 skills together and asserts the
whole pipeline's shape + output correctness.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

# Skill APIs (prepended to sys.path by tests/e2e/conftest.py).
import council
from council import run_council
from pt_sa import parallel_tempering_sa
from polish import polish
from recon import recon
from tri_verify import tri_verify
from fanout import parallel_fanout
from recipe_router import RECIPES, load_recipe, route, NoRecipeMatch

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
PROJECTS_DIR = REPO_ROOT / "projects"
TEMPLATE = SKILLS_DIR / "tool-einstein-arena" / "assets" / "playbook-template.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _approach_line(name, p=0.80, effort="medium", ref="ref"):
    return f"1. {name} | P(BEAT): {p:.2f} | EFFORT: {effort} | REF: {ref}\n   Rationale: r."


def _council_response(approach_name: str) -> str:
    return (
        "APPROACHES:\n"
        f"{_approach_line(approach_name)}\n"
        "DEAD_ENDS: none\n"
        "CONFIDENCE: 0.80"
    )


# ---------------------------------------------------------------------------
# E.8.1 — Council → route-to-recipe → apply
# ---------------------------------------------------------------------------

def test_e8_1_council_to_recipe_router():
    """Three personas all suggest an approach whose name contains router
    keywords. The synthesised output should then route to a real recipe."""
    # Use phrasing that clearly hits the 'ulp-descent' recipe's keywords.
    name = "apply ULP descent for precision polish at the float64 floor"
    responses = {p: _council_response(name) for p in ("Gauss", "Erdős", "Tao")}

    with patch("council._call_persona", side_effect=lambda p, q: responses[p]):
        synthesis = run_council("How do we break past 1e-12?")

    # The synthesis output must contain the approach name — feed that to the router.
    assert name.lower() in synthesis.lower()
    slug = route(name)
    assert slug == "ulp-descent"
    # And load_recipe succeeds on the routed slug.
    body = load_recipe(slug)
    assert "When to use" in body


# ---------------------------------------------------------------------------
# E.8.2 — arena-runner recon → template fill → schema validate
# ---------------------------------------------------------------------------

def test_e8_2_recon_to_fill_to_schema_roundtrip(tmp_path):
    import sys as _sys
    skill_tests = SKILLS_DIR / "tool-einstein-arena" / "tests"
    if str(skill_tests) not in _sys.path:
        _sys.path.insert(0, str(skill_tests))
    from test_playbook_structure import EXPECTED_SECTIONS, _parse_sections

    project = tmp_path / "e8-2"
    recon(slug="test-e2e", project_dir=project, template_path=TEMPLATE)

    md = (project / "PLAYBOOK.md").read_text()
    # Auto-fill every placeholder.
    filled = re.sub(r"<!--\s*fill:\s*[^-]*(?:-(?!->)[^-]*)*-->", "ok", md, flags=re.DOTALL)
    (project / "PLAYBOOK.md").write_text(filled)

    assert _parse_sections(filled) == EXPECTED_SECTIONS
    leftover = re.findall(r"<!--\s*fill:[^>]+-->", filled)
    assert not leftover


# ---------------------------------------------------------------------------
# E.8.3 — PT-SA warm-start → ULP polish
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_e8_3_ptsa_then_polish():
    """Minimise f(x) = Σx² via PT-SA, then polish with ULP descent. Polish
    must not MAKE IT WORSE (it may be a no-op if PT-SA already landed at the
    float64 floor, which is the common case for this toy objective)."""
    def loss(x):
        return float((x ** 2).sum())

    x0 = np.array([3.0, 3.0, 3.0], dtype=np.float64)

    def propose(state, rng, idx=None):
        new = state.copy()
        if idx is None:
            idx = int(rng.integers(0, state.size))
        new[idx] = new[idx] + rng.normal(0.0, 0.1)
        return new, (idx, 0.0)

    out = parallel_tempering_sa(
        x0, loss, propose,
        n_replicas=4, t_min=1e-6, t_max=1.0,
        max_steps=800, exchange_every=25, seed=17,
    )
    pt_best = out["best_loss"]
    best_state = out["best_state"].reshape(1, -1)  # polish needs a 2-D matrix

    # polish expects (n, d); treat the whole vector as one row.
    # Use a trivial evaluator that matches the kissing-API signature.
    def eval_fn(V):
        return float((V.flatten() ** 2).sum())

    V_out, polished = polish(best_state, eval_fn,
                              max_ulps=2, max_sweeps=2,
                              budget_sec=5.0, verbose=False)

    assert polished <= pt_best + 1e-12, (
        f"polish regressed: PT={pt_best}, polish={polished}"
    )


# ---------------------------------------------------------------------------
# E.8.4 — Fanout result → council problem framing (shape compatibility)
# ---------------------------------------------------------------------------

def test_e8_4_fanout_feeds_council_shape():
    def mk(offset):
        return lambda q: [
            {"doi": f"10.{offset}/{i}", "title": f"Dinkelbach study {i}",
             "year": 2024, "authors": ["A"]}
            for i in range(10)
        ]
    backends = {"pubmed": mk(100), "arxiv": mk(200), "s2": mk(300)}
    fanout_out = parallel_fanout("Dinkelbach", backends, timeout_per_source=2.0)
    assert len(fanout_out["results"]) == 30

    # Council stubs that would reasonably reference Dinkelbach:
    responses = {
        p: _council_response(f"Apply Dinkelbach — see {fanout_out['results'][0]['title']}")
        for p in ("Gauss", "Erdős", "Tao")
    }
    with patch("council._call_persona", side_effect=lambda p, q: responses[p]):
        synthesis = run_council("How do we handle N(x)/D(x)?")

    # Compatibility assertion: 30 papers ≥ 3 approaches (the fanout output can
    # plausibly fund any persona's reading list without running out).
    assert len(fanout_out["results"]) >= 3
    assert "Dinkelbach" in synthesis


# ---------------------------------------------------------------------------
# E.8.5 — Tri-verify on a real arena solution
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.needs_arena_data
def test_e8_5_triverify_kissing_d11(kissing_d11_fixture):
    V, _ = kissing_d11_fixture

    def float_score():
        norms = np.sqrt((V ** 2).sum(axis=1, keepdims=True))
        c = 2.0 * V / norms
        d2 = ((c[:, None, :] - c[None, :, :]) ** 2).sum(-1)
        iu = np.triu_indices(V.shape[0], k=1)
        pair = d2[iu]
        under = pair < 4.0
        if not under.any():
            return 0.0
        return float((2.0 - np.sqrt(pair[under])).sum())

    def alt_score():
        # Same loss via a slightly different formulation — should agree exactly
        # on a valid configuration.
        norms = np.linalg.norm(V, axis=1)
        c = V * (2.0 / norms)[:, None]
        total = 0.0
        n = V.shape[0]
        for i in range(n):
            diff = c[i + 1:] - c[i]
            d = np.linalg.norm(diff, axis=1)
            violating = d < 2.0
            total += (2.0 - d[violating]).sum()
        return float(total)

    result = tri_verify(float_score, None, alt_score, tolerance=1e-6)
    assert result["status"] == "pass", result
    assert result["methods_run"] == 2
    assert result["methods_agree"] == 2


# ---------------------------------------------------------------------------
# E.8.6 — Full arena-campaign dry run
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_e8_6_full_campaign_dry_run(tmp_path):
    """The big one: recon → auto-fill → (toy) PT-SA → polish → tri-verify.
    We skip the real-arena-data step entirely (replaced by a synthetic
    3-vector problem) so this always runs."""
    import sys as _sys
    skill_tests = SKILLS_DIR / "tool-einstein-arena" / "tests"
    if str(skill_tests) not in _sys.path:
        _sys.path.insert(0, str(skill_tests))
    from test_playbook_structure import EXPECTED_SECTIONS, _parse_sections

    # 1. recon
    project = tmp_path / "e8-6"
    recon(slug="e8-6-demo", project_dir=project, template_path=TEMPLATE)
    playbook = project / "PLAYBOOK.md"
    assert playbook.is_file()

    # 2. auto-fill the playbook
    filled = re.sub(r"<!--\s*fill:\s*[^-]*(?:-(?!->)[^-]*)*-->", "ok",
                    playbook.read_text(), flags=re.DOTALL)
    playbook.write_text(filled)

    # 3. small PT-SA
    def loss(x): return float((x ** 2).sum())
    def propose(s, rng, idx=None):
        new = s.copy()
        idx = idx if idx is not None else int(rng.integers(0, s.size))
        new[idx] += rng.normal(0.0, 0.1)
        return new, (idx, 0.0)

    pt = parallel_tempering_sa(
        np.array([2.0, 2.0], dtype=np.float64), loss, propose,
        n_replicas=2, t_min=1e-4, t_max=0.5,
        max_steps=300, exchange_every=20, seed=1,
    )

    # 4. polish
    V_in = pt["best_state"].reshape(1, -1)
    _, polished = polish(V_in, lambda V: float((V.flatten() ** 2).sum()),
                          max_ulps=1, max_sweeps=1,
                          budget_sec=2.0, verbose=False)
    assert polished <= pt["best_loss"] + 1e-12

    # 5. tri-verify with 2 methods
    result = tri_verify(lambda: polished, None, lambda: polished, tolerance=1e-9)
    assert result["status"] == "pass"

    # 6. Playbook still schema-valid at end-of-pipeline.
    assert _parse_sections(playbook.read_text()) == EXPECTED_SECTIONS


# ---------------------------------------------------------------------------
# E.8.7 — Full parallel-agent dry run (council → recipes)
# ---------------------------------------------------------------------------

def test_e8_7_parallel_agent_dry_run():
    """Three personas propose three approaches each; route every approach
    name through the recipe router. Assert ≥ 2 of the approach phrases hit
    a known recipe — sanity bound on recipe coverage of common techniques."""

    persona_approaches = {
        "Gauss": [
            "try ULP descent to polish past 1e-12",
            "use Dinkelbach for the fractional program",
            "remez equioscillation for the minimax polynomial",
        ],
        "Erdős": [
            "k-climb the deceptive landscape via variable neighborhood",
            "apply LP reform with epigraph",
            "mpmath arbitrary precision lottery",
        ],
        "Tao": [
            "cross-resolution warm-start basin transfer",
            "square param x=s^2 to break peak-lock",
            "nelder-mead simplex method fallback",
        ],
    }

    routed_count = 0
    total = 0
    for persona, approaches in persona_approaches.items():
        for approach in approaches:
            total += 1
            try:
                slug = route(approach)
            except NoRecipeMatch:
                continue
            if slug in RECIPES:
                routed_count += 1

    # 9 approaches, every one should hit a recipe — but loose bound of ≥ 2
    # per handoff §3.8 E.8.7 language ("sanity bound on recipe coverage").
    assert routed_count >= 2, f"only {routed_count}/{total} approaches routed"
    # In practice this run should achieve 9/9:
    assert routed_count == 9, (
        f"expected 9/9 coverage, got {routed_count}/9 — router may have regressed"
    )
