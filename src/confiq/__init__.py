"""confiq — typed configuration from an ordered list of sources."""
from __future__ import annotations

from typing import TYPE_CHECKING

from confiq import context
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError
from confiq.exceptions import MissingConfigError
from confiq.exceptions import SchemaError
from confiq.exceptions import ErrorContext
from confiq.exceptions import SourceError
from confiq._merge import FetchedEntry
from confiq._types import FieldAnnotations
from confiq._types import MergeMode
from confiq._types import PluginList
from confiq._types import Provenance
from confiq._field import ConfigField
from confiq._hookspecs import hookimpl
from confiq._lazy import LazyConfig
from confiq._load import ResolutionSpec
from confiq._load import load
from confiq._load import load_async
from confiq._schemaless import SchemalessConfig
from confiq.cli._bind import ConfigBind
from confiq.source._argparse import ArgparseSource
from confiq.source._env import EnvSource
from confiq.source._file import FileSource
from confiq.source._memory import MemorySource


if TYPE_CHECKING:
    from confiq._handle import ConfigHandle

try:
    from confiq._handle import ConfigHandle as ConfigHandle  # noqa: F401
except ImportError:
    pass

__all__: list[str] = [
    # errors
    "ConfiqError",
    "ConfigValidationError",
    "ErrorContext",
    "MissingConfigError",
    "SchemaError",
    "SourceError",
    # field metadata
    "ConfigField",
    # loading
    "ResolutionSpec",
    "load",
    "load_async",
    # lifecycle
    "ConfigHandle",  # requires confiq[reload]
    "LazyConfig",
    # CLI
    "ConfigBind",
    # schemaless
    "SchemalessConfig",
    # context override
    "context",
    # sources
    "ArgparseSource",
    "EnvSource",
    "FileSource",
    "MemorySource",
    # plugin system
    "hookimpl",
    # types
    "MergeMode",
    "FetchedEntry",
    "Provenance",
    "FieldAnnotations",
    "PluginList",
]
