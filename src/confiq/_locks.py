"""Module containing threading primitives used throughout the confiq package."""
from __future__ import annotations

import threading
from types import TracebackType

from typing_extensions import Self


_REENTRY_MESSAGE = (
    "reload is already in progress on this handle: a reload subscriber triggered another reload, "
    "or a concurrent reload was attempted from another thread/task. Reloads must not overlap or be "
    "re-entered."
)


class ReentrancyGuard:
    """Reentrant-safe guard that fast-fails if a reload triggers another reload.

    Used as a context manager around the ConfigHandle reload body. Raises
    RuntimeError on reentrant acquisition rather than deadlocking.

    A plain non-reentrant lock cannot distinguish reentry from genuine
    cross-thread contention; both surface as the same RuntimeError. This is
    acceptable under the infrequent, deliberate reload contract (design_d §9.2).
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()

    def __enter__(self) -> Self:
        if not self._lock.acquire(blocking=False):
            raise RuntimeError(_REENTRY_MESSAGE)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._lock.release()
