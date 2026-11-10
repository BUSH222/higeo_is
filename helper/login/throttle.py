"""Login throttling: lock out an IP or email after too many failed attempts in a row.

In-memory and per-process, which is enough for the single-process deployment this app runs under.
"""

import threading
import time

WINDOW_SECONDS = 15 * 60
MAX_ATTEMPTS = 5

_lock = threading.Lock()
_failed_attempts: dict[str, list[float]] = {}


def _recent_attempts(key: str, now: float) -> list[float]:
    attempts = [attempt for attempt in _failed_attempts.get(key, []) if now - attempt < WINDOW_SECONDS]
    _failed_attempts[key] = attempts
    return attempts


def is_locked_out(key: str) -> bool:
    """Whether this key (an IP address or an email address) has hit the attempt limit recently."""
    with _lock:
        return len(_recent_attempts(key, time.time())) >= MAX_ATTEMPTS


def record_failed_attempt(key: str) -> None:
    with _lock:
        _recent_attempts(key, time.time()).append(time.time())


def clear_attempts(key: str) -> None:
    with _lock:
        _failed_attempts.pop(key, None)


def reset() -> None:
    """Forget every tracked attempt. For tests, so that one test's failures don't lock out another."""
    with _lock:
        _failed_attempts.clear()
