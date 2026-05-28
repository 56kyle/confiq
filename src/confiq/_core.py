"""Core Config class: the public API for layered, schema-validated configuration."""

from __future__ import annotations

import contextvars
import copy
import threading
import warnings
from contextlib import contextmanager
from types import MappingProxyType
from typing import Any
from typing import Callable
from typing import Generic
from typing import Iterator
from typing import TypeVar

from confiq._hookspecs import hookimpl
from confiq._locks import ReentrancyGuard
from confiq._merge import _freeze
from confiq._merge import deep_merge
from confiq._plugins import _make_plugin_manager
from confiq._plugins import _register_optional_loaders
from confiq._snapshot import ConfigSnapshot
from confiq.sources.argparse_source import ArgparseSource
from confiq.sources.defaults import DefaultsSource
from confiq.sources.dict_source import DictSource
from confiq.sources.env import EnvSource
from confiq.sources.file import FileSource


T = TypeVar("T")

_MISSING = object()


class _OnReloadAdapter:
    def __init__(self, fn: Callable[[Any, Any], None]) -> None:
        self._fn = fn

    @hookimpl
    def confiq_on_reload(self, old_model: Any, new_model: Any) -> None:
        self._fn(old_model, new_model)


class Config(Generic[T]):
    """The one Config to rule them all. Import as `from confiq import config`.

    See docs/design.md §4.5 and ADR 0001.
    """

    def __init__(self) -> None:
        self._sources: list[Any] = []
        self._schema: type[T] | None = None
        self._adapter: Any = None
        self._lock = threading.Lock()
        self._reentry = ReentrancyGuard()
        self._current: ConfigSnapshot[T] = ConfigSnapshot(
            model=None,
            raw=MappingProxyType({}),
            version=0,
            sources=(),
        )
        self._plugin_manager = _make_plugin_manager()
        _register_optional_loaders(self._plugin_manager)
        self._frozen = False
        # Per-instance ContextVar so multiple Config() objects don't share override
        # state. See ADR 0001.
        self._override_var: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
            f"confiq_override_{id(self)}", default=None
        )

    # ─── public read API (LOCK-FREE) ─────────────────────────────────────────

    def get(
        self,
        dotted: str | None = None,
        default: Any = _MISSING,
        *,
        cast: Any = None,
    ) -> Any:
        """Dotted-path read from the current snapshot; lock-free.

        Applies `cast` to the leaf if given. Raises `KeyError` when the path is absent
        and no default is provided. An active `override()` context takes precedence for
        the requested key. Returns the full model when `dotted` is None.
        """
        snap = self._current  # single LOAD_ATTR — lock-free per ADR 0001
        override = self._override_var.get()
        if override is not None and dotted:
            try:
                node: Any = override
                for part in dotted.split("."):
                    node = node[part]
                return cast(node) if cast else node
            except (KeyError, TypeError):
                pass
        if dotted is None:
            return snap.model
        if default is _MISSING:
            return snap.get(dotted, cast=cast)
        return snap.get(dotted, default, cast=cast)

    def snapshot(self) -> ConfigSnapshot[T]:
        """Return the current `ConfigSnapshot`; no lock needed."""
        return self._current

    # ─── fluent registration API
    def bind(self, schema: type[T]) -> Config[T]:
        """Set the schema type and adapter, then rebuild immediately.

        Raises `TypeError` if no registered adapter recognises the schema. Returns `self`.
        """
        with self._lock, self._reentry:
            self._assert_unfrozen()
            self._schema = schema
            self._adapter = self._plugin_manager.hook.confiq_get_schema_adapter(schema=schema)
            if self._adapter is None:
                raise TypeError(f"No registered adapter handles {schema!r}")
            self._rebuild_locked()
        return self  # type: ignore[return-value]

    def add_source(self, src: Any) -> Config[T]:
        """Append the source, re-sort by priority, rebuild, and attach a watch when `src.watch_enabled` is true. Returns `self`."""
        with self._lock, self._reentry:
            self._assert_unfrozen()
            self._sources.append(src)
            self._sources.sort(key=lambda s: s.priority)
            self._rebuild_locked()
            self._maybe_attach_watch(src)
        return self

    def reprioritize_sources(self, key: Callable[[Any], Any]) -> Config[T]:
        """Re-sort the source list in-place using `key`, then rebuild. Returns `self`."""
        with self._lock, self._reentry:
            self._assert_unfrozen()
            self._sources.sort(key=key)
            self._rebuild_locked()
        return self

    def add_file(
        self,
        path: Any,
        *,
        required: bool = True,
        watch: bool = False,
        file_format: str | None = None,
        priority: int | None = None,
    ) -> Config[T]:
        """Convenience wrapper around `FileSource`.

        `required=False` silently returns `{}` when the file is absent; `watch=True`
        attaches a filesystem watcher. Returns `self`.
        """
        return self.add_source(
            FileSource(
                path,
                required=required,
                watch=watch,
                file_format=file_format,
                priority=priority,
                plugin_manager=self._plugin_manager,
            )
        )

    def add_dict(
        self,
        data: dict[str, Any],
        *,
        priority: int | None = None,
    ) -> Config[T]:
        """Wrap `data` in a `DictSource`; canonical primitive for tests and inline defaults. Returns `self`."""
        return self.add_source(DictSource(data, priority=priority))

    def add_env(
        self,
        *,
        prefix: str = "",
        delimiter: str = "__",
        dotenv: Any = None,
        priority: int | None = None,
    ) -> Config[T]:
        """Wrap `EnvSource`.

        `delimiter` (default `__`) splits env-var names into nested keys; when `dotenv`
        is set its values are merged under the live environment, with live env winning.
        Returns `self`.
        """
        return self.add_source(EnvSource(prefix=prefix, delimiter=delimiter, dotenv=dotenv, priority=priority))

    def add_argparse(
        self,
        namespace: Any = None,
        *,
        argv: list[str] | None = None,
        priority: int | None = None,
    ) -> Config[T]:
        """Wrap `ArgparseSource`.

        Pass a parsed `argparse.Namespace` or a raw `argv` list using `--key.sub=value`
        dot syntax; defaults to `sys.argv[1:]` when both are None. Returns `self`.
        """
        return self.add_source(ArgparseSource(namespace=namespace, argv=argv, priority=priority))

    def add_defaults_from_schema(self) -> Config[T]:
        """Add a `DefaultsSource` backed by the bound schema adapter as the lowest-priority layer. Returns `self`."""
        return self.add_source(DefaultsSource(self._adapter))

    def add_click(
        self,
        ctx_or_params: Any,
        *,
        delimiter: str = "__",
        priority: int | None = None,
    ) -> Config[T]:
        """Wrap `ClickSource`; integrates Click command parameters at CLI priority. Returns `self`."""
        from confiq.sources.click_source import ClickSource

        return self.add_source(ClickSource(ctx_or_params, delimiter=delimiter, priority=priority))

    def add_typer(
        self,
        params: dict[str, Any],
        *,
        delimiter: str = "__",
        priority: int | None = None,
    ) -> Config[T]:
        """Wrap `TyperSource`; integrates Typer command locals at CLI priority. Returns `self`."""
        from confiq.sources.typer_source import TyperSource

        return self.add_source(TyperSource(params, delimiter=delimiter, priority=priority))

    # ─── plugin / subscriber API

    def register_plugin(self, plugin: Any, name: str | None = None) -> None:
        """Register a pluggy plugin with this config's plugin manager."""
        self._plugin_manager.register(plugin, name=name)

    def unregister_plugin(self, plugin_or_name: Any) -> None:
        """Unregister a plugin by object or name."""
        self._plugin_manager.unregister(plugin_or_name)

    def on_reload(self, fn: Callable[[Any, Any], None]) -> Callable[[Any, Any], None]:
        """Decorator: register a free function as an on_reload hookimpl."""
        self._plugin_manager.register(_OnReloadAdapter(fn), name=f"on_reload:{fn.__qualname__}")
        return fn

    def reload(self) -> ConfigSnapshot[T]:
        """Force a full rebuild under the write lock. Returns the new `ConfigSnapshot`."""
        with self._lock, self._reentry:
            return self._rebuild_locked()
        raise RuntimeError("Failed to rebuild a new ConfigSnapshot.")

    @contextmanager
    def override(self, **patches: Any) -> Iterator[Config[T]]:
        """contextvars-based per-task override; safe for asyncio and threads."""
        prev: dict[str, Any] | None = self._override_var.get()
        new: dict[str, Any] = deep_merge(copy.deepcopy(prev) if prev else {}, patches)
        token: contextvars.Token[dict[str, Any] | None] = self._override_var.set(new)
        try:
            yield self
        finally:
            self._override_var.reset(token)

    def freeze(self) -> Config[T]:
        """Mark this instance immutable; subsequent mutating calls raise `RuntimeError`. Returns `self`."""
        self._frozen = True
        return self

    # ─── internals (lock is held) ─────────────────────────────────────────────

    def _rebuild_locked(self) -> ConfigSnapshot[T]:
        old: ConfigSnapshot[T] = self._current
        merged: dict[str, Any] = {}
        sources_used: list[str] = []
        for src in self._sources:
            self._plugin_manager.hook.confiq_before_load(source=src)
            merged = deep_merge(merged, src.load())
            sources_used.append(src.protocol)

        transformed: dict[str, Any] | None = self._plugin_manager.hook.confiq_after_merge(merged=merged)
        if transformed is not None:
            merged = transformed

        model = self._adapter.validate(merged) if self._adapter is not None else None
        new_snap: ConfigSnapshot[T] = ConfigSnapshot(
            model=model,
            raw=_freeze(merged),  # type: ignore[arg-type]
            version=old.version + 1,
            sources=tuple(sources_used),
        )

        self._plugin_manager.hook.confiq_before_publish(old_snapshot=old, new_snapshot=new_snap)
        self._current = new_snap  # atomic reference swap — ADR 0001
        self._enqueue_notify(old.model, new_snap.model)
        return new_snap

    def _enqueue_notify(self, old_model: Any, new_model: Any) -> None:
        def _run() -> None:
            try:
                self._plugin_manager.hook.confiq_on_reload(old_model=old_model, new_model=new_model)
            except Exception as exc:

                warnings.warn(
                    f"confiq: on_reload hook raised {type(exc).__name__}: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )

        threading.Thread(target=_run, daemon=True, name="confiq-notify").start()

    def _assert_unfrozen(self) -> None:
        if self._frozen:
            raise RuntimeError("This Config instance is frozen. Construct a fresh Config() for mutation.")

    def _maybe_attach_watch(self, src: Any) -> None:
        if not getattr(src, "watch_enabled", False):
            return
        if not src.supports_watch():
            return
        src.watch(self.reload)
