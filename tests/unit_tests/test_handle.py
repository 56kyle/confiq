from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel

from confiq._hookspecs import hookimpl
from confiq._load import ConfigHandle
from confiq.sources._memory import MemorySource


class Settings(BaseModel, frozen=True):
    name: str = "initial"


def test_create_returns_config_handle() -> None:
    handle = ConfigHandle.create(Settings, sources=[MemorySource({"name": "hello"})])
    assert isinstance(handle, ConfigHandle)


def test_current_returns_initial_value() -> None:
    handle = ConfigHandle.create(Settings, sources=[MemorySource({"name": "hello"})])
    assert handle.current().name == "hello"


def test_reload_returns_model_instance() -> None:
    handle = ConfigHandle.create(Settings, sources=[MemorySource({"name": "first"})])
    result = handle.reload()
    assert isinstance(result, Settings)


def test_reload_updates_current() -> None:
    handle = ConfigHandle.create(Settings, sources=[MemorySource({"name": "first"})])
    handle.reload()
    assert isinstance(handle.current(), Settings)


def test_on_reload_subscriber_called() -> None:
    handle = ConfigHandle.create(Settings, sources=[MemorySource({"name": "v1"})])
    received: list[tuple[Any, Any]] = []

    @handle.on_reload
    def subscriber(old: Settings, new: Settings) -> None:
        received.append((old, new))

    handle.reload()
    time.sleep(0.1)
    assert len(received) == 1
    assert isinstance(received[0][1], Settings)


def test_on_reload_subscriber_receives_old_and_new() -> None:
    handle = ConfigHandle.create(Settings, sources=[MemorySource({"name": "original"})])
    pairs: list[tuple[Settings, Settings]] = []

    @handle.on_reload
    def subscriber(old: Settings, new: Settings) -> None:
        pairs.append((old, new))

    handle.reload()
    time.sleep(0.1)
    assert len(pairs) == 1
    old, new = pairs[0]
    assert old.name == "original"
    assert isinstance(new, Settings)


def test_reentrancy_raises_runtime_error() -> None:
    """A confiq_post_load hookimpl that calls reload() on the same thread triggers reentrancy."""
    handle_ref: list[ConfigHandle[Settings]] = []
    caught: list[Exception] = []

    class _ReentrantPlugin:
        @hookimpl
        def confiq_post_load(self, config: object) -> None:
            if not handle_ref:
                return
            try:
                handle_ref[0].reload()
            except RuntimeError as exc:
                caught.append(exc)

    handle = ConfigHandle.create(
        Settings,
        sources=[MemorySource({"name": "x"})],
        plugins=[_ReentrantPlugin()],
    )
    handle_ref.append(handle)
    handle.reload()
    assert len(caught) == 1
    assert "confiq" in str(caught[0]).lower() or "re-enter" in str(caught[0]).lower() or "deadlock" in str(caught[0]).lower()
