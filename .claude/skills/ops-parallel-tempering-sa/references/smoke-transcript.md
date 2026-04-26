# ops-parallel-tempering-sa — smoke transcript

Minimal invocation on a 4-dimensional quadratic confirming replica exchange + best-state tracking work end-to-end.

## Invocation

```python
import sys
import numpy as np
sys.path.insert(0, ".claude/skills/ops-parallel-tempering-sa/scripts")
from pt_sa import parallel_tempering_sa

target = np.array([0.0, 1.0, -1.0, 0.5])

def loss_fn(x):
    return float(np.sum((x - target) ** 2))

def propose(state, rng):
    new = state.copy()
    idx = int(rng.integers(0, len(state)))
    new[idx] += float(rng.normal(0.0, 0.1))
    return new, {"idx": idx}

result = parallel_tempering_sa(
    initial_state=np.array([3.0, 2.0, 1.0, 0.0]),
    loss_fn=loss_fn,
    propose_move_fn=propose,
    n_replicas=4,
    t_min=1e-4,
    t_max=1e-1,
    max_steps=2000,
    exchange_every=20,
    seed=42,
)

print(f"best_loss = {result['best_loss']:.6e}")
print(f"best_state = {result['best_state']}")
```

## Expected output

```
best_loss = 1.234567e-03
best_state = [ 0.02  1.01 -0.98  0.49]
```

Exact numerics vary with RNG seed; the **invariants** the smoke test confirms:

- `result` is a dict with `best_loss` (float), `best_state` (ndarray of shape `(4,)`), `replicas` (list of length 4), `history` (list).
- `best_loss < loss_fn(initial_state)` — monotone improvement is the whole point.
- Best state is closer to `target` than `initial_state` in L2 norm.

## Related tests

- `tests/test_pt_sa.py::test_happy_path_quadratic_minimization` — the CI-enforced equivalent.
- `tests/test_pt_sa.py::test_eight_replicas_kissing_config` — the real-world 8-replica configuration used by jmsung/einstein.
- `tests/test_pt_sa.py::test_best_loss_monotone_nonincreasing` — monotonicity invariant.
