---
name: sci-council
description: Three-persona mathematical research fan-out. Asks Gauss (algebraic / number-theoretic), Erdős (probabilistic / extremal), and Tao (harmonic / arithmetic-combinatorics) the same problem independently in parallel, then synthesises their 3×3 proposals into one ranked table with cross-persona consensus flags and composite scores. Use when a hard math problem needs breadth — stuck competitions, Einstein Arena openings, a new research question where a single frame is likely to miss something. Triggers "research council", "ask the council", "mathematician council", "3 personas", "gauss erdos tao", "fan out personas", "research fan-out". Does NOT trigger for literature search (use sci-literature-research) or single-author scientific writing (use sci-writing).
---

# sci-council — 3-persona research fan-out

## When to use

You have a hard math / optimisation problem where one frame is likely to miss
the winning idea. Examples:

- Einstein Arena opening sessions where you haven't committed to an approach yet.
- A plateau on an active campaign where a fresh frame might surface a non-local move.
- Research-grade "how do I even think about this" questions.

Skip when:
- The problem is already well-routed (a specific arena submission polish — use
  `sci-optimization` or `ops-ulp-polish` instead).
- You need a literature search, not a research plan (use `sci-literature-research`).
- You're drafting prose, not proposing methods (use `sci-writing`).

## Methodology

1. **Fan out** — spawn three persona sub-agents (Gauss / Erdős / Tao) in
   parallel with the same problem statement. Personas do not see each
   other's drafts.
2. **Each persona returns** exactly 3 ranked approaches using the schema in
   `references/synthesis-protocol.md` (approaches, dead ends, confidence).
3. **Synthesise** — union the 9 approaches, deduplicate by semantic
   equivalence, score by `mean(P(BEAT)) / EFFORT_PENALTY[median_effort]`,
   rank descending, flag consensus (1/3, 2/3, 3/3).
4. **Return** one markdown synthesis: ranked table + dead ends consensus +
   dissenting views + council confidence.

Personas are opinionated by design (see `references/personas.md`). Do not
blend them during the fan-out — adversarial diversity is the whole point.

## API

```python
from council import run_council, synthesize_responses, CouncilAllFailedError

# Fan-out + synthesis (happy path — 3 personas, default)
result = run_council("maximise the number of unit-distance pairs on n points in R^2")

# Custom persona list (e.g. add a sphere-packing specialist)
result = run_council(problem, personas=["Gauss", "Erdős", "Tao"], timeout_sec=120)

# Synthesis only (when you already have persona responses from elsewhere)
responses = {"Gauss": gauss_text, "Erdős": erdos_text, "Tao": tao_text}
result = synthesize_responses(responses)
```

Failure modes:
- `ValueError` — empty problem statement.
- `CouncilAllFailedError` — all personas failed or timed out.
- 1 or 2 persona failures are tolerated; the synthesis header is annotated with
  the degraded state (`[WARNING: Erdős unavailable — 2/3 perspectives]`).

## Dependencies

| Dependency | Required | Provides | Fallback |
|---|---|---|---|
| Python 3.10+ | Yes | stdlib `concurrent.futures`, `dataclasses`, `re` | None |
| `pytest` | Dev-only | Test runner for `tests/test_council.py` | `unittest` |

No external API keys. When wired into the Agent tool for real persona
invocations, each persona call goes through the caller's configured LLM
provider — `_call_persona(persona_name, problem_statement)` is the single
monkey-patch point for testing and for swapping backends.

## References

- `references/personas.md` — full Gauss / Erdős / Tao profiles + "when they
  activate" pattern triggers.
- `references/synthesis-protocol.md` — output schema, synthesis algorithm,
  dedup calibration, output format, failure handling.

## Tests

```bash
python3 -m pytest .claude/skills/sci-council/tests/test_council.py -v
```

12 unit tests covering happy path, parallelism (max(t_i) not sum(t_i)),
single-persona failure, all-fail → CouncilAllFailedError, duplicate approach
dedup, no-consensus 9-row output, empty problem validation, persona override,
deterministic synthesis, per-persona timeout, and `parse_persona_response`
happy + malformed paths. All GREEN.

## Triggers

Use when: "research council", "ask the council", "mathematician council",
"3 personas", "gauss erdos tao", "gauss erdős tao", "fan out personas",
"research fan-out", "council on", "persona fan-out".

Do NOT use for: literature search (use `sci-literature-research`),
single-author scientific writing (use `sci-writing`), data analysis
(use `sci-data-analysis`), one-liner optimisation queries.
