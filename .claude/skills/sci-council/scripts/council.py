"""sci-council — 3-persona research fan-out.

Spawns three persona sub-agents (Gauss / Erdős / Tao by default) in parallel
against the same problem statement, then synthesises their 3×3 proposals into
one ranked markdown table with consensus flags.

Public API:
    run_council(problem, personas=None, timeout_sec=None) -> str
    synthesize_responses(responses: dict[str, str]) -> str
    parse_persona_response(raw: str) -> dict
    CouncilAllFailedError

Testing contract: monkey-patch `_call_persona(persona_name, problem)` to stub
persona responses. See tests/test_council.py.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from statistics import median_low
from typing import Iterable


DEFAULT_PERSONAS = ("Gauss", "Erdős", "Tao")

EFFORT_PENALTY = {"low": 1.0, "medium": 1.5, "high": 2.5}

CONSENSUS_FLAG = {1: "1/3", 2: "2/3", 3: "3/3"}
CONSENSUS_EMOJI = {1: "🟢", 2: "🟡", 3: "🔴"}


class CouncilAllFailedError(RuntimeError):
    """Raised when every persona fails to return a usable response."""


@dataclass
class Approach:
    name: str
    rationale: str
    ref: str
    p_beats: list[float] = field(default_factory=list)
    efforts: list[str] = field(default_factory=list)
    personas: list[str] = field(default_factory=list)

    @property
    def mean_p_beat(self) -> float:
        return sum(self.p_beats) / len(self.p_beats) if self.p_beats else 0.0

    @property
    def effort_median(self) -> str:
        if not self.efforts:
            return "medium"
        order = ("low", "medium", "high")
        sorted_efforts = sorted(self.efforts, key=order.index)
        return median_low(sorted_efforts) if len(sorted_efforts) > 0 else "medium"

    @property
    def composite_score(self) -> float:
        penalty = EFFORT_PENALTY.get(self.effort_median, 1.5)
        return self.mean_p_beat / penalty


# --------------------------------------------------------------------------
# Persona invocation hook — patched by tests, replaced in production by an
# Agent-tool call that spawns a real LLM persona sub-agent.
# --------------------------------------------------------------------------

PersonaCaller = "Callable[[str, str], str]"  # (persona_name, problem) -> raw response


def _call_persona(persona_name: str, problem: str) -> str:
    """Default stub. Production usage either (a) monkey-patches this with a real
    sub-agent call, or (b) passes `caller=` to `run_council` to bypass this
    stub entirely. The `caller=` path is preferred for new code because it
    avoids mutating module-level state."""
    raise NotImplementedError(
        "_call_persona is a patch point. In tests, use "
        "unittest.mock.patch('council._call_persona', side_effect=...). "
        "In production, either replace with an Agent tool invocation, OR pass "
        "caller=<callable> to run_council() — the caller-argument path is "
        "thread-safe across concurrent council runs. See "
        "sci-council/references/agent-tool-invocation.md for the real-Agent pattern."
    )


def build_file_exchange_caller(workspace):
    """Build a persona caller that uses a file-exchange protocol for real Agent
    invocations.

    Pattern (driven by Claude, not this script):
      1. `run_council(problem, caller=build_file_exchange_caller(ws))` writes
         `{ws}/council/requests/{persona}.txt` with the problem statement.
      2. The caller blocks (with a generous timeout) on the existence of
         `{ws}/council/responses/{persona}.txt`.
      3. Between steps 1 and 2, Claude (the parent agent) spawns one `Agent`
         tool call per persona with `subagent_type` matching the persona (or
         a prompt hand-crafted per `references/personas.md`). Each sub-agent
         writes its raw response string to
         `{ws}/council/responses/{persona}.txt`.
      4. As each response file appears, this caller reads it and returns it.

    Returns a callable matching the `PersonaCaller` signature.
    """
    import pathlib
    import time

    ws = pathlib.Path(workspace)
    req_dir = ws / "council" / "requests"
    res_dir = ws / "council" / "responses"
    req_dir.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)

    def _caller(persona_name: str, problem: str) -> str:
        req = req_dir / f"{persona_name}.txt"
        res = res_dir / f"{persona_name}.txt"
        req.write_text(problem)
        deadline = time.monotonic() + 600  # 10 min cap per persona
        while time.monotonic() < deadline:
            if res.is_file():
                return res.read_text()
            time.sleep(0.25)
        raise TimeoutError(
            f"persona {persona_name!r}: no response file at {res} within 600s"
        )

    return _caller


# --------------------------------------------------------------------------
# Parser — converts a raw persona response string into an approaches dict.
# --------------------------------------------------------------------------

_APPROACH_RE = re.compile(
    r"""^\s*\d+\.\s*
        (?P<name>[^|]+?)
        \s*\|\s*P\(BEAT\):\s*(?P<p>[0-9.]+)
        \s*\|\s*EFFORT:\s*(?P<effort>low|medium|high)
        \s*\|\s*REF:\s*(?P<ref>[^\n]+)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def parse_persona_response(raw: str) -> dict:
    """Parse a raw persona response into {approaches, dead_ends, confidence}."""
    if not isinstance(raw, str) or "APPROACHES:" not in raw:
        return {"error": "missing APPROACHES: block", "approaches": [], "dead_ends": "", "confidence": None}

    # Isolate the APPROACHES block from DEAD_ENDS / CONFIDENCE sections.
    # Each approach line ends with a REF: token; the line immediately after may
    # be a "Rationale:" continuation we pair up.
    approaches: list[dict] = []
    lines = raw.splitlines()
    i = 0
    in_approaches = False
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("APPROACHES:"):
            in_approaches = True
            i += 1
            continue
        if line.strip().startswith(("DEAD_ENDS:", "CONFIDENCE:")):
            in_approaches = False
        if in_approaches:
            m = _APPROACH_RE.match(line)
            if m:
                rationale = ""
                j = i + 1
                while j < len(lines):
                    nxt = lines[j].strip()
                    if nxt.lower().startswith("rationale:"):
                        rationale = nxt.split(":", 1)[1].strip()
                        break
                    if nxt == "" or _APPROACH_RE.match(lines[j]) or nxt.startswith(("DEAD_ENDS:", "CONFIDENCE:")):
                        break
                    j += 1
                approaches.append({
                    "name": m.group("name").strip(),
                    "p_beat": float(m.group("p")),
                    "effort": m.group("effort").strip().lower(),
                    "ref": m.group("ref").strip(),
                    "rationale": rationale,
                })
        i += 1

    dead_ends_match = re.search(r"DEAD_ENDS:\s*(.*?)(?:\n\s*CONFIDENCE:|$)", raw, re.DOTALL)
    dead_ends = dead_ends_match.group(1).strip() if dead_ends_match else ""

    conf_match = re.search(r"CONFIDENCE:\s*([0-9.]+)", raw)
    confidence = float(conf_match.group(1)) if conf_match else None

    return {"approaches": approaches, "dead_ends": dead_ends, "confidence": confidence}


# --------------------------------------------------------------------------
# Synthesis — union, dedupe, score, rank, render.
# --------------------------------------------------------------------------

_NAME_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_name(name: str) -> str:
    """Canonicalise approach names for dedup. Lowercase + collapse non-alnum to '-'."""
    slug = _NAME_NORMALIZE_RE.sub("-", name.lower()).strip("-")
    return slug


def synthesize_responses(responses: dict[str, str]) -> str:
    """Union approaches from all persona responses, dedupe, rank, render markdown."""
    parsed: dict[str, dict] = {}
    parse_errors: list[str] = []
    for persona, raw in responses.items():
        p = parse_persona_response(raw)
        if p.get("error") or not p.get("approaches"):
            parse_errors.append(persona)
            continue
        parsed[persona] = p

    # Union → dedupe by normalized name
    merged: dict[str, Approach] = {}
    # Iterate personas in deterministic order (as provided).
    for persona in responses.keys():
        if persona not in parsed:
            continue
        for a in parsed[persona]["approaches"]:
            key = _normalize_name(a["name"])
            if key not in merged:
                merged[key] = Approach(
                    name=a["name"].strip(),
                    rationale=a["rationale"],
                    ref=a["ref"],
                )
            merged[key].p_beats.append(a["p_beat"])
            merged[key].efforts.append(a["effort"])
            if persona not in merged[key].personas:
                merged[key].personas.append(persona)

    ranked = sorted(
        merged.values(),
        key=lambda a: (-a.composite_score, _normalize_name(a.name)),
    )

    confidences = [parsed[p]["confidence"] for p in parsed if parsed[p].get("confidence") is not None]
    mean_conf = sum(confidences) / len(confidences) if confidences else None

    # Dead ends — collect per-persona, flag any technique named by ≥ 2 personas.
    dead_ends: dict[str, list[str]] = {}
    for persona, p in parsed.items():
        if not p.get("dead_ends"):
            continue
        for piece in re.split(r";|\n", p["dead_ends"]):
            piece = piece.strip()
            if not piece or piece.lower() == "none":
                continue
            key = _normalize_name(piece.split("—")[0] if "—" in piece else piece[:40])
            dead_ends.setdefault(key, []).append(f"{persona}: {piece}")
    consensus_dead = [v for v in dead_ends.values() if len(v) >= 2]

    total_personas = len(parsed)

    # ---- Render ----
    lines: list[str] = []
    header = "## Council Synthesis"
    degraded_notes: list[str] = []
    expected_personas = set(responses.keys())
    live_personas = set(parsed.keys())
    missing = sorted(expected_personas - live_personas)
    if missing:
        missing_label = ", ".join(missing)
        if total_personas == 0:
            degraded_notes.append(f"[ALL PERSONAS FAILED]")
        elif total_personas == 1:
            degraded_notes.append(f"[SINGLE-PERSPECTIVE ANALYSIS — 2 personas unavailable: {missing_label}]")
        else:
            degraded_notes.append(
                f"[WARNING: {missing_label} unavailable — 2-of-3 perspectives (single failure)]"
            )
    lines.append(header)
    for note in degraded_notes:
        lines.append(note)
    lines.append("")

    lines.append("### Ranked Approaches")
    lines.append("| Rank | Approach | Composite Score | Consensus | Effort | Mean P(BEAT) | Who proposes |")
    lines.append("|------|----------|-----------------|-----------|--------|--------------|-------------|")
    for idx, a in enumerate(ranked, start=1):
        consensus_n = len(a.personas)
        flag = CONSENSUS_FLAG.get(consensus_n, f"{consensus_n}/?")
        emoji = CONSENSUS_EMOJI.get(consensus_n, "")
        consensus_cell = f"{emoji} {flag}".strip()
        lines.append(
            f"| {idx} | {a.name} | {a.composite_score:.3f} | {consensus_cell} | "
            f"{a.effort_median} | {a.mean_p_beat:.2f} | {', '.join(a.personas)} |"
        )
    lines.append("")

    if consensus_dead:
        lines.append("### Dead Ends (consensus ≥ 2/3)")
        for bucket in consensus_dead:
            lines.append(f"- {bucket[0]}")
        lines.append("")

    if mean_conf is not None:
        lines.append("### Council Confidence")
        lines.append(f"Mean: {mean_conf:.2f} across {len(confidences)} persona(s).")
        lines.append("")

    if parse_errors:
        lines.append("### Parse Errors")
        for p in parse_errors:
            lines.append(f"- {p}: response unparseable; persona treated as unavailable.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------
# Orchestrator — fan out 3 personas, collect with per-future timeout, synthesise.
# --------------------------------------------------------------------------

def run_council(
    problem: str,
    personas: Iterable[str] | None = None,
    timeout_sec: float | None = None,
    *,
    caller=None,
) -> str:
    """Fan out to N personas in parallel and synthesise their proposals.

    Args:
        problem: the problem statement (non-empty str).
        personas: list of persona names to fan out to; defaults to Gauss/Erdős/Tao.
        timeout_sec: per-run wall-clock cap; None = no cap.
        caller: optional `PersonaCaller` that overrides the module-level
            `_call_persona`. Useful for production wiring without mutating
            module state — e.g. `caller=build_file_exchange_caller(workspace)`
            for the real-Agent pattern. Also useful for tests that want to
            exercise the run_council path explicitly without patching.
    """
    if not isinstance(problem, str) or not problem.strip():
        raise ValueError("problem statement must be a non-empty string")

    persona_list = list(personas) if personas else list(DEFAULT_PERSONAS)
    if not persona_list:
        raise ValueError("personas list cannot be empty")

    invoke = caller if caller is not None else _call_persona

    # Daemon threads — the timeout contract requires that a blocked persona
    # does NOT prevent the call from returning, and must NOT hold pytest
    # open. ThreadPoolExecutor threads are non-daemon and keep the process
    # alive; daemon threads get killed when the process exits cleanly.
    responses: dict[str, str] = {}
    failures: dict[str, str] = {}
    results_lock = threading.Lock()
    done_event = threading.Event()
    done_count = [0]  # list-wrap for closure mutation

    def runner(persona: str):
        try:
            r = invoke(persona, problem)
            with results_lock:
                responses[persona] = r
        except Exception as exc:
            with results_lock:
                failures[persona] = f"{type(exc).__name__}: {exc}"
        finally:
            with results_lock:
                done_count[0] += 1
                if done_count[0] >= len(persona_list):
                    done_event.set()

    threads = []
    for p in persona_list:
        t = threading.Thread(target=runner, args=(p,), daemon=True, name=f"council-{p}")
        t.start()
        threads.append(t)

    # Wait until all personas finish OR the timeout elapses.
    done_event.wait(timeout=timeout_sec)

    # Any personas still running at this point are lagging — record as
    # timeout-failed and leave their threads running in the background.
    with results_lock:
        for p in persona_list:
            if p not in responses and p not in failures:
                failures[p] = "TimeoutError: per-persona wall-clock exceeded"

    if not responses:
        reasons = ", ".join(f"{p}: {r}" for p, r in sorted(failures.items()))
        # Fall back to listing all personas to keep the error msg complete.
        if not reasons:
            reasons = ", ".join(f"{p}: unknown failure" for p in persona_list)
        raise CouncilAllFailedError(f"All personas failed: {reasons}")

    # Add stub responses for failed personas so synthesize_responses can flag them.
    all_responses: dict[str, str] = {p: responses.get(p, "") for p in persona_list}
    return synthesize_responses(all_responses)


if __name__ == "__main__":  # pragma: no cover — CLI demo only
    import argparse
    ap = argparse.ArgumentParser(description="sci-council dry-run (requires _call_persona to be wired).")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--timeout", type=float, default=None)
    args = ap.parse_args()
    print(run_council(args.problem, timeout_sec=args.timeout))
