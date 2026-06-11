"""Subpackage defining configuration sources used throughout the confiq package."""
from __future__ import annotations

from confiq.source._argparse import ArgparseSource
from confiq.source._base_source import BaseSource
from confiq.source._click import ClickSource
from confiq.source._dotenv import DotenvSource
from confiq.source._env import EnvSource
from confiq.source._file import FileSource
from confiq.source._memory import MemorySource
from confiq.source._source import AsyncSource
from confiq.source._source import Source
from confiq.source._source import SyncSource
from confiq.source._typer import TyperSource


__all__: list[str] = [
    "AsyncSource",
    "ArgparseSource",
    "BaseSource",
    "ClickSource",
    "DotenvSource",
    "EnvSource",
    "FileSource",
    "MemorySource",
    "Source",
    "SyncSource",
    "TyperSource",
]
