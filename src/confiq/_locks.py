"""Per-thread reentrancy guard that fast-fails instead of deadlocking."""

from __future__ import annotations

import threading


class ReentrancyGuard:
    """Per-thread fast-fail: raise on re-entry rather than deadlock.

    Modeled on loguru's _protected_lock (loguru/_handler.py). See ADR 0001.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def __enter__(self) -> ReentrancyGuard:
        if getattr(self._local, "in_use", False):
            raise RuntimeError(
                "confiq: re-entered the config write lock from the same thread "
                "(deadlock avoided). A hookimpl or subscriber tried to mutate "
                "config synchronously. Move that work off the notification thread."
            )
        self._local.in_use = True
        return self

    def __exit__(self, *exc: object) -> bool:
        self._local.in_use = False
        return False
