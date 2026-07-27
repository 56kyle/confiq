"""Integration tests pinning the Stage 8 live-reload handle (`confiq.ConfigHandle`).

These drive real load()/load_async() cycles through the assembled resolver. A test-local
mutable source stands in for a live backing store (MemorySource deep-copies at construction,
so it cannot change between reloads); frozen schemas satisfy the immutable-snapshot contract
that the lock-free read depends on (design_d §8-9). Async paths run via asyncio.run inside
sync tests, matching the repo convention (no pytest-asyncio).
"""

from __future__ import annotations

import asyncio
import gc
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass
from typing_extensions import TypedDict

from confiq import ConfigHandle
from confiq import ResolutionSpec
from confiq._handle import _ASYNC_SUBSCRIBER_MESSAGE
from confiq._locks import _REENTRY_MESSAGE
from confiq.exceptions import SchemaError


if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


class FrozenPort(BaseModel):
    model_config = ConfigDict(frozen=True)

    port: int


@dataclass(frozen=True)
class FrozenPortDataclass:
    port: int


class MutablePort(BaseModel):
    port: int


@dataclass
class MutablePortDataclass:
    port: int


@pydantic_dataclass(frozen=True)
class FrozenPortPydanticDataclass:
    port: int


@pydantic_dataclass
class MutablePortPydanticDataclass:
    port: int


class PortTypedDict(TypedDict):
    port: int


class _MutableSource:
    """A live sync source whose fetched data can be reassigned between reloads."""

    def __init__(self, data: Mapping[str, Any], name: str = "mutable") -> None:
        self.data: Mapping[str, Any] = data
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def profile(self) -> str | None:
        return None

    def fetch(self) -> Mapping[str, Any]:
        return dict(self.data)


def _frozen_handle(source: _MutableSource) -> ConfigHandle[FrozenPort]:
    return ConfigHandle(ResolutionSpec(FrozenPort, [source]))


def test_construction_eagerly_loads_a_valid_current_snapshot() -> None:
    handle = _frozen_handle(_MutableSource({"port": 1}))

    assert handle.current.port == 1


def test_reload_swaps_current_to_a_fresh_snapshot_and_returns_it() -> None:
    source = _MutableSource({"port": 1})
    handle = _frozen_handle(source)

    source.data = {"port": 2}
    returned = handle.reload()

    assert returned.port == 2
    assert handle.current.port == 2
    assert returned == handle.current


def test_on_reload_fires_with_the_previous_and_new_snapshots() -> None:
    source = _MutableSource({"port": 1})
    handle = _frozen_handle(source)
    received: list[tuple[FrozenPort, FrozenPort]] = []

    def subscriber(old: FrozenPort, new: FrozenPort) -> None:
        received.append((old, new))

    handle.on_reload(subscriber)
    source.data = {"port": 2}
    handle.reload()

    assert received == [(FrozenPort(port=1), FrozenPort(port=2))]


def test_disconnect_stops_a_subscriber_while_a_sibling_keeps_firing() -> None:
    source = _MutableSource({"port": 1})
    handle = _frozen_handle(source)
    dropped: list[tuple[FrozenPort, FrozenPort]] = []
    kept: list[tuple[FrozenPort, FrozenPort]] = []

    def dropped_subscriber(old: FrozenPort, new: FrozenPort) -> None:
        dropped.append((old, new))

    def kept_subscriber(old: FrozenPort, new: FrozenPort) -> None:
        kept.append((old, new))

    disconnect = handle.on_reload(dropped_subscriber)
    handle.on_reload(kept_subscriber)
    disconnect()
    source.data = {"port": 2}
    handle.reload()

    assert dropped == []
    assert kept == [(FrozenPort(port=1), FrozenPort(port=2))]


def test_reload_skips_a_weakly_collected_subscriber() -> None:
    source = _MutableSource({"port": 1})
    handle = _frozen_handle(source)
    fired: list[tuple[FrozenPort, FrozenPort]] = []

    class _Subscriber:
        def __init__(self, sink: list[tuple[FrozenPort, FrozenPort]]) -> None:
            self.sink = sink

        def on_reload(self, old: FrozenPort, new: FrozenPort) -> None:
            self.sink.append((old, new))

    subscriber = _Subscriber(fired)
    handle.on_reload(subscriber.on_reload)
    del subscriber
    gc.collect()

    source.data = {"port": 2}
    handle.reload()

    assert fired == []


def test_reentrant_sync_subscriber_fast_fails_with_runtime_error() -> None:
    source = _MutableSource({"port": 1})
    handle = _frozen_handle(source)

    def reentrant(old: FrozenPort, new: FrozenPort) -> None:
        _ = handle.reload()

    handle.on_reload(reentrant)
    source.data = {"port": 2}

    with pytest.raises(RuntimeError, match=re.escape(_REENTRY_MESSAGE)):
        handle.reload()


def test_reload_refuses_when_a_live_async_subscriber_is_registered() -> None:
    source = _MutableSource({"port": 1})
    handle = _frozen_handle(source)

    async def _async_subscriber(old: FrozenPort, new: FrozenPort) -> None:
        return None

    handle.on_reload(_async_subscriber)

    with pytest.raises(RuntimeError, match=re.escape(_ASYNC_SUBSCRIBER_MESSAGE)):
        handle.reload()


@pytest.mark.parametrize(
    "schema",
    [MutablePort, MutablePortDataclass, MutablePortPydanticDataclass, PortTypedDict, None],
    ids=[
        "non-frozen-model",
        "non-frozen-dataclass",
        "non-frozen-pydantic-dataclass",
        "typed-dict",
        "schemaless",
    ],
)
def test_construction_refuses_a_non_frozen_schema(schema: type[Any] | None) -> None:
    with pytest.raises(SchemaError):
        ConfigHandle(ResolutionSpec(schema, [_MutableSource({"port": 1})]))


def test_construction_accepts_a_frozen_model() -> None:
    handle: ConfigHandle[FrozenPort] = ConfigHandle(ResolutionSpec(FrozenPort, [_MutableSource({"port": 1})]))

    assert handle.current.port == 1


def test_construction_accepts_a_frozen_dataclass() -> None:
    handle: ConfigHandle[FrozenPortDataclass] = ConfigHandle(
        ResolutionSpec(FrozenPortDataclass, [_MutableSource({"port": 1})]),
    )

    assert handle.current.port == 1


def test_construction_accepts_a_frozen_pydantic_dataclass() -> None:
    handle: ConfigHandle[FrozenPortPydanticDataclass] = ConfigHandle(
        ResolutionSpec(FrozenPortPydanticDataclass, [_MutableSource({"port": 1})]),
    )

    assert handle.current.port == 1


def test_reload_async_swaps_current_and_awaits_an_async_subscriber() -> None:
    source = _MutableSource({"port": 1})
    handle = _frozen_handle(source)
    awaited: list[tuple[FrozenPort, FrozenPort]] = []

    async def _async_subscriber(old: FrozenPort, new: FrozenPort) -> None:
        awaited.append((old, new))

    handle.on_reload(_async_subscriber)

    async def scenario() -> FrozenPort:
        source.data = {"port": 2}
        return await handle.reload_async()

    returned = asyncio.run(scenario())

    assert returned.port == 2
    assert handle.current.port == 2
    assert awaited == [(FrozenPort(port=1), FrozenPort(port=2))]


def test_reload_async_still_fires_sync_subscribers_inline() -> None:
    source = _MutableSource({"port": 1})
    handle = _frozen_handle(source)
    fired: list[tuple[FrozenPort, FrozenPort]] = []

    def subscriber(old: FrozenPort, new: FrozenPort) -> None:
        fired.append((old, new))

    handle.on_reload(subscriber)

    async def scenario() -> None:
        source.data = {"port": 2}
        _ = await handle.reload_async()

    asyncio.run(scenario())

    assert fired == [(FrozenPort(port=1), FrozenPort(port=2))]


def test_reentrant_async_subscriber_fast_fails_with_runtime_error() -> None:
    source = _MutableSource({"port": 1})
    handle = _frozen_handle(source)

    async def _reentrant(old: FrozenPort, new: FrozenPort) -> None:
        _ = await handle.reload_async()

    handle.on_reload(_reentrant)

    async def scenario() -> None:
        source.data = {"port": 2}
        _ = await handle.reload_async()

    with pytest.raises(RuntimeError, match=re.escape(_REENTRY_MESSAGE)):
        asyncio.run(scenario())
