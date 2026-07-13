"""Module containing ContextVar-based scoped configuration overrides.

The sole core reader is the LazyConfig proxy (Stage 8); load() never consults
this overlay (ADR 0028).
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from collections.abc import Generator
from collections.abc import Mapping
from contextlib import asynccontextmanager
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


_OVERRIDE_VAR: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "_confiq_override", default=None
)


@contextmanager
def override(data: Mapping[str, Any]) -> Generator[None, None, None]:
    """Scope a data overlay for the LazyConfig proxy; an inner override replaces the outer (ADR 0028)."""
    token = _OVERRIDE_VAR.set(data)
    try:
        yield
    finally:
        _OVERRIDE_VAR.reset(token)


@asynccontextmanager
async def async_override(data: Mapping[str, Any]) -> AsyncGenerator[None, None]:
    """Async counterpart of override(); the ContextVar propagates within the task across await."""
    token = _OVERRIDE_VAR.set(data)
    try:
        yield
    finally:
        _OVERRIDE_VAR.reset(token)


def current_override() -> Mapping[str, Any] | None:
    """Return the override in scope, read only by the LazyConfig proxy (ADR 0028)."""
    return _OVERRIDE_VAR.get()
