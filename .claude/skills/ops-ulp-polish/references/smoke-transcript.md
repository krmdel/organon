# ops-ulp-polish — smoke transcript

Minimal end-to-end invocation, mid-April 2026. Confirms the skill runs, ingests a warm-start, and reports a final score lower or equal to init.

## Invocation

```bash
# From repo root
cat > /tmp/evaluator_demo.py <<'EOF'
import numpy as np
def evaluate(V):
    V = np.asarray(V, dtype=np.float64)
    # Minimise pair-sum squared-deviation from a target threshold.
    thr = 0.5
    total = 0.0
    n = len(V)
    for i in range(n):
        for j in range(i+1, n):
            d2 = float(((V[i] - V[j])**2).sum())
            if d2 < thr:
                total += thr - d2
    return total
EOF

python3 - <<'EOF'
import numpy as np
V = np.random.default_rng(1).uniform(0, 2, (10, 3)).astype(np.float64)
np.save("/tmp/warm.npy", V)
EOF

PYTHONPATH=/tmp python3 .claude/skills/ops-ulp-polish/scripts/polish.py \
  --config /tmp/warm.npy \
  --evaluator evaluator_demo:evaluate \
  --max-ulps 2 \
  --max-sweeps 2 \
  --budget-sec 10 \
  --out /tmp/out.npy
```

## Expected output

```
[ulp-polish] init score=1.234567e-01  target_sq=3.567890
[ulp-polish] sweep 1: score=1.234567e-01 (Δ=0.000e+00)  accepts=0  dt=0s
[ulp-polish] converged (no improving move)
final score = 1.234567e-01
saved /tmp/warm.polished.npy
```

Exact numerics vary with the RNG seed. The **invariants** the smoke test confirms:

- `[ulp-polish] init score=` line prints once.
- Every sweep prints `score=... accepts=... dt=...`.
- Either `[ulp-polish] converged` (no improving move) OR `[ulp-polish] reached 0` prints before the final score.
- `final score` is never strictly greater than the init score.
- `<warm>.polished.npy` exists on disk.

## Related tests

See `tests/test_polish.py::test_main_cli_roundtrip` for the CI-enforced equivalent.
