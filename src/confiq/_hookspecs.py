"""Module containing pluggy hookspec definitions and the SchemaAdapter protocol used throughout the confiq package."""
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol

import pluggy


if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from confiq.exceptions import ConfiqError

hookspec = pluggy.HookspecMarker("confiq")
hookimpl = pluggy.HookimplMarker("confiq")


class SchemaAdapter(Protocol):
    """Adapts a schema class to confiq's resolver interface."""

    def field_hints(self) -> Mapping[str, object]:
        """Return field name to annotated type mapping, including Annotated wrappers."""
        ...

    def validate(self, data: dict[str, Any]) -> object:
        """Validate and coerce the merged data dict into the schema type."""
        ...


class ConfiqSpecs:
    """Pluggy hookspec definitions for the confiq plugin system."""

    @hookspec(firstresult=True)
    def confiq_load_file(self, path: Path) -> dict[str, Any] | None:
        """Load a file; return its dict, or None to pass to the next handler."""

    @hookspec(firstresult=True)
    def confiq_get_schema_adapter(self, schema: type) -> SchemaAdapter | None:
        """Return a SchemaAdapter for this schema type, or None if unrecognized."""

    @hookspec
    def confiq_pre_load(self, schema: type, sources: list[Any]) -> None:
        """Called before resolution begins with a shallow copy of the sources list.

        Mutations affect only this load call.
        """

    @hookspec
    def confiq_post_load(self, config: object) -> None:
        """Called after a successful load. Config is frozen; read-only."""

    @hookspec
    def confiq_on_reload(self, old: object, new: object) -> None:
        """Called after ConfigHandle reload. Runs on daemon thread outside the lock."""

    @hookspec
    def confiq_on_error(self, error: ConfiqError) -> None:
        """Called when load() fails. Plugin may log or record metrics; not for recovery."""
