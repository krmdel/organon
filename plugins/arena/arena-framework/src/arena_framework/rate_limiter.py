"""LLM call-rate limiter — guards against runaway async fan-out spend.

Used by ``seed_generator.opro_propose`` and the MAP-Elites mutator (Upgrade U6)
when they would otherwise issue uncapped LLM calls.

Sliding-window token bucket: allow at most ``calls_per_window`` in any rolling
``window_s``-second interval. Blocks the caller if the budget is exceeded;
raises ``RuntimeError`` if the configured hard-cap is hit.

Thread-safe (uses a mutex). Process-safe via file lock when ``state_path`` is
supplied — this is the right choice when multiple parallel_runner children
each make LLM calls: the lock file guarantees global cap enforcement.
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from pathlib import Path
from threading import Lock
from typing import Optional


class LLMCallLimiter:
    """Sliding-window + optional persistent lock-file rate limit.

    Args:
        calls_per_window: max LLM calls per ``window_s`` seconds (e.g. 60/60
            for "60 calls per minute").
        window_s: window duration in seconds.
        hard_cap: if set, raises ``RuntimeError`` when total calls hit this.
            Use as a session-wide safety net; None disables.
        state_path: if given, state persists at this path across processes.
    """

    def __init__(
        self,
        *,
        calls_per_window: int = 60,
        window_s: float = 60.0,
        hard_cap: Optional[int] = None,
        state_path: Optional[Path] = None,
    ) -> None:
        self.calls_per_window = calls_per_window
        self.window_s = window_s
        self.hard_cap = hard_cap
        self.state_path = Path(state_path) if state_path else None
        self._lock = Lock()
        self._calls: deque[float] = deque()
        self._total = 0
        if self.state_path:
            self._load_state()

    def _load_state(self) -> None:
        if not self.state_path or not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text())
            for t in data.get("calls", []):
                self._calls.append(float(t))
            self._total = int(data.get("total", 0))
        except (OSError, json.JSONDecodeError):
            pass

    def _persist(self) -> None:
        if not self.state_path:
            return
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps({"calls": list(self._calls), "total": self._total})
            )
        except OSError:
            pass

    def _trim(self, now: float) -> None:
        cutoff = now - self.window_s
        while self._calls and self._calls[0] < cutoff:
            self._calls.popleft()

    def acquire(self, *, block: bool = True, timeout_s: float = 600.0) -> bool:
        """Reserve a call slot. Returns True on success, False if non-blocking
        and cap is hit. Raises ``RuntimeError`` if ``hard_cap`` is exceeded.
        """
        t_deadline = time.monotonic() + timeout_s
        while True:
            with self._lock:
                now = time.monotonic()
                self._trim(now)
                if self.hard_cap is not None and self._total >= self.hard_cap:
                    raise RuntimeError(
                        f"LLMCallLimiter hard_cap ({self.hard_cap}) reached"
                    )
                if len(self._calls) < self.calls_per_window:
                    self._calls.append(now)
                    self._total += 1
                    self._persist()
                    return True
                if not block:
                    return False
                # How long until the oldest call ages out?
                oldest = self._calls[0]
                wait = max(0.01, oldest + self.window_s - now)
            if time.monotonic() + wait > t_deadline:
                return False
            time.sleep(wait)

    @property
    def total_calls(self) -> int:
        with self._lock:
            return self._total

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()
            self._total = 0
            if self.state_path and self.state_path.exists():
                try:
                    self.state_path.unlink()
                except OSError:
                    pass


# Module-level singleton for simple call sites.
_default_limiter: Optional[LLMCallLimiter] = None


def get_default_limiter() -> LLMCallLimiter:
    """Lazy-init process-wide limiter (60 calls/min, no hard cap).

    For testing, callers can monkeypatch ``_default_limiter`` directly.
    """
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = LLMCallLimiter()
    return _default_limiter


def set_default_limiter(limiter: LLMCallLimiter) -> None:
    """Install a custom limiter (used by tests + attack_loops that need a
    tighter cap for an individual run)."""
    global _default_limiter
    _default_limiter = limiter
