from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pluggy

hookspec = pluggy.HookspecMarker("confiq")
hookimpl = pluggy.HookimplMarker("confiq")

if TYPE_CHECKING:
    from confiq._snapshot import ConfigSnapshot
    from confiq.sources.base import ConfigSource


class ConfiqSpecs:
    """Hook contract that third parties (and built-ins) implement."""

    @hookspec(firstresult=True)
    def confiq_load_file(self, path: Path, suffix: str) -> dict[str, Any] | None:
        """Load a file; return its contents as a dict, or None for unhandled suffixes."""

    @hookspec(firstresult=True)
    def confiq_get_schema_adapter(self, schema: type) -> Any | None:
        """Return a SchemaAdapter for this schema type, or None if unrecognised."""

    @hookspec
    def confiq_before_load(self, source: ConfigSource) -> None:
        """Called before each source's load() during a rebuild."""

    @hookspec(firstresult=True)
    def confiq_after_merge(self, merged: dict[str, Any]) -> dict[str, Any] | None:
        """Called once with the fully-merged dict before schema validation.

        Return a transformed dict to replace the merged value, or None to pass.
        The highest-priority registered impl wins (firstresult). Register with
        tryfirst=True to take priority over other plugins. See ADR 0003.
        """

    @hookspec
    def confiq_before_publish(
        self,
        old_snapshot: ConfigSnapshot,  # type: ignore[type-arg]
        new_snapshot: ConfigSnapshot,  # type: ignore[type-arg]
    ) -> None:
        """Called under the write lock just before the atomic swap; raise to abort."""

    @hookspec
    def confiq_on_reload(self, old_model: Any, new_model: Any) -> None:
        """Called on the daemon notification thread after a successful publish."""
