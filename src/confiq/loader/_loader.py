"""Module defining the base for loading configuration data from bytes into mappings."""
from typing import Any
from typing import Mapping

from typing_extensions import Protocol
from typing_extensions import runtime_checkable


@runtime_checkable
class Loader(Protocol):
    """Base class for loading configuration data from bytes into mappings."""

    def parse(self, raw: bytes) -> Mapping[str, Any]:
        """Parses the provided bytes into a mapping."""
        ...
