# sci-council — smoke transcript

Minimal end-to-end demo confirming three personas synthesise a ranked table from mocked responses. Uses the same contract the Agent tool uses in production (monkey-patch `_call_persona` for the test harness; swap in a real Agent invocation for production).

## Invocation

```python
from unittest.mock import patch
import sys
sys.path.insert(0, ".claude/skills/sci-council/scripts")
from council import run_council

GAUSS = """APPROACHES:
1. Cyclotomic lattice | P(BEAT): 0.80 | EFFORT: medium | REF: Gauss 1831
   Rationale: algebraic structure gives provable density.
2. Character-sum bound | P(BEAT): 0.60 | EFFORT: high | REF: Weil 1948
   Rationale: Fourier-side analysis of Gauss sums.
3. Reciprocity reframing | P(BEAT): 0.55 | EFFORT: low | REF: Gauss 1801
   Rationale: quadratic reciprocity flips the problem into a dual form.
DEAD_ENDS: Brute enumeration intractable beyond n=20.
CONFIDENCE: 0.85"""

ERDOS = """APPROACHES:
1. Probabilistic construction | P(BEAT): 0.70 | EFFORT: medium | REF: Erdős 1947
   Rationale: first moment shows a witness exists.
2. Extremal-combinatorics bound | P(BEAT): 0.55 | EFFORT: medium | REF: Erdős-Rado 1952
   Rationale: pigeonhole for the pair-count.
3. Cyclotomic lattice | P(BEAT): 0.80 | EFFORT: medium | REF: Gauss 1831
   Rationale: agrees with Gauss on the headline approach.
DEAD_ENDS: Pure deterministic search too slow.
CONFIDENCE: 0.75"""

TAO = """APPROACHES:
1. Entropy method | P(BEAT): 0.65 | EFFORT: high | REF: Tao 2012
   Rationale: relative-entropy bound cuts the feasibility region.
2. Multi-scale decomposition | P(BEAT): 0.60 | EFFORT: medium | REF: Tao 2006
   Rationale: dyadic partitioning localises the extremal example.
3. Cyclotomic lattice | P(BEAT): 0.80 | EFFORT: medium | REF: Gauss 1831
   Rationale: both persona agree this is the right frame.
DEAD_ENDS: Direct algebraic constructions break above d=8.
CONFIDENCE: 0.80"""

mapping = {"Gauss": GAUSS, "Erdős": ERDOS, "Tao": TAO}

with patch("council._call_persona", side_effect=lambda p, q: mapping[p]):
    out = run_council("example problem statement here")

print(out)
```

## Expected output (shape)

```
## Council Synthesis

### Ranked Approaches
| Rank | Approach | Composite Score | Consensus | Effort | Mean P(BEAT) | Who proposes |
|------|----------|-----------------|-----------|--------|--------------|-------------|
| 1 | Cyclotomic lattice | 0.533 | 🔴 3/3 | medium | 0.80 | Gauss, Erdős, Tao |
| 2 | Entropy method | 0.260 | 🟢 1/3 | high | 0.65 | Tao |
| 3 | Probabilistic construction | 0.467 | 🟢 1/3 | medium | 0.70 | Erdős |
| ... |

### Council Confidence
Mean: 0.80 across 3 persona(s).
```

Invariants the smoke test confirms:

- Output begins with `## Council Synthesis`.
- A markdown table with rank / approach / composite score / consensus / effort / P(BEAT) / who is emitted.
- Duplicate approaches (Cyclotomic lattice named by all 3) collapse to a single row with 3/3 consensus.
- Mean confidence line prints when at least one persona returned `CONFIDENCE:`.

## Related tests

Full coverage in `tests/test_council.py::test_happy_path_ranked_table`, `test_duplicate_approach_deduplication`, `test_no_agreement_nine_entries`.
