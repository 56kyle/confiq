"""Module defining ConfigHandle for live-reload config management."""
from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Callable
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic

from confiq._imports import import_optional
from confiq._load import ResolutionSpec
from confiq._load import load
from confiq._load import load_async
from confiq._locks import ReentrancyGuard
from confiq._types import T
from confiq.adapter._kinds import is_base_model
from confiq.exceptions import SchemaError


if TYPE_CHECKING:
    from blinker import Signal


_ASYNC_SUBSCRIBER_MESSAGE = (
    "reload() cannot run: an async subscriber is registered on this handle and would be skipped; "
    "drive it with reload_async()."
)


class ConfigHandle(Generic[T]):
    """Holds a ResolutionSpec and recomputes it on reload() (design_d §8.2).

    Requires a frozen schema — the lock-free read guarantee (§9.1) depends on
    each snapshot being immutable. Raises SchemaError on construction if the
    schema is not frozen.

    Ships behind confiq[reload]; blinker is a runtime requirement of this class
    only, not of the core.
    """

    def __init__(self, spec: ResolutionSpec[T]) -> None:
        """Construct a handle from *spec*.

        Raises SchemaError if spec.schema is not a frozen pydantic model or
        frozen dataclass. Raises ImportError if blinker is not installed.
        """
        blinker = import_optional("blinker", extra="reload")
        _require_frozen_schema(spec.schema)
        self._spec: ResolutionSpec[T] = spec
        self._guard: ReentrancyGuard = ReentrancyGuard()
        self._sync_signal: Signal = blinker.Signal()  # pyright: ignore[reportAny]  # optional-dep module attr is Any
        self._async_signal: Signal = blinker.Signal()  # pyright: ignore[reportAny]  # optional-dep module attr is Any
        self._current: T = load(self._spec)

    @property
    def current(self) -> T:
        """The current configuration snapshot. Lock-free read (§9.1)."""
        return self._current

    def reload(self) -> T:
        """Recompute, atomically swap, and notify sync subscribers inline (§9.2–§9.3).

        Raises RuntimeError (via ReentrancyGuard) if called from within a reload
        subscriber, or if a live async subscriber is registered — an async
        subscriber commits the handle to reload_async().

        A failed recompute (load raising ConfigValidationError, MissingConfigError,
        or SchemaError) propagates and leaves current unchanged: the swap runs only
        after a successful load (the §9.2 choke point).
        """
        with self._guard:
            if self._live_async_receivers():
                raise RuntimeError(_ASYNC_SUBSCRIBER_MESSAGE)
            new = load(self._spec)
            old = self._swap(new)
            self._notify_sync(old, new)
            return new

    async def reload_async(self) -> T:
        """Async variant of reload(); awaits async subscribers on the running loop.

        Sync subscribers still run inline (§9.3).
        """
        with self._guard:
            new = await load_async(self._spec)
            old = self._swap(new)
            self._notify_sync(old, new)
            pending = [receiver(old, new) for receiver in self._live_async_receivers()]
            _ = await asyncio.gather(*pending)  # pyright: ignore[reportAny]  # blinker receiver returns an Any coroutine
            return new

    def on_reload(
        self,
        fn: Callable[[T, T], Any],
    ) -> Callable[[], None]:
        """Register *fn* as a reload subscriber.

        *fn* receives (old, new). Returns a disconnect callable (§14.1 #3).
        Uses blinker weak-reference semantics. A coroutine subscriber is routed
        to the async signal and fires only under reload_async().
        """
        signal = self._async_signal if asyncio.iscoroutinefunction(fn) else self._sync_signal
        _ = signal.connect(fn)
        return lambda: signal.disconnect(fn)

    def _swap(self, new: T) -> T:
        """Store *new* as the current snapshot and return the prior one (single-writer atomic ref)."""
        old = self._current
        self._current = new
        return old

    def _notify_sync(self, old: T, new: T) -> None:
        """Invoke every live sync subscriber inline with the positional (old, new) contract.

        Shared by both reload colors so the notification path cannot drift (ADR 0035).
        """
        for receiver in self._sync_signal.receivers_for(self):
            _ = receiver(old, new)  # pyright: ignore[reportAny]  # blinker receiver returns Any

    def _live_async_receivers(self) -> list[Callable[..., Any]]:
        """Return the currently-live async subscribers (weak-dead ones are pruned by blinker)."""
        return list(self._async_signal.receivers_for(self))


def _require_frozen_schema(schema: type[Any] | None) -> None:
    """Refuse a schema whose snapshots would be mutable, naming the frozen remediation (§9.1, §13).

    A frozen pydantic model or frozen dataclass guarantees immutable snapshots for the lock-free
    read. Schemaless and TypedDict configs cannot express frozenness and are refused.
    """
    if schema is None:
        raise SchemaError(
            "ConfigHandle requires a frozen schema; a schemaless config has no immutable snapshot. "
            "Use a frozen pydantic model (model_config = ConfigDict(frozen=True)) or a frozen dataclass.",
        )
    if is_base_model(schema):
        if not schema.model_config.get("frozen", False):
            raise SchemaError(
                f"ConfigHandle requires a frozen schema; {schema.__name__} is not frozen. "
                f"Set model_config = ConfigDict(frozen=True).",
            )
        return
    if dataclasses.is_dataclass(schema):
        params = getattr(schema, "__dataclass_params__", None)
        if not getattr(params, "frozen", False):
            raise SchemaError(
                f"ConfigHandle requires a frozen schema; dataclass {schema.__name__} is not frozen. "
                f"Declare it with @dataclass(frozen=True).",
            )
        return
    raise SchemaError(
        f"ConfigHandle requires a frozen schema; {schema.__name__} cannot express frozenness. "
        f"Use a frozen pydantic model (model_config = ConfigDict(frozen=True)) or a frozen dataclass.",
    )
