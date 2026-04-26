# sci-council -- real Agent-tool wiring

The unit tests in `tests/test_council.py` monkey-patch `council._call_persona`
so they can exercise the synthesiser without live sub-agents. That is still
the default contract. This doc covers the **production-wiring** path that
avoids monkey-patching and composes cleanly with the arena-attack-problem
pipeline.

## Two wiring modes

### Mode A -- `caller=` keyword (preferred for new code)

```python
from council import run_council, build_file_exchange_caller

caller = build_file_exchange_caller("/abs/path/to/campaign-workspace")
synthesis = run_council(
    "How do we break past 1e-12 on kissing-d11?",
    caller=caller,
    timeout_sec=600,
)
```

`build_file_exchange_caller(workspace)` returns a callable that:

1. Writes `{workspace}/council/requests/{persona}.txt` with the problem statement.
2. Blocks for up to 600 seconds waiting for `{workspace}/council/responses/{persona}.txt`.
3. Reads and returns the response string when the file appears.

Meanwhile, between step 1 and step 2, the parent Claude agent issues three
`Agent` tool calls in parallel -- one per persona. Each sub-agent's prompt
must end with a directive that tells it to write its response to the
expected path. Example for the Gauss persona:

```
Your answer MUST be written to:
    /abs/path/to/campaign-workspace/council/responses/Gauss.txt

Use the APPROACHES / DEAD_ENDS / CONFIDENCE format documented in
.claude/skills/sci-council/references/synthesis-protocol.md. No preamble.
```

This pattern is race-free (one file per persona, no shared mutable state),
scales to any persona count, and keeps `run_council` pure Python so it
stays unit-testable.

### Mode B -- monkey-patch `_call_persona` (legacy / tests only)

```python
from unittest.mock import patch
with patch("council._call_persona", side_effect=my_caller):
    synthesis = run_council(problem)
```

Still works for backward compatibility. Avoid for new wiring because it
mutates module-level state, which breaks concurrent council invocations.

## When to use which

| Context | Mode | Why |
|---|---|---|
| Production (arena-attack-problem, live council) | A | Thread-safe, composable |
| Unit test asserting synthesiser behaviour | B | Simpler; no filesystem |
| Integration test asserting the full `run_council` path | A with stub caller | Exercises the parameter surface |

## The `PersonaCaller` protocol

```python
PersonaCaller = Callable[[str, str], str]
# (persona_name: str, problem: str) -> raw_response: str
```

Any object matching this protocol can be passed as `caller=`. `build_file_exchange_caller`
is the canonical production implementation; swap in a custom one for:

- Direct API calls to a remote LLM service (bypass the Agent tool)
- Deterministic stubs in long-running integration tests
- Logging / telemetry wrappers around the default file-exchange caller
