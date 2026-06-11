"""Module containing custom types used throughout the confiq package."""

import enum
from collections.abc import Mapping
from typing import Any
from typing import TypeAlias
from typing import TypeVar


T = TypeVar("T")


# (str, Enum) mixin instead of enum.StrEnum: identical semantics, Python 3.10 compatible (StrEnum added in 3.11)
class MergeMode(str, enum.Enum):
    OVERRIDE = "override"
    FILL = "fill"


Provenance: TypeAlias = Mapping[str, str]
FieldAnnotations: TypeAlias = Mapping[str, list[Any]]
PluginList: TypeAlias = tuple[object, ...]
