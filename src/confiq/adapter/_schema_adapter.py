"""Module defining a base for configuration field schema adapters."""
from typing import Any
from typing import Mapping

from typing_extensions import Protocol
from typing_extensions import runtime_checkable

from confiq._types import FieldAnnotations
from confiq._types import T


@runtime_checkable
class SchemaAdapter(Protocol[T]):
    """Defines an adapter for converting a configuration field into a given type."""

    def field_metadata(self) -> FieldAnnotations:
        """Returns a mapping containing the Annotated metadata for this field."""
        ...

    def validate(self, data: Mapping[str, Any]) -> T:
        """Validates the given data and coerces it into an instance of its declared type."""
        ...
