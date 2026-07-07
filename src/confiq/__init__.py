"""confiq — typed configuration from an ordered list of sources."""

from __future__ import annotations

from confiq import context
from confiq._cli import ConfigBind
from confiq._cli import options_from
from confiq._field import ConfigField
from confiq._handle import ConfigHandle
from confiq._hookspecs import hookimpl
from confiq._lazy import LazyConfig
from confiq._load import ResolutionSpec
from confiq._load import load
from confiq._load import load_async
from confiq._load import spec_with
from confiq._merge import FetchedEntry
from confiq._schemaless import SchemalessConfig
from confiq._types import FieldAnnotations
from confiq._types import PluginList
from confiq._types import Provenance
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError
from confiq.exceptions import ErrorContext
from confiq.exceptions import MissingConfigError
from confiq.exceptions import SchemaError
from confiq.exceptions import SourceError
from confiq.source._argparse import ArgparseSource
from confiq.source._env import EnvSource
from confiq.source._file import FileSource
from confiq.source._memory import MemorySource


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
    "spec_with",
    # lifecycle
    "ConfigHandle",  # blinker (confiq[reload]) required at construction time
    "LazyConfig",
    # CLI
    "ConfigBind",
    "options_from",
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
    "FetchedEntry",
    "Provenance",
    "FieldAnnotations",
    "PluginList",
]
