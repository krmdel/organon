# sci-optimization-recipes — smoke transcript

Minimal invocation confirming the router dispatches correctly and the recipe body loads.

## Invocation

```python
import sys
sys.path.insert(0, ".claude/skills/sci-optimization-recipes/scripts")
from recipe_router import RECIPES, route, load_recipe

# 1. Registry completeness
print(sorted(RECIPES.keys()))

# 2. Router dispatch for 3 canonical problems
print(route("minimise a ratio of two linear forms"))   # -> dinkelbach
print(route("gradient stalled at 1e-12 but need 1e-13"))  # -> ulp-descent
print(route("min-max polynomial approximation"))       # -> remez

# 3. Load a recipe body
body = load_recipe("dinkelbach")
print(body[:200])
```

## Expected output

```
['cross-resolution', 'dinkelbach', 'incremental-loss', 'k-climbing',
 'lp-reformulation', 'mpmath-lottery', 'nelder-mead', 'remez',
 'sigmoid-bound', 'square-param', 'ulp-descent']
dinkelbach
ulp-descent
remez
# Dinkelbach Algorithm for Fractional Programs

## When to use

You are minimising a ratio N(x) / D(x) ...
```

Invariants the smoke test confirms:
- `RECIPES` has exactly 11 entries.
- Router returns the expected slug for three canonical problem descriptions.
- `load_recipe` returns a markdown body (not the whole file frontmatter).

## Related tests

See `tests/test_recipes.py::test_route_dinkelbach`, `test_route_ulp_descent`, `test_route_remez`, `test_every_recipe_file_exists`.
