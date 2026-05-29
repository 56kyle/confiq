"""Module containing the ReentrancyGuard threading primitive used throughout the confiq package."""
from __future__ import annotations

import threading
from types import TracebackType


_REENTRANCY_ERROR = (
    "confiq: re-entered the config write lock from the same thread (deadlock avoided). "
    "A hookimpl or subscriber tried to trigger reload synchronously. "
    "Move that work to a separate thread or schedule it on the event loop."
)


class ReentrancyGuard:
    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._owner_ident: int | None = None

    def __enter__(self) -> ReentrancyGuard:
        current_ident: int = threading.current_thread().ident  # type: ignore[assignment]
        if self._owner_ident == current_ident:
            raise RuntimeError(_REENTRANCY_ERROR)
        self._lock.acquire()
        self._owner_ident = current_ident
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._owner_ident = None
        self._lock.release()
