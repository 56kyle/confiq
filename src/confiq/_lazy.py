"""Module defining LazyConfig, the opt-in lazy proxy for ambient config access."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any
from typing import Generic

from confiq._load import ResolutionSpec
from confiq._types import T
from confiq.source._source import Source


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
    ) -> None: ...

    @property
    def value(self) -> T:
        """The lazy proxy, typed as the schema.

        Raises RuntimeError (with a clear "not bound" message) if accessed
        before bind() has been called and no context.override() is active.
        """
        ...

    def bind(self, *, cli: Source | None = None) -> None:
        """Resolve the base config value once, post-CLI-parse.

        Calls spec_builder(cli=cli) to build the ResolutionSpec, then runs
        load() to produce the base snapshot stored in the handle.
        """
        ...

    def reset(self) -> None:
        """Clear the bound base value (used by pytest-confiq between tests)."""
        ...

    @property
    def bound(self) -> bool:
        """True after bind() has been called and before reset() clears it."""
        ...


class _LazyProxy(Generic[T]):
    """Internal proxy object returned by LazyConfig.value.

    Forwards every attribute access to the wrapped config value after checking
    context.current_override(). isinstance() works via __class__ forwarding.
    The same proxy instance is returned on every LazyConfig.value access so
    ``from myapp.config import config`` stays a stable reference.
    """

    def __init__(self, handle: LazyConfig[T]) -> None: ...

    def __getattr__(self, name: str) -> Any: ...

    @property
    def __class__(self) -> type:  # type: ignore[override]
        """Forward isinstance() checks to the wrapped value's class."""
        ...

    def __repr__(self) -> str: ...
