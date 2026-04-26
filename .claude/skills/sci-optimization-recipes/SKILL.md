---
name: sci-optimization-recipes
description: Catalog of named optimisation recipes with trigger-based dispatch. Each recipe covers a distinct pattern (Dinkelbach for fractional programs, k-climbing for deceptive landscapes, Remez exchange for minimax polynomial, cross-resolution basin transfer, square parameterisation, ULP descent, mpmath precision lottery, LP reformulation, Nelder-Mead / L-BFGS fallbacks, sigmoid bounding, incremental O(n) loss) with trigger conditions, pseudocode, worked example, gotchas, and citations. Router matches the user's problem description against recipe keywords and returns the best fit. Use when you want a principled pattern before reaching for ad-hoc code. Triggers "optimization recipe", "recipe for", "dinkelbach", "variable neighborhood", "remez exchange", "cross-resolution transfer", "ulp descent", "lp reformulation", "mpmath lottery", "sigmoid bounding", "incremental loss". Does NOT trigger for literature search, data analysis, or writing.
---

# sci-optimization-recipes — recipe catalog + dispatcher

## When to use

You're stuck on a math/optimisation problem and want to find the right named pattern before writing code. Examples:

- "Minimise n(x) / d(x) with n, d linear" → Dinkelbach.
- "Gradient stalled at 1e-12 but exact evaluator says residual is 1e-13" → ULP descent.
- "Min-max polynomial approximation of an arbitrary function on [a,b]" → Remez exchange.
- "I have an n-body objective and a per-coordinate sweep — too slow" → incremental O(n) loss.

Skip when:
- The problem is a direct instantiation of a specific skill (use `sci-optimization` for LP/ULP, `ops-parallel-tempering-sa` for PT-SA, `ops-ulp-polish` for ULP polish). This catalog is the _router_ to those skills plus a library of algorithms that don't yet have dedicated skills.
- You already know the recipe — just apply it.
- You need a literature search (use `sci-literature-research`) or a research plan (use `sci-council`).

## Methodology

1. **Describe the problem in one sentence** — include objective type, constraints, known difficulty modes (non-smoothness, multi-modality, float-precision floor, etc.).
2. **Call the router**:
   ```python
   from recipe_router import route, load_recipe, RECIPES
   slug = route("minimise a ratio of two linear forms")  # → "dinkelbach"
   body = load_recipe(slug)                              # raw markdown
   ```
3. **Read the recipe** — every recipe has the same 5 sections: `When to use` / `Pseudocode` / `Worked example` / `Gotchas` / `References`.
4. **Apply** — copy the pseudocode, adapt to your problem, cross-check against the gotchas list.
5. **If nothing matches**, `route()` returns `None` — fall back to `sci-council` (three-persona research fan-out) or `sci-literature-research` for a targeted search.

## API

```python
from recipe_router import RECIPES, route, load_recipe, NoRecipeMatch

# Exhaustive catalog
print(list(RECIPES.keys()))
# ['dinkelbach', 'k-climbing', 'remez', 'cross-resolution', 'square-param',
#  'ulp-descent', 'mpmath-lottery', 'lp-reformulation', 'nelder-mead',
#  'sigmoid-bound', 'incremental-loss']

# Single-line dispatch
route("min-max polynomial approximation")   # → "remez"
route("apple pie")                          # → None  (or raises NoRecipeMatch)
route("")                                   # raises ValueError

# Load a recipe body (raw markdown)
md = load_recipe("dinkelbach")
print(md[:200])  # first 200 chars
```

Ties are broken alphabetically by slug. Matching is case-insensitive on keywords. `NoRecipeMatch` is available for callers that prefer an exception over `None`.

## Dependencies

| Dependency | Required | Provides | Fallback |
|---|---|---|---|
| Python 3.8+ | Yes | stdlib only (`re`, `pathlib`) | None |
| `pytest` | Dev-only | Test runner | `unittest` |

No external API keys. No network calls. Entirely offline.

## References

Each recipe has its own per-file references section. The catalog is at `references/recipes/`:

- `dinkelbach.md` — Dinkelbach 1967 parametric algorithm for fractional programs.
- `k-climbing.md` — Variable neighbourhood search / k-climbing (Hansen-Mladenović VNS).
- `remez.md` — Equioscillation + Remez exchange for minimax polynomial approximation.
- `cross-resolution.md` — Low-res → high-res basin transfer (pack-30k → n=90k pattern).
- `square-param.md` — `x = s²` parameterisation to handle non-negative variables.
- `ulp-descent.md` — ULP coordinate descent (routes to `ops-ulp-polish`).
- `mpmath-lottery.md` — Arbitrary-precision nudge + round-to-float64.
- `lp-reformulation.md` — Epigraph trick for max-type objectives.
- `nelder-mead.md` — Gradient-free CPU fallback (Nelder-Mead / L-BFGS-B / hill climbing).
- `sigmoid-bound.md` — Sigmoid bounding for ratio objectives.
- `incremental-loss.md` — O(n) incremental pair-sum updates for n-body objectives.

## Tests

```bash
python3 -m pytest .claude/skills/sci-optimization-recipes/tests/ -v
```

The suite covers:
- Registry completeness (all 11 slugs present in `RECIPES`).
- Schema validation (every `*.md` under `references/recipes/` has the 5-section header structure).
- Router happy paths (`dinkelbach`, `ulp-descent`, `remez`).
- Case-insensitive keyword matching.
- Empty input `ValueError`.
- `NoRecipeMatch` (or `None`) on unmatched queries.
- Tie-breaking by slug alphabetical order.
- `load_recipe` happy path + bad-slug error.
- Non-empty Pseudocode section per recipe.

Line coverage target on `scripts/recipe_router.py` is ≥ 90%.

## Triggers

Use when: "optimization recipe", "recipe for", "which algorithm for", "dinkelbach", "variable neighborhood", "k-climbing", "remez exchange", "equioscillation", "cross-resolution transfer", "low-res warm-start", "square parameterization", "non-negative variable parameterization", "ulp descent", "float64 floor", "mpmath lottery", "precision lottery", "lp reformulation", "epigraph", "nelder-mead fallback", "l-bfgs fallback", "sigmoid bounding", "ratio objective", "incremental o(n) loss", "n-body pairwise update".

Do NOT use for: literature search (use `sci-literature-research`), mathematical research fan-out (use `sci-council`), direct data analysis (use `sci-data-analysis`), full manuscript drafting (use `sci-writing`).
