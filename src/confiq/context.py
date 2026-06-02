"""Module containing the per-task config override context manager used throughout the confiq package."""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Generator


_override_var: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "confiq_override", default=None
)


def get_override() -> dict[str, Any] | None:
    """Return the active override dict for the current task, or None."""
    return _override_var.get()


@contextmanager
def override(**patches: Any) -> Generator[None, None, None]:
    """Context manager that installs a per-task config overlay via ContextVar."""
    token: contextvars.Token[dict[str, Any] | None] = _override_var.set(patches)
    try:
        yield
    finally:
        _override_var.reset(token)
