"""Module containing convenience helpers for loading config from env vars and files used by the confiq package."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import TypeVar
from typing import overload

from confiq._load import SchemalessConfig
from confiq._load import load
from confiq.sources._env import EnvSource
from confiq.sources._file import FileSource


T = TypeVar("T")


@overload
def from_env_and_file(
    schema: type[T],
    *,
    prefix: str = "",
    path: Path | str | None = None,
    required: bool = True,
) -> T: ...


@overload
def from_env_and_file(
    schema: None = None,
    *,
    prefix: str = "",
    path: Path | str | None = None,
    required: bool = True,
) -> SchemalessConfig: ...


def from_env_and_file(
    schema: type[T] | None = None,
    *,
    prefix: str = "",
    path: Path | str | None = None,
    required: bool = True,
) -> T | SchemalessConfig:
    """Load config from an optional file followed by env vars, then validate against schema."""
    sources: list[Any] = []
    if path is not None:
        sources.append(FileSource(path, required=required))
    sources.append(EnvSource(prefix=prefix))
    return load(schema, sources=sources)
