"""Confiq — a thread-safe, pluggable configuration manager for Python."""

from confiq._core import Config
from confiq._hookspecs import hookimpl
from confiq._registry import MissingDependencyError, create_source, registry
from confiq._snapshot import ConfigSnapshot

config: Config = Config()  # type: ignore[type-arg]

__all__ = [
    "Config",
    "ConfigSnapshot",
    "MissingDependencyError",
    "config",
    "create_source",
    "hookimpl",
    "registry",
]
