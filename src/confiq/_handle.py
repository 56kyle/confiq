"""Module defining ConfigHandle for live-reload config management."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any
from typing import Generic

from confiq._load import ResolutionSpec
from confiq._types import T


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
        ...

    @property
    def current(self) -> T:
        """The current configuration snapshot. Lock-free read (§9.1)."""
        ...

    def reload(self) -> T:
        """Recompute the snapshot from the spec, swap it atomically, notify
        sync subscribers inline (§9.2–§9.3).

        Raises RuntimeError (via ReentrancyGuard) if called from within a
        reload subscriber.
        """
        ...

    async def reload_async(self) -> T:
        """Async variant of reload(). Gathers async subscribers on the running
        loop; runs sync subscribers inline (§9.3).
        """
        ...

    def on_reload(
        self,
        fn: Callable[[T, T], Any],
    ) -> Callable[[], None]:
        """Register *fn* as a reload subscriber.

        *fn* receives (old, new). Returns a disconnect callable (§14.3).
        Uses blinker weak-reference semantics.
        """
        ...
