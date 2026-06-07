"""Module containing threading primitives used throughout the confiq package."""
from __future__ import annotations

import threading
from types import TracebackType
from typing_extensions import Self


class ReentrancyGuard:
    """Reentrant-safe guard that fast-fails if a reload triggers another reload.

    Used as a context manager around the ConfigHandle reload body. Raises
    RuntimeError on reentrant acquisition rather than deadlocking.
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...
