"""Filesystem watcher integration (watchdog) for live config file reloads."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any
from typing import Callable

from confiq._registry import MissingDependencyError


_DEBOUNCE_S = 0.1

Stopper = Callable[[], None]


def watch_path(path: Path, on_change: Callable[[], None]) -> Stopper:
    """Attach a watchdog observer to `path`; call `on_change()` after a 100 ms quiet window.

    Returns a Stopper; calling it tears down the observer cleanly.
    Raises MissingDependencyError when watchdog is not installed (confiq[watch]).
    """
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as exc:
        raise MissingDependencyError(
            "Install confiq[watch] to enable file watching (requires watchdog>=4.0)."
        ) from exc

    class _Handler(FileSystemEventHandler):  # type: ignore[misc]
        def __init__(self) -> None:
            self._timer: threading.Timer | None = None
            self._lock = threading.Lock()

        def _schedule(self) -> None:
            with self._lock:
                if self._timer is not None:
                    self._timer.cancel()
                self._timer = threading.Timer(_DEBOUNCE_S, on_change)
                self._timer.daemon = True
                self._timer.start()

        def on_modified(self, event: Any) -> None:
            if not event.is_directory and Path(event.src_path).resolve() == path.resolve():
                self._schedule()

        def on_created(self, event: Any) -> None:
            # Editors that save via atomic rename (write temp → rename to final)
            if not event.is_directory and Path(event.src_path).resolve() == path.resolve():
                self._schedule()

    observer = Observer()
    handler = _Handler()
    observer.schedule(handler, str(path.parent), recursive=False)
    observer.daemon = True
    observer.start()

    def _stop() -> None:
        observer.stop()
        observer.join(timeout=2.0)

    return _stop
