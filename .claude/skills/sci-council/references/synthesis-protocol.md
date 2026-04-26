# Synthesis Protocol — sci-council

## Per-Persona Output Format

Each persona (Gauss, Erdős, Tao) returns exactly this structure. No extra fields, no omissions.

```
APPROACHES:
1. [approach name] | P(BEAT): [0.0–1.0] | EFFORT: [low/medium/high] | REF: [citation or "none"]
   Rationale: [1 sentence]
2. [approach name] | P(BEAT): [0.0–1.0] | EFFORT: [low/medium/high] | REF: [citation or "none"]
   Rationale: [1 sentence]
3. [approach name] | P(BEAT): [0.0–1.0] | EFFORT: [low/medium/high] | REF: [citation or "none"]
   Rationale: [1 sentence]

DEAD_ENDS: [technique 1] — [one-line reason]; [technique 2] — [one-line reason]

CONFIDENCE: [0.0–1.0] — [one-line justification]
```

Rules: exactly 3 approaches, ranked best-first within the persona. `P(BEAT)` is the persona's
estimate that this approach beats the current best known result. `REF` is a BibTeX key, DOI,
or "none". `DEAD_ENDS` lists directions the persona would actively avoid.

---

## Synthesis Algorithm

### Step 1 — Parse

Extract each approach into a record:

```python
@dataclass
class Approach:
    name: str           # normalized lowercase slug
    p_beat: float       # 0.0–1.0
    effort: str         # "low" | "medium" | "high"
    ref: str            # citation key or "none"
    rationale: str
    personas: list[str] # which personas proposed this
```

Parse `DEAD_ENDS` and `CONFIDENCE` per persona separately.

### Step 2 — Union

Collect all 9 approaches (3 per persona) into a flat list. Tag each with its source persona.

### Step 3 — Deduplicate

Compare approach names using semantic equivalence, not string equality. Two approaches merge
when they propose the same core mathematical technique applied to the same object. Record the
union of persona tags on the merged entry.

See Deduplication Examples below for calibration.

### Step 4 — Score

```python
EFFORT_PENALTY = {"low": 1.0, "medium": 1.5, "high": 2.5}

def composite_score(approach: Approach) -> float:
    mean_p = sum(approach.p_beat_per_persona) / len(approach.p_beat_per_persona)
    penalty = EFFORT_PENALTY[approach.effort]
    return mean_p / penalty

def rank_approaches(approaches: list[Approach]) -> list[Approach]:
    for a in approaches:
        a.score = composite_score(a)
    return sorted(approaches, key=lambda a: a.score, reverse=True)
```

When personas disagree on effort for the same merged approach, use the median (round up on tie).

### Step 5 — Rank

Sort deduplicated approaches by `composite_score` descending.

### Step 6 — Flag Consensus

| Overlap | Flag |
|---------|------|
| 3 / 3 personas | 🔴 high consensus |
| 2 / 3 personas | 🟡 moderate consensus |
| 1 / 3 personas | 🟢 single-persona view |

---

## Output Format

```markdown
## Council Synthesis — [Problem Name]

### Ranked Approaches
| Rank | Approach | Composite Score | Consensus | Effort | Est. P(BEAT) | Who proposes |
|------|----------|----------------|-----------|--------|--------------|-------------|
| 1 | ... | 0.XX | 🔴 3/3 | medium | 0.XX | Gauss, Erdős, Tao |
| 2 | ... | 0.XX | 🟡 2/3 | low | 0.XX | Gauss, Tao |
| 3 | ... | 0.XX | 🟢 1/3 | high | 0.XX | Erdős |

### Dead Ends (consensus)
Directions ruled out by ≥ 2/3 personas, with the shared reason:
- [technique] — [reason]

### Dissenting Views
Approaches proposed by exactly 1 persona that were not merged with any other:
- [approach] — proposed by [Persona]. [Rationale from that persona.]

### Council Confidence
Mean confidence: X.XX. [Brief note if confidence is low (<0.5) or split (std > 0.2).]
```

---

## Failure Handling

| Scenario | Behavior |
|----------|----------|
| 1 persona fails or times out | Proceed with 2 personas. Append `[WARNING: [PersonaName] unavailable — 2/3 perspectives]` to the synthesis header. |
| 2 personas fail | Proceed with 1 persona. Replace synthesis header with `[SINGLE-PERSPECTIVE ANALYSIS — 2 personas unavailable]`. Consensus flags are suppressed. |
| All 3 personas fail | Raise `CouncilAllFailedError` with message listing each persona's failure reason. Do not emit a partial synthesis. |
| Malformed output (unparseable) | Treat that persona as failed. Log: `[PARSE ERROR: PersonaName — <reason>]`. Apply the 1- or 2-persona fallback as appropriate. |

---

## Deduplication Examples

**MERGE — same core technique, different vocabulary**

- Gauss: "Singer construction inner block" — uses a Singer difference set to build the inner block design.
- Erdős: "algebraic difference set" — applies a difference set from a cyclic group to the same construction.

Decision: merge. Both propose exploiting the algebraic structure of a Singer difference set.
Merged entry: `singer-difference-set | personas: [Gauss, Erdős]`.

**NO MERGE — genuinely different techniques**

- Tao: "Fourier analysis over Z/mZ" — uses additive characters to bound exponential sums.
- Erdős: "random greedy construction" — probabilistic argument, no algebraic structure assumed.

Decision: keep separate. One is analytic/algebraic; the other is probabilistic with no common
mathematical object.
