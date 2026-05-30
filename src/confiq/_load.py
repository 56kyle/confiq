"""Module containing the load, load_async, and ConfigHandle entrypoints used throughout the confiq package."""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import TypeVar
from typing import overload

from pydantic import ValidationError

from confiq._locks import ReentrancyGuard
from confiq._plugins import _make_plugin_manager
from confiq._resolver import resolve
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError


if TYPE_CHECKING:
    import pluggy

    from confiq._hookspecs import SchemaAdapter
    from confiq._resolver import ResolvedSnapshot
    from confiq.sources._protocol import AsyncSource
    from confiq.sources._protocol import Source


T = TypeVar("T")


class SchemalessConfig(Mapping[str, Any]):
    """Read-only subscript-access result of a schemaless load() call."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data: dict[str, Any] = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


async def _gather_async(
    sources: list[Source | AsyncSource],
) -> list[tuple[str, Any]]:
    results: list[tuple[str, Any]] = []
    for s in sources:
        if asyncio.iscoroutinefunction(getattr(s, "fetch", None)):
            results.append((s.name, await s.fetch()))  # type: ignore[union-attr]
        else:
            results.append((s.name, s.fetch()))  # type: ignore[union-attr]
    return results


def _fetch_sources(
    sources: list[Source | AsyncSource],
) -> list[tuple[str, Any]]:
    has_async: bool = any(
        asyncio.iscoroutinefunction(getattr(s, "fetch", None)) for s in sources
    )
    if has_async:
        def _run_async() -> list[tuple[str, Any]]:
            return asyncio.run(_gather_async(sources))

        exe: ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as exe:
            return exe.submit(_run_async).result()

    return [(s.name, s.fetch()) for s in sources]  # type: ignore[union-attr]


def _resolve_config(
    schema: type[T] | None,
    fetched: list[tuple[str, Any]],
    strict: bool,
    pm: pluggy.PluginManager,
) -> T | SchemalessConfig:
    snapshot: ResolvedSnapshot = resolve(fetched, schema, strict=strict)

    if schema is None:
        return SchemalessConfig(snapshot.merged)

    adapter: SchemaAdapter | None = pm.hook.confiq_get_schema_adapter(schema=schema)
    if adapter is None:
        raise TypeError(f"No schema adapter found for {schema!r}")

    try:
        validated: T = adapter.validate(snapshot.merged)
    except ValidationError as exc:
        raise ConfigValidationError(
            str(exc),
            field_path="",
            source_names=list(snapshot.provenance.values()),
            pydantic_errors=exc.errors(),
        ) from exc

    pm.hook.confiq_post_load(config=validated)
    return validated


@overload
def load(
    schema: type[T],
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = ...,
    strict: bool = ...,
) -> T: ...


@overload
def load(
    schema: None = ...,
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = ...,
    strict: bool = ...,
) -> SchemalessConfig: ...


def load(
    schema: type[T] | None = None,
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = None,
    strict: bool = True,
) -> T | SchemalessConfig:
    pm: pluggy.PluginManager = _make_plugin_manager()
    if plugins is not None:
        for plugin in plugins:
            pm.register(plugin)

    sources_copy: list[Source | AsyncSource] = list(sources)
    pm.hook.confiq_pre_load(schema=schema, sources=sources_copy)

    try:
        fetched: list[tuple[str, Any]] = _fetch_sources(sources_copy)
        return _resolve_config(schema, fetched, strict, pm)
    except ConfiqError as exc:
        pm.hook.confiq_on_error(error=exc)
        raise


async def load_async(
    schema: type[T] | None = None,
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = None,
    strict: bool = True,
) -> T | SchemalessConfig:
    pm: pluggy.PluginManager = _make_plugin_manager()
    if plugins is not None:
        for plugin in plugins:
            pm.register(plugin)

    sources_copy: list[Source | AsyncSource] = list(sources)
    pm.hook.confiq_pre_load(schema=schema, sources=sources_copy)

    try:
        fetched: list[tuple[str, Any]] = await _gather_async(sources_copy)
        return _resolve_config(schema, fetched, strict, pm)
    except ConfiqError as exc:
        pm.hook.confiq_on_error(error=exc)
        raise


def _invoke_subscriber(fn: Callable[[Any, Any], None], old: Any, new: Any) -> None:
    try:
        fn(old, new)
    except Exception:  # noqa: BLE001
        pass


def _notify(
    subscribers: list[Callable[[Any, Any], None]],
    old: Any,
    new: Any,
) -> None:
    fn: Callable[[Any, Any], None]
    for fn in subscribers:
        _invoke_subscriber(fn, old, new)


class ConfigHandle(Generic[T]):
    """Live-reload handle for a typed config value.

    Constructed via ConfigHandle.create(); do not instantiate directly.
    """

    def __init__(
        self,
        schema: type[T],
        sources: list[Source | AsyncSource],
        plugins: list[object] | None,
        initial: T,
    ) -> None:
        self._schema: type[T] = schema
        self._sources: list[Source | AsyncSource] = sources
        self._plugins: list[object] | None = plugins
        self._current: T = initial
        self._guard: ReentrancyGuard = ReentrancyGuard()
        self._async_lock: asyncio.Lock = asyncio.Lock()
        self._subscribers: list[Callable[[T, T], None]] = []

    @classmethod
    def create(
        cls,
        schema: type[T],
        *,
        sources: list[Source | AsyncSource],
        plugins: list[object] | None = None,
    ) -> ConfigHandle[T]:
        initial: T = load(schema, sources=sources, plugins=plugins)
        return cls(schema, list(sources), plugins, initial)

    def current(self) -> T:
        return self._current

    def reload(self) -> T:
        with self._guard:
            new: T = load(self._schema, sources=self._sources, plugins=self._plugins)
            old: T = self._current
            self._current = new

        subscribers: list[Callable[[T, T], None]] = list(self._subscribers)
        threading.Thread(
            target=_notify, args=(subscribers, old, new), daemon=True
        ).start()
        return new

    async def reload_async(self) -> T:
        async with self._async_lock:
            new: T = await load_async(
                self._schema, sources=self._sources, plugins=self._plugins
            )
            old: T = self._current
            self._current = new

        subscribers: list[Callable[[T, T], None]] = list(self._subscribers)
        threading.Thread(
            target=_notify, args=(subscribers, old, new), daemon=True
        ).start()
        return new

    def on_reload(self, fn: Callable[[T, T], None]) -> Callable[[T, T], None]:
        self._subscribers.append(fn)
        return fn
