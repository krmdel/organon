"""Integration tests for sci-council's real Agent-tool wiring path.

Unit tests monkey-patch `_call_persona` at the module level. These tests
exercise the NEW caller-argument path (Mode A per
references/agent-tool-invocation.md) + the file-exchange production
caller. No module-state mutation; thread-safe across concurrent runs.

This closes Gap 7 from the 7-gap integration audit.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from council import (
    CouncilAllFailedError,
    build_file_exchange_caller,
    run_council,
)


def _persona_response(approach_name: str, p: float = 0.80,
                       effort: str = "medium", ref: str = "ref",
                       rationale: str = "rat") -> str:
    return (
        "APPROACHES:\n"
        f"1. {approach_name} | P(BEAT): {p:.2f} | EFFORT: {effort} | REF: {ref}\n"
        f"   Rationale: {rationale}\n"
        "DEAD_ENDS: none\n"
        "CONFIDENCE: 0.80"
    )


class TestCallerArgumentPath:
    """Verify the `caller=` kwarg works end-to-end without touching
    module-level `_call_persona`."""

    def test_explicit_caller_bypasses_module_stub(self):
        """`_call_persona` raises NotImplementedError by default. Passing a
        caller must bypass it entirely."""
        def my_caller(persona: str, problem: str) -> str:
            return _persona_response(f"{persona}-approach")

        # If the caller-path is broken, this would raise NotImplementedError
        # from the default `_call_persona` stub.
        synthesis = run_council(
            "test problem",
            caller=my_caller,
            timeout_sec=5.0,
        )
        assert "Council Synthesis" in synthesis
        # All 3 default personas should appear in the rendered output.
        for persona in ("Gauss", "Erdős", "Tao"):
            assert persona in synthesis

    def test_caller_receives_persona_and_problem(self):
        """The caller signature is (persona_name, problem) -> str. Verify
        both args are forwarded correctly."""
        captured: list[tuple[str, str]] = []
        lock = threading.Lock()

        def recording_caller(persona: str, problem: str) -> str:
            with lock:
                captured.append((persona, problem))
            return _persona_response("X")

        run_council(
            "SPECIFIC PROBLEM STATEMENT",
            caller=recording_caller,
            timeout_sec=5.0,
        )
        assert {p for p, _ in captured} == {"Gauss", "Erdős", "Tao"}
        assert all(msg == "SPECIFIC PROBLEM STATEMENT" for _, msg in captured)

    def test_per_persona_caller_failures_are_tolerated(self):
        """If 1 of 3 callers raises, the synthesiser should degrade
        gracefully (same behaviour as the monkey-patched path)."""
        def partial_caller(persona: str, problem: str) -> str:
            if persona == "Tao":
                raise RuntimeError("simulated outage")
            return _persona_response(f"{persona}-plan")

        synthesis = run_council(
            "partial failure test",
            caller=partial_caller,
            timeout_sec=5.0,
        )
        assert "Council Synthesis" in synthesis
        # Degradation banner should mention Tao as missing
        assert "Tao" in synthesis

    def test_all_callers_fail_raises(self):
        """If every caller fails, CouncilAllFailedError fires."""
        def dead_caller(persona: str, problem: str) -> str:
            raise RuntimeError("all dead")

        with pytest.raises(CouncilAllFailedError):
            run_council(
                "all fail",
                caller=dead_caller,
                timeout_sec=5.0,
            )

    def test_caller_path_is_parallel_not_sequential(self):
        """A caller that sleeps 0.3s per persona must run in parallel --
        total wall-clock should be < 3 * 0.3s (sequential baseline)."""
        def slow_caller(persona: str, problem: str) -> str:
            time.sleep(0.3)
            return _persona_response(persona)

        t0 = time.monotonic()
        run_council("parallel test", caller=slow_caller, timeout_sec=5.0)
        elapsed = time.monotonic() - t0
        # Generous bound: 3 personas in parallel should finish well under 0.9s
        assert elapsed < 0.8, f"elapsed {elapsed:.2f}s suggests sequential execution"

    def test_caller_does_not_mutate_module_state(self):
        """After run_council(caller=...), the module-level `_call_persona`
        should still raise NotImplementedError. (Regression guard: nothing
        should sneak in and monkey-patch it via the caller path.)"""
        def my_caller(persona: str, problem: str) -> str:
            return _persona_response(persona)

        run_council("state-check", caller=my_caller, timeout_sec=5.0)

        # Post-condition: the default stub is untouched.
        import council as council_module
        with pytest.raises(NotImplementedError):
            council_module._call_persona("Gauss", "any problem")


class TestFileExchangeCaller:
    """Validate the file-exchange production caller used by
    arena-attack-problem's Stage-2 agent spawn."""

    def test_round_trip_with_pre_populated_responses(self, tmp_path):
        """If the response files exist BEFORE the caller starts polling,
        it returns immediately (no deadline wait)."""
        ws = tmp_path / "campaign"
        res_dir = ws / "council" / "responses"
        res_dir.mkdir(parents=True)

        for persona in ("Gauss", "Erdős", "Tao"):
            (res_dir / f"{persona}.txt").write_text(
                _persona_response(f"{persona}-preloaded")
            )

        caller = build_file_exchange_caller(ws)
        t0 = time.monotonic()
        synthesis = run_council("pre-populated", caller=caller, timeout_sec=30.0)
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"pre-populated run took {elapsed:.2f}s"
        assert "Council Synthesis" in synthesis
        assert "Gauss-preloaded" in synthesis or "preloaded" in synthesis.lower()

    def test_caller_writes_request_files(self, tmp_path):
        """Each persona's request file must land in the workspace."""
        ws = tmp_path / "campaign"
        res_dir = ws / "council" / "responses"
        res_dir.mkdir(parents=True)

        # Pre-populate responses so the caller doesn't block
        for persona in ("Gauss", "Erdős", "Tao"):
            (res_dir / f"{persona}.txt").write_text(_persona_response("x"))

        caller = build_file_exchange_caller(ws)
        run_council("request-capture test", caller=caller, timeout_sec=10.0)

        req_dir = ws / "council" / "requests"
        for persona in ("Gauss", "Erdős", "Tao"):
            req_file = req_dir / f"{persona}.txt"
            assert req_file.is_file(), f"missing request file for {persona}"
            assert req_file.read_text() == "request-capture test"

    def test_late_arriving_response_is_picked_up(self, tmp_path):
        """Simulate an Agent writing its response after a short delay.
        Caller should read it as soon as it appears."""
        ws = tmp_path / "campaign"
        res_dir = ws / "council" / "responses"
        res_dir.mkdir(parents=True)

        def _late_writer():
            time.sleep(0.5)
            for persona in ("Gauss", "Erdős", "Tao"):
                (res_dir / f"{persona}.txt").write_text(
                    _persona_response(f"{persona}-late")
                )

        writer = threading.Thread(target=_late_writer, daemon=True)
        writer.start()

        caller = build_file_exchange_caller(ws)
        synthesis = run_council("late-arrival", caller=caller, timeout_sec=10.0)
        writer.join(timeout=2.0)
        assert "Council Synthesis" in synthesis

    def test_caller_times_out_if_no_response(self, tmp_path):
        """The file-exchange caller has its own 600s internal cap, but
        `run_council`'s timeout_sec should short-circuit well before that."""
        ws = tmp_path / "campaign"
        (ws / "council" / "responses").mkdir(parents=True)
        (ws / "council" / "requests").mkdir(parents=True)

        caller = build_file_exchange_caller(ws)

        t0 = time.monotonic()
        with pytest.raises(CouncilAllFailedError):
            run_council("no responses ever", caller=caller, timeout_sec=0.5)
        elapsed = time.monotonic() - t0
        # Generous: the synchronous run_council timeout should kick in
        assert elapsed < 3.0, f"timeout did not fire in time: {elapsed:.2f}s"


class TestArenaAttackIntegration:
    """Show that sci-council composes cleanly with arena-attack-problem's
    workspace layout. Stage 2 of the arena pipeline spawns the 5 recon
    agents via the Agent tool; sci-council's caller-argument path is the
    same plumbing pattern."""

    def test_caller_protocol_matches_arena_pattern(self, tmp_path):
        """arena-attack-problem writes agent outputs to
        {workspace}/literature/, {workspace}/recon/, etc. sci-council writes
        to {workspace}/council/. Both follow the same request-response
        file-exchange protocol, so the same orchestration script can drive
        either. This test documents the invariant."""
        ws = tmp_path / "campaign"
        ws.mkdir()

        # sci-council
        council_caller = build_file_exchange_caller(ws)

        # Pre-populate so we don't block
        (ws / "council" / "responses").mkdir(parents=True, exist_ok=True)
        for p in ("Gauss", "Erdős", "Tao"):
            (ws / "council" / "responses" / f"{p}.txt").write_text(
                _persona_response(p)
            )

        synthesis = run_council("integration", caller=council_caller,
                                 timeout_sec=10.0)
        assert "Council Synthesis" in synthesis

        # Assert both the sci-council request dir and the arena-style
        # recon/ layout can coexist in the same workspace.
        (ws / "recon").mkdir(exist_ok=True)
        (ws / "literature").mkdir(exist_ok=True)
        assert (ws / "council" / "requests").is_dir()
        assert (ws / "recon").is_dir()
        assert (ws / "literature").is_dir()
