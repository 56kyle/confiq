"""Module containing custom types used throughout the confiq package."""

from collections.abc import Mapping
from typing import Any
from typing import TypeAlias
from typing import TypeVar


T = TypeVar("T")


Provenance: TypeAlias = Mapping[str, str]
# Keyed by dotted field path — the schema path table key space (ADR 0026).
FieldAnnotations: TypeAlias = Mapping[str, list[Any]]
PluginList: TypeAlias = tuple[object, ...]
