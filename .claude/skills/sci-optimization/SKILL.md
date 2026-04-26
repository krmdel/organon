---
name: sci-optimization
description: Mathematical optimization toolkit for competition math. LP solving, column generation, cutting-plane methods, ULP float64 polishing, and intelligent variable selection. Problem-agnostic primitives for Einstein Arena and similar platforms.
---

# Mathematical Optimization Toolkit

Reusable optimization primitives for competition math problems. LP solving, column
generation, constraint management, precision polishing. Problem-agnostic; works for
PNT, circle packing, Heilbronn, and similar constrained optimization problems.

## Modules

### lp_solver.py -- LP Solving Engine
Full-constraint and cutting-plane LP with scipy's HiGHS backend.

```python
from lp_solver import LPSolver
solver = LPSolver(keys, objective_fn, constraint_fn, bounds=(-10, 10))
result = solver.solve_full(time_limit=7200)
result = solver.solve_cutting_plane(n_init=3000, max_iters=50)
```

### column_generation.py -- Variable Selection Optimizer
Find optimal variable sets via reduced cost pricing from LP duals.

```python
from column_generation import ColumnGenerator
cg = ColumnGenerator(lp_result, constraint_fn)
rc = cg.price_candidates(candidates, constraint_points)
best = cg.iterative_generation(initial_keys, candidates, budget=2000)
```

### ulp_polish.py -- Float64 Precision Descent
Discrete descent at ULP (Unit in Last Place) granularity for squeezing the last
bits of score from a solution.

```python
from ulp_polish import ulp_step_descent
polished = ulp_step_descent(solution, evaluator_fn, max_rounds=5)
```

### post_lp_scaling.py -- Tolerance Exploitation
Binary search and per-variable optimization to exploit evaluator tolerance.

```python
from post_lp_scaling import optimal_scale, non_uniform_scale
scale, score = optimal_scale(solution, evaluator_fn)
```

### key_selector.py -- Intelligent Variable Selection
Multiple strategies for selecting the best subset of variables.

### constraint_builder.py -- Constraint Matrix Construction
Build constraint matrices for floor/ceil optimization problems.

### solution_analyzer.py -- Solution Comparison
Compare solutions, find patterns, decompose scores.

## Methodology

1. **Formulate**: Express the problem as min c'x s.t. Ax <= b, lb <= x <= ub
2. **Solve**: Full LP (exact) or cutting-plane (memory-efficient)
3. **Select**: If overcomplete, use importance-based or dual-guided selection
4. **Polish**: Scale to exploit evaluator tolerance, then ULP descent
5. **Verify**: Run evaluator, compare with leaderboard
6. **Iterate**: Column generation to prove or improve optimality

## Dependencies

| Dependency | Required | Provides | Fallback |
|---|---|---|---|
| `numpy` | Yes | Array operations, matrix math | None |
| `scipy` | Yes | LP solver (HiGHS backend) | None |
| `sympy` | Optional | Symbolic math for formulations | Manual formulation |

## Triggers

Use when: "optimize", "linear program", "LP solver", "column generation",
"cutting plane", "scale solution", "ULP polish", "float64 precision",
"competition math", "constraint optimization".

Do NOT use for: data analysis, statistics, plotting, hypothesis testing.
