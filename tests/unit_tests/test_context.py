"""Unit tests pinning the Stage 5 scoped-override surface (`confiq.context`).

These pin the ContextVar scoping of override/async_override/current_override, plus
the load() purity property from ADR 0028: load() never consults the overlay.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import BaseModel

from confiq import MemorySource
from confiq import load
from confiq.context import async_override
from confiq.context import current_override
from confiq.context import override


if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


class SinglePort(BaseModel):
    port: int


def test_current_override_is_none_outside_any_scope() -> None:
    assert current_override() is None


def test_override_exposes_the_mapping_within_scope_and_clears_on_exit() -> None:
    with override({"port": 999}):
        assert current_override() == {"port": 999}

    assert current_override() is None


def test_override_nesting_restores_the_outer_mapping_on_inner_exit() -> None:
    with override({"scope": "outer"}):
        assert current_override() == {"scope": "outer"}
        with override({"scope": "inner"}):
            assert current_override() == {"scope": "inner"}
        assert current_override() == {"scope": "outer"}

    assert current_override() is None


def test_async_override_exposes_the_mapping_within_scope_and_clears_on_exit() -> None:
    observed: list[Mapping[str, Any] | None] = []

    async def scenario() -> None:
        async with async_override({"port": 999}):
            observed.append(current_override())

    asyncio.run(scenario())

    assert observed == [{"port": 999}]
    assert current_override() is None


def test_load_ignores_the_active_override() -> None:
    with override({"port": 999}):
        result = load(SinglePort, [MemorySource({"port": 1})])

    assert isinstance(result, SinglePort)
    assert result.port == 1
