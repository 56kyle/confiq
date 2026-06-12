"""Module defining a base for configuration field schema adapters."""
from typing import Any
from typing import Mapping

from typing_extensions import Protocol
from typing_extensions import runtime_checkable

from confiq._types import FieldAnnotations
from confiq._types import T


@runtime_checkable
class SchemaAdapter(Protocol[T]):
    """Defines an adapter between the resolver and a supported schema kind."""

    def field_metadata(self) -> FieldAnnotations:
        """Returns the schema's path table: dotted path -> Annotated extras (ADR 0026).

        One entry per fixed path reachable from the schema root, recursing through
        nested models, dataclasses, and TypedDicts. Elements of list-of-model fields
        and union branches contribute no per-element paths.
        """
        ...

    def validate(self, data: Mapping[str, Any]) -> T:
        """Validates the given data and coerces it into an instance of its declared type."""
        ...
