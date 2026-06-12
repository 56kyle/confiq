"""Module containing custom types used throughout the confiq package."""

import enum
from collections.abc import Mapping
from typing import Any
from typing import TypeAlias
from typing import TypeVar


T = TypeVar("T")


# (str, Enum) mixin instead of enum.StrEnum (3.11+) for the 3.10 floor; __str__ is
# reassigned because the mixin would otherwise format as "MergeMode.OVERRIDE" where
# StrEnum yields "override" (ADR 0024, amended).
class MergeMode(str, enum.Enum):
    OVERRIDE = "override"
    FILL = "fill"

    __str__ = str.__str__


Provenance: TypeAlias = Mapping[str, str]
# Keyed by dotted field path — the schema path table key space (ADR 0026).
FieldAnnotations: TypeAlias = Mapping[str, list[Any]]
PluginList: TypeAlias = tuple[object, ...]
