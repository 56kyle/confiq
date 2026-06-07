"""Module containing ContextVar-based scoped configuration overrides."""
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
def override(data: Mapping[str, Any]) -> Generator[None, None, None]: ...


@asynccontextmanager
async def async_override(data: Mapping[str, Any]) -> AsyncGenerator[None, None]: ...


def current_override() -> Mapping[str, Any] | None: ...
