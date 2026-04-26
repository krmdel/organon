"""Claude-backed SEARCH/REPLACE diff mutator (Upgrade U6/3).

Follows the OpenEvolve / AlphaEvolve contract: the parent program carries
``# EVOLVE-BLOCK-START`` / ``# EVOLVE-BLOCK-END`` markers delimiting the
region the LLM is allowed to mutate. The mutator sends the parent +
problem context to Claude, asks for one or more SEARCH/REPLACE blocks, and
applies them to produce a child program.

SEARCH/REPLACE format::

    <<<<<<< SEARCH
    old code (must appear verbatim in an EVOLVE block)
    =======
    new code (what to swap in)
    >>>>>>> REPLACE

Multiple blocks may appear in one response; they apply in order. If any
SEARCH doesn't match verbatim, the whole response is rejected and the
mutator falls back.

Fallback cascade (four paths, matching seed_generator.generate_opro_proposals):

1. ``ANTHROPIC_API_KEY`` missing → identity mutation (return parent code
   unchanged, ``metadata.fallback_reason = 'no_api_key'``).
2. Rate-limit hit (``LLMCallLimiter`` raises or times out) → identity +
   ``fallback_reason = 'rate_limited'``.
3. Parse error (no SEARCH/REPLACE blocks found, or a SEARCH doesn't match
   verbatim) → identity + ``fallback_reason = 'parse_error'``.
4. Any other exception (SDK error, empty response, JSON malformed in
   metadata sidecar) → identity + ``fallback_reason = 'exception'``.

This makes the mutator safe to fan out via ``parallel_runner``: the worst
case is a null mutation that wastes one evaluation, not a crash.

Test hooks: all LLM calls go through ``client.messages.create`` so tests
inject a ``_StubClient`` with a hand-written reply. See
``tests/test_mutator.py``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..rate_limiter import LLMCallLimiter, get_default_limiter


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


EVOLVE_BLOCK_START = "# EVOLVE-BLOCK-START"
EVOLVE_BLOCK_END = "# EVOLVE-BLOCK-END"

_BLOCK_PATTERN = re.compile(
    r"<<<<<<<\s*SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>>\s*REPLACE",
    re.DOTALL,
)

MUTATOR_SYSTEM_PROMPT = """You are an arena evolutionary mutator. You are given
a parent program that constructs a candidate solution to a math optimization
problem, a brief problem description, and a history of prior scores. You
propose ONE mutation to the parent's EVOLVE block.

Output ONLY SEARCH/REPLACE blocks in the format:

<<<<<<< SEARCH
old code (must appear verbatim inside an EVOLVE block in the parent)
=======
new code
>>>>>>> REPLACE

Rules:

1. You MUST NOT modify anything outside the EVOLVE-BLOCK-START / EVOLVE-BLOCK-END
   markers. The SEARCH text must appear within one of those blocks.
2. You MAY emit multiple SEARCH/REPLACE blocks; they apply in order.
3. No prose, no markdown, no JSON — only the SEARCH/REPLACE blocks.
4. Prefer small, principled edits (swap one primitive for another, retune
   one numerical parameter, add one structural twist) over large rewrites.
5. Preserve all imports and function signatures the outer harness depends on.
"""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DiffBlock:
    """One SEARCH/REPLACE block."""

    search: str
    replace: str


@dataclass
class MutationResult:
    """Output of one mutation attempt."""

    child_code: str
    fallback_reason: Optional[str] = None
    n_diff_blocks: int = 0
    raw_response: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_code": self.child_code,
            "fallback_reason": self.fallback_reason,
            "n_diff_blocks": self.n_diff_blocks,
            "raw_response": self.raw_response,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_diff_blocks(text: str) -> list[DiffBlock]:
    """Extract all SEARCH/REPLACE blocks from a model response.

    Trailing and leading whitespace inside each half is preserved; the
    caller uses the raw text for verbatim matching against the parent.
    """
    matches = _BLOCK_PATTERN.findall(text)
    return [DiffBlock(search=s, replace=r) for s, r in matches]


def find_evolve_blocks(code: str) -> list[tuple[int, int]]:
    """Return (start, end) character offsets of every EVOLVE block body in
    ``code``. The body excludes the marker lines themselves."""
    lines = code.splitlines(keepends=True)
    offsets: list[tuple[int, int]] = []
    cursor = 0
    start = None
    for line in lines:
        stripped = line.strip()
        if stripped == EVOLVE_BLOCK_START:
            start = cursor + len(line)
        elif stripped == EVOLVE_BLOCK_END and start is not None:
            offsets.append((start, cursor))
            start = None
        cursor += len(line)
    return offsets


def _is_within_evolve_block(code: str, position: int, length: int) -> bool:
    for s, e in find_evolve_blocks(code):
        if s <= position and position + length <= e:
            return True
    return False


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def apply_diff_blocks(parent_code: str, blocks: list[DiffBlock]) -> Optional[str]:
    """Apply blocks in order, returning the new code or None on mismatch.

    A mismatch means either:
    - a SEARCH text does not appear verbatim in the current code, OR
    - the matched position lies outside every EVOLVE block.

    Both are hard rejections — the mutator falls back to identity in either
    case.
    """
    if not blocks:
        return None
    code = parent_code
    for block in blocks:
        idx = code.find(block.search)
        if idx == -1:
            return None
        if not _is_within_evolve_block(code, idx, len(block.search)):
            return None
        code = code[:idx] + block.replace + code[idx + len(block.search):]
    return code


# ---------------------------------------------------------------------------
# Mutator orchestration
# ---------------------------------------------------------------------------


def mutate(
    *,
    parent_code: str,
    problem_context: str,
    history_summary: str = "",
    limiter: Optional[LLMCallLimiter] = None,
    client: Any = None,
    max_tokens: int = 2000,
    temperature: float = 0.8,
) -> MutationResult:
    """Request one mutation. Returns identity on any fallback path.

    Args:
        parent_code: full parent program (must contain at least one EVOLVE
            block; if none, fallback fires with reason 'no_evolve_block').
        problem_context: short problem description + scoring direction.
        history_summary: optional prior-score summary to ground the mutation.
        limiter: rate limiter; defaults to the process-wide singleton.
        client: Anthropic client or stub. Tests inject ``_StubClient``.
        max_tokens / temperature: standard LLM knobs.
    """
    if not find_evolve_blocks(parent_code):
        return MutationResult(
            child_code=parent_code,
            fallback_reason="no_evolve_block",
            metadata={"note": "parent missing EVOLVE-BLOCK markers"},
        )

    client = client if client is not None else _build_default_claude_client()
    if client is None:
        return MutationResult(
            child_code=parent_code, fallback_reason="no_api_key"
        )

    limiter = limiter or get_default_limiter()
    try:
        acquired = limiter.acquire()
        if not acquired:
            return MutationResult(
                child_code=parent_code, fallback_reason="rate_limited"
            )
    except RuntimeError:
        return MutationResult(
            child_code=parent_code, fallback_reason="rate_limited"
        )

    user_prompt = _build_user_prompt(parent_code, problem_context, history_summary)

    try:
        reply = client.messages.create(
            model=os.environ.get("ORGANON_CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=max_tokens,
            temperature=temperature,
            system=MUTATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = reply.content[0].text
    except Exception as e:  # noqa: BLE001 — caller wants a universal fallback
        return MutationResult(
            child_code=parent_code,
            fallback_reason="exception",
            metadata={"error": type(e).__name__, "message": str(e)},
        )

    blocks = parse_diff_blocks(text)
    if not blocks:
        return MutationResult(
            child_code=parent_code,
            fallback_reason="parse_error",
            raw_response=text,
            metadata={"note": "no SEARCH/REPLACE blocks in response"},
        )

    child = apply_diff_blocks(parent_code, blocks)
    if child is None:
        return MutationResult(
            child_code=parent_code,
            fallback_reason="parse_error",
            n_diff_blocks=len(blocks),
            raw_response=text,
            metadata={"note": "a SEARCH didn't match or fell outside EVOLVE block"},
        )

    return MutationResult(
        child_code=child,
        n_diff_blocks=len(blocks),
        raw_response=text,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_user_prompt(parent_code: str, context: str, history: str) -> str:
    parts = [
        f"problem_context:\n{context}",
    ]
    if history:
        parts.append(f"\nhistory_summary:\n{history}")
    parts.append(
        "\nparent_program (propose a mutation to any EVOLVE block; emit only "
        "SEARCH/REPLACE blocks):\n\n" + parent_code
    )
    return "\n".join(parts)


def _build_default_claude_client() -> Any:
    """Anthropic client or None if SDK/key missing. Isolated for easy stub."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # type: ignore

        return anthropic.Anthropic()
    except Exception:
        return None
