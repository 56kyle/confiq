"""Unit tests pinning the Stage 6 async resolver shell (`confiq._resolve`).

Covers resolve_async and the color-bearing fetch helpers (_fetch_all_async,
_fetch_one_async). The async shell shares the color-agnostic core with resolve()
(ADR 0035); only fetch differs by color, so these tests concentrate on the fetch
seam: concurrency, order/precedence preservation, inline sync handling, dual-source
color preference, and the neither-color refusal. End-to-end load_async behaviour is
pinned in the integration suite.

No async test plugin is configured; async coroutines are driven with asyncio.run()
inside sync tests, mirroring tests/unit_tests/test_context.py (ADR 0013, no thread bridge).
"""

from __future__ import annotations

import asyncio
import copy
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from confiq import MemorySource
from confiq import SchemalessConfig
from confiq._resolve import _fetch_one_async
from confiq._resolve import resolve_async
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError


if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


_SLEEP_SECONDS = 0.05


class DbConfig(BaseModel):
    host: str
    port: int


class SinglePort(BaseModel):
    port: int


class _AsyncMemorySource:
    """Genuinely async, async-only in-memory source: fetch_async only, no fetch (ADR 0047).

    confiq ships no AsyncSource; this is the test-local driver for the async path. It
    deep-copies on fetch so neither caller nor input can corrupt the source, matching
    MemorySource's contract.
    """

    def __init__(
        self,
        data: Mapping[str, Any],
        *,
        name: str = "async-memory",
        profile: str | None = None,
    ) -> None:
        self._data: dict[str, Any] = copy.deepcopy(dict(data))
        self.name = name
        self.profile = profile

    async def fetch_async(self) -> Mapping[str, Any]:
        return copy.deepcopy(self._data)


class _SleepingAsyncSource:
    """Async-only source that awaits before returning, so concurrent gather is observable."""

    def __init__(
        self,
        data: Mapping[str, Any],
        *,
        name: str = "sleeping",
        delay: float = _SLEEP_SECONDS,
        profile: str | None = None,
    ) -> None:
        self._data: dict[str, Any] = copy.deepcopy(dict(data))
        self._delay = delay
        self.name = name
        self.profile = profile

    async def fetch_async(self) -> Mapping[str, Any]:
        await asyncio.sleep(self._delay)
        return copy.deepcopy(self._data)


class _RendezvousAsyncSource:
    """Async-only source that signals its own start then blocks until a peer has started.

    Proves concurrent gather deterministically, with no wall-clock timing: fetch_async
    sets its `started` event, then awaits `peer_started`. Cross-wire two of these and both
    only ever return if the resolver awaits their fetch_async coroutines concurrently; a
    serial gather would deadlock on the first source's wait for a peer that never runs.
    """

    def __init__(
        self,
        data: Mapping[str, Any],
        *,
        started: asyncio.Event,
        peer_started: asyncio.Event,
        name: str = "rendezvous",
        profile: str | None = None,
    ) -> None:
        self._data: dict[str, Any] = copy.deepcopy(dict(data))
        self._started = started
        self._peer_started = peer_started
        self.name = name
        self.profile = profile

    async def fetch_async(self) -> Mapping[str, Any]:
        self._started.set()
        await self._peer_started.wait()
        return copy.deepcopy(self._data)


class _DualSource:
    """Source implementing both colors, returning different data per color to prove preference."""

    def __init__(
        self,
        *,
        sync_data: Mapping[str, Any],
        async_data: Mapping[str, Any],
        name: str = "dual",
        profile: str | None = None,
    ) -> None:
        self._sync_data: dict[str, Any] = copy.deepcopy(dict(sync_data))
        self._async_data: dict[str, Any] = copy.deepcopy(dict(async_data))
        self.name = name
        self.profile = profile

    def fetch(self) -> Mapping[str, Any]:
        return copy.deepcopy(self._sync_data)

    async def fetch_async(self) -> Mapping[str, Any]:
        return copy.deepcopy(self._async_data)


class _NeitherSource:
    """Object satisfying only the base Source protocol: neither fetch nor fetch_async."""

    def __init__(self, name: str = "neither", profile: str | None = None) -> None:
        self.name = name
        self.profile = profile


def test_resolve_async_with_async_only_source_resolves_to_validated_instance() -> None:
    source = _AsyncMemorySource({"port": 8080})

    result = asyncio.run(resolve_async(SinglePort, [source]))

    assert isinstance(result, SinglePort)
    assert result.port == 8080


def test_resolve_async_with_sync_source_runs_inline_and_resolves() -> None:
    result = asyncio.run(resolve_async(SinglePort, [MemorySource({"port": 8080})]))

    assert isinstance(result, SinglePort)
    assert result.port == 8080


def test_resolve_async_gathers_sources_concurrently() -> None:
    async def _drive() -> DbConfig | SchemalessConfig:
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        sources = [
            _RendezvousAsyncSource(
                {"host": "a"}, started=first_started, peer_started=second_started, name="first"
            ),
            _RendezvousAsyncSource(
                {"port": 1}, started=second_started, peer_started=first_started, name="second"
            ),
        ]
        return await asyncio.wait_for(resolve_async(DbConfig, sources), timeout=5.0)

    result = asyncio.run(_drive())

    assert isinstance(result, DbConfig)
    assert result.host == "a"
    assert result.port == 1


def test_resolve_async_lets_later_listed_source_win_even_when_it_completes_first() -> None:
    early_slow = _SleepingAsyncSource({"port": 1}, name="early-slow", delay=_SLEEP_SECONDS)
    late_fast = _SleepingAsyncSource({"port": 2}, name="late-fast", delay=0.0)

    result = asyncio.run(resolve_async(SinglePort, [early_slow, late_fast]))

    assert isinstance(result, SinglePort)
    assert result.port == 2


def test_resolve_async_with_async_earlier_sync_later_lets_sync_win() -> None:
    async_early = _AsyncMemorySource({"port": 1}, name="async-early")
    sync_late = MemorySource({"port": 2}, name="sync-late")

    result = asyncio.run(resolve_async(SinglePort, [async_early, sync_late]))

    assert isinstance(result, SinglePort)
    assert result.port == 2


def test_resolve_async_with_sync_earlier_async_later_lets_async_win() -> None:
    sync_early = MemorySource({"port": 1}, name="sync-early")
    async_late = _AsyncMemorySource({"port": 2}, name="async-late")

    result = asyncio.run(resolve_async(SinglePort, [sync_early, async_late]))

    assert isinstance(result, SinglePort)
    assert result.port == 2


def test_resolve_async_with_invalid_field_names_winning_source_in_provenance() -> None:
    source = _AsyncMemorySource({"host": "localhost", "port": "not-a-port"}, name="vault")

    with pytest.raises(ConfigValidationError) as exc_info:
        asyncio.run(resolve_async(DbConfig, [source]))

    error = exc_info.value
    assert error.field_path == "port"
    assert error.sources == ("vault",)


def test__fetch_one_async_with_async_only_source_awaits_fetch_async() -> None:
    entry = asyncio.run(_fetch_one_async(_AsyncMemorySource({"port": 8080}, name="async")))

    assert entry.source.name == "async"
    assert entry.data == {"port": 8080}


def test__fetch_one_async_with_sync_only_source_calls_fetch_inline() -> None:
    entry = asyncio.run(_fetch_one_async(MemorySource({"port": 8080}, name="sync")))

    assert entry.source.name == "sync"
    assert entry.data == {"port": 8080}


def test__fetch_one_async_with_dual_source_prefers_fetch_async() -> None:
    source = _DualSource(sync_data={"color": "sync"}, async_data={"color": "async"})

    entry = asyncio.run(_fetch_one_async(source))

    assert entry.data == {"color": "async"}


def test__fetch_one_async_with_neither_color_raises_confiq_error_naming_source() -> None:
    with pytest.raises(ConfiqError) as exc_info:
        asyncio.run(_fetch_one_async(_NeitherSource(name="broken")))

    assert "broken" in str(exc_info.value)
