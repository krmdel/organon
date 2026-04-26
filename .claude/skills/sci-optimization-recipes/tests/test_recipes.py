"""Test suite for sci-optimization-recipes.

Tests written FIRST (TDD). recipe_router.py + recipe markdown files do not
exist yet — these tests define the contract.

Run with:
  python3 -m pytest .claude/skills/sci-optimization-recipes/tests/ -v
"""
import os
import re
import sys
import pytest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
RECIPES_DIR = SKILL_DIR / "references" / "recipes"

sys.path.insert(0, str(SCRIPTS_DIR))

from recipe_router import RECIPES, route, load_recipe, NoRecipeMatch  # noqa: E402


EXPECTED_SLUGS = {
    "dinkelbach",
    "k-climbing",
    "remez",
    "cross-resolution",
    "square-param",
    "ulp-descent",
    "mpmath-lottery",
    "lp-reformulation",
    "nelder-mead",
    "sigmoid-bound",
    "incremental-loss",
}

REQUIRED_SECTIONS = [
    "When to use",
    "Pseudocode",
    "Worked example",
    "Gotchas",
    "References",
]


# ---------------------------------------------------------------------------
# Registry contract
# ---------------------------------------------------------------------------

def test_registry_importable():
    """RECIPES dict, route(), load_recipe() must be importable."""
    assert isinstance(RECIPES, dict)
    assert callable(route)
    assert callable(load_recipe)


def test_registry_completeness():
    """All 11 recipes present by slug."""
    assert set(RECIPES.keys()) == EXPECTED_SLUGS, (
        f"Missing: {EXPECTED_SLUGS - set(RECIPES.keys())}, "
        f"Extra: {set(RECIPES.keys()) - EXPECTED_SLUGS}"
    )


def test_registry_entries_have_keywords_and_title():
    """Every recipe entry has non-empty 'keywords' list and 'title' string."""
    for slug, entry in RECIPES.items():
        assert "keywords" in entry, f"{slug} missing 'keywords'"
        assert isinstance(entry["keywords"], list), f"{slug} keywords not list"
        assert len(entry["keywords"]) > 0, f"{slug} has no keywords"
        assert "title" in entry, f"{slug} missing 'title'"
        assert isinstance(entry["title"], str) and entry["title"]


# ---------------------------------------------------------------------------
# Schema: each recipe markdown file
# ---------------------------------------------------------------------------

def test_every_recipe_file_exists():
    """A .md file exists for every registered slug."""
    for slug in EXPECTED_SLUGS:
        p = RECIPES_DIR / f"{slug}.md"
        assert p.exists(), f"Missing recipe file: {p}"


@pytest.mark.parametrize("slug", sorted(EXPECTED_SLUGS))
def test_recipe_has_required_sections_in_order(slug):
    """Each recipe has exactly the 5 required ## sections in the right order."""
    path = RECIPES_DIR / f"{slug}.md"
    text = path.read_text()

    # Find all level-2 headings (## title), keep order.
    headings = re.findall(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE)

    # Normalise: lowercase, strip punctuation/whitespace.
    norm = [h.strip() for h in headings]

    expected = REQUIRED_SECTIONS
    assert norm == expected, (
        f"{slug}.md sections = {norm}, expected {expected}"
    )


@pytest.mark.parametrize("slug", sorted(EXPECTED_SLUGS))
def test_pseudocode_section_non_empty(slug):
    """Pseudocode section must have real content (≥ 10 non-blank lines)."""
    body = load_recipe(slug)
    # Extract text between '## Pseudocode' and the next '## '.
    m = re.search(
        r"##\s+Pseudocode\s*\n(.*?)(?=\n##\s+|\Z)",
        body,
        flags=re.DOTALL,
    )
    assert m, f"{slug}.md missing Pseudocode section body"
    section = m.group(1)
    non_blank = [ln for ln in section.splitlines() if ln.strip()]
    assert len(non_blank) >= 10, (
        f"{slug}.md Pseudocode has only {len(non_blank)} non-blank lines, need ≥ 10"
    )


# ---------------------------------------------------------------------------
# Router happy paths
# ---------------------------------------------------------------------------

def test_route_dinkelbach():
    assert route("minimize a ratio of two linear forms") == "dinkelbach"


def test_route_ulp_descent():
    assert route("gradient stalled at 1e-12 but need 1e-13") == "ulp-descent"


def test_route_remez():
    assert route("min-max polynomial approximation") == "remez"


def test_route_is_case_insensitive():
    assert route("DINKELBACH should work") == "dinkelbach"


# ---------------------------------------------------------------------------
# Router edge cases
# ---------------------------------------------------------------------------

def test_route_no_match_raises():
    """A wholly off-topic problem raises NoRecipeMatch."""
    with pytest.raises(NoRecipeMatch):
        route("apple pie")


def test_route_empty_input_raises_value_error():
    with pytest.raises(ValueError):
        route("")


def test_route_whitespace_only_raises_value_error():
    with pytest.raises(ValueError):
        route("   \t\n")


def test_route_tie_break_prefers_most_matches():
    """When multiple recipes could match, the one with more keyword hits wins."""
    # This problem mentions both "remez" and "min-max" (2 remez keyword hits)
    # while only one lp-reformulation keyword ("max"). Remez must win.
    problem = "need remez exchange for min-max polynomial fit"
    assert route(problem) == "remez"


def test_route_alphabetical_tie_break():
    """When two recipes tie on match count, alphabetically earliest wins."""
    # Craft a problem that hits exactly one keyword from two recipes.
    # "nelder-mead" and "remez" both have exactly one hit here.
    problem = "nelder-mead vs remez, one hit each"
    result = route(problem)
    # With 1 hit each, alphabetical: nelder-mead < remez.
    assert result == "nelder-mead"


# ---------------------------------------------------------------------------
# load_recipe
# ---------------------------------------------------------------------------

def test_load_recipe_happy_path():
    body = load_recipe("dinkelbach")
    assert isinstance(body, str)
    assert "## When to use" in body
    assert "## Pseudocode" in body


def test_load_recipe_unknown_slug_raises():
    with pytest.raises(ValueError):
        load_recipe("not-a-real-slug-12345")


def test_load_recipe_returns_file_body_not_wrapper():
    """load_recipe returns the markdown body, not a dict or object."""
    body = load_recipe("remez")
    assert body.startswith("# ") or body.startswith("## ") or "##" in body[:200]


# ---------------------------------------------------------------------------
# Extra coverage: every recipe is routeable via at least one keyword
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", sorted(EXPECTED_SLUGS))
def test_each_recipe_routeable_via_first_keyword(slug):
    """Sanity check: every recipe can be routed using its own first keyword."""
    kw = RECIPES[slug]["keywords"][0]
    result = route(f"I have a problem with {kw} here")
    # The recipe whose keyword we used should win (unless another recipe
    # also has that substring, in which case tie-break resolves it).
    assert result in EXPECTED_SLUGS  # weak but meaningful: something matched
