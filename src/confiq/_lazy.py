"""Module defining LazyConfig, the opt-in lazy proxy for ambient config access."""
from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from typing import Any
from typing import Generic
from typing import NoReturn
from typing import cast

from pydantic import TypeAdapter
from pydantic import ValidationError

from confiq._hookspecs import make_plugin_manager
from confiq._hookspecs import resolve_schema_adapter
from confiq._load import ResolutionSpec
from confiq._load import load
from confiq._merge import FetchedEntry
from confiq._merge import merge_sources
from confiq._types import T
from confiq.adapter._schema_adapter import SchemaAdapter
from confiq.context import current_override
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ErrorContext
from confiq.exceptions import join_loc
from confiq.source._source import SyncSource


_NOT_BOUND_MESSAGE = (
    "LazyConfig is not bound: call bind() before dereferencing config, or enter a "
    "context.override(...) scope."
)
_BASE_SOURCE_NAME = "base"
_OVERRIDE_SOURCE_NAME = "override"


class _UnboundConfigError(AttributeError):
    """Raised on dereference of an unbound LazyConfig proxy (design_d §8.4).

    Subclasses AttributeError so that hasattr()/getattr()-with-default probes on an
    unbound proxy degrade normally, while a direct value read still raises loudly.
    """


class LazyConfig(Generic[T]):
    """Opt-in lazy proxy for ambient config access (design_d §8.4).

    Usage::

        # myapp/config.py
        config_handle = LazyConfig(settings_spec)
        config = config_handle.value   # typed as T; import this everywhere

        # myapp/__main__.py
        config_handle.bind(cli=TyperSource())

    ``value`` is a stable proxy object: it forwards every attribute to the
    wrapped config value, but first checks context.current_override() so that
    pytest-confiq's override() context manager flows through it transparently.

    ``bind``, ``reset``, and ``bound`` live on the handle, not the proxy, to
    avoid shadowing schema fields of the same names.
    """

    def __init__(
        self,
        spec_builder: Callable[..., ResolutionSpec[T]],
    ) -> None:
        self._spec_builder: Callable[..., ResolutionSpec[T]] = spec_builder
        self._base: T | None = None
        self._adapter: SchemaAdapter[Any] | None = None
        self._base_mapping: dict[str, Any] = {}
        self._cache: dict[int, tuple[Mapping[str, Any], T]] = {}
        self._proxy: _LazyProxy[T] = _LazyProxy(self)

    @property
    def value(self) -> T:
        """The lazy proxy, typed as the schema.

        Never raises: the "not bound" error surfaces on proxy dereference, so
        ``config = handle.value`` at import time is always safe.
        """
        return cast("T", self._proxy)

    def bind(self, *, cli: SyncSource | None = None) -> None:
        """Resolve the base config value once, post-CLI-parse.

        Calls spec_builder(cli=cli) to build the ResolutionSpec, then runs
        load() to produce the base snapshot stored in the handle. The load runs
        before any state mutation, so a failed bind leaves prior state intact.

        Raises ConfigValidationError (via load) if the base config is invalid,
        and SchemaError if no adapter claims the schema.
        """
        spec = self._spec_builder(cli=cli)
        base = load(spec)
        manager = make_plugin_manager(spec.plugins)
        adapter = resolve_schema_adapter(manager, spec.schema)
        mapping = cast("dict[str, Any]", TypeAdapter(spec.schema).dump_python(base))
        self._adapter = adapter
        self._base_mapping = mapping
        self._cache.clear()
        self._base = base

    def reset(self) -> None:
        """Clear the bound base value (used by pytest-confiq between tests)."""
        self._base = None
        self._adapter = None
        self._base_mapping = {}
        self._cache.clear()

    @property
    def bound(self) -> bool:
        """True after bind() has been called and before reset() clears it."""
        return self._base is not None

    def _require_base(self) -> T:
        """Return the bound base, or refuse with the not-bound remediation (design_d §8.4)."""
        if self._base is None:
            raise _UnboundConfigError(_NOT_BOUND_MESSAGE)
        return self._base

    def _peek_base(self) -> T | None:
        """Return the bound base or None, never raising (for __class__/__repr__ support)."""
        return self._base

    def _snapshot_for(self, override: Mapping[str, Any]) -> T:
        """Return the validated base+override snapshot, memoised per override identity (ADR 0031).

        Keyed by id(override) with a stored-identity re-check to close the id-recycle hazard.
        Production never populates this cache (overrides are test-scoped, so the base fast-path
        is taken); reset()/bind() clear it.
        """
        key = id(override)
        cached = self._cache.get(key)
        if cached is not None and cached[0] is override:
            return cached[1]
        snapshot = self._validate_overlay(override)
        self._cache[key] = (override, snapshot)
        return snapshot

    def _validate_overlay(self, override: Mapping[str, Any]) -> T:
        """Merge the override over the base mapping and validate it as one more source (ADR 0031).

        The override is the highest-precedence source (base low, override high). Validation
        failures are translated to ConfigValidationError naming ("override",), mirroring
        _resolve._validate.
        """
        adapter = self._adapter
        if adapter is None:
            raise _UnboundConfigError(_NOT_BOUND_MESSAGE)
        merged = merge_sources(
            [
                FetchedEntry(_BASE_SOURCE_NAME, self._base_mapping),
                FetchedEntry(_OVERRIDE_SOURCE_NAME, dict(override)),
            ],
        ).merged
        try:
            return cast("T", adapter.validate(merged))
        except ValidationError as exc:
            contexts = tuple(
                ErrorContext(field_path=join_loc(detail["loc"]), sources=(_OVERRIDE_SOURCE_NAME,))
                for detail in exc.errors()
            )
            raise ConfigValidationError(contexts, original=exc) from exc


class _LazyProxy(Generic[T]):
    """Internal proxy object returned by LazyConfig.value.

    Forwards every attribute access to the wrapped config value after checking
    context.current_override(). isinstance() works via __class__ forwarding.
    The same proxy instance is returned on every LazyConfig.value access so
    ``from myapp.config import config`` stays a stable reference.
    """

    def __init__(self, handle: LazyConfig[T]) -> None:
        self._handle: LazyConfig[T] = handle

    def __setattr__(self, name: str, value: object) -> None:
        if name == "_handle":
            super().__setattr__(name, value)
            return
        raise AttributeError("the config proxy is read-only; it forwards reads to the bound config value")

    def __deepcopy__(self, memo: dict[int, Any]) -> NoReturn:
        raise TypeError("LazyConfig proxy is not copyable; copy config_handle.value's target instead")

    def __copy__(self) -> NoReturn:
        raise TypeError("LazyConfig proxy is not copyable; copy config_handle.value's target instead")

    def __getattr__(self, name: str) -> Any:  # pyright: ignore[reportAny]  # transparent proxy: forwards to the Any-typed wrapped value
        handle = self._handle
        override = current_override()
        target = handle._require_base() if override is None else handle._snapshot_for(override)  # noqa: SLF001  # proxy is the handle's intimate same-module collaborator
        return getattr(target, name)  # pyright: ignore[reportAny]  # transparent proxy: wrapped value is Any-typed

    @property
    def __class__(self) -> type:  # pyright: ignore[reportIncompatibleMethodOverride]  # transparent proxy: isinstance forwards to the wrapped type
        """Forward isinstance() checks to the wrapped value's class."""
        base = self._handle._peek_base()  # noqa: SLF001  # proxy is the handle's intimate same-module collaborator
        return type(base) if base is not None else _LazyProxy

    def __repr__(self) -> str:
        base = self._handle._peek_base()  # noqa: SLF001  # proxy is the handle's intimate same-module collaborator
        if base is None:
            return "<LazyConfig value: unbound>"
        return f"<LazyConfig value: bound to {type(base).__name__}>"
