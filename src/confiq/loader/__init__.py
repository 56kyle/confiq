"""Subpackage for parsing raw bytes into configuration mappings."""
from __future__ import annotations

from confiq.loader._json import JsonLoader
from confiq.loader._loader import Loader
from confiq.loader._registry import default_loaders
from confiq.loader._registry import loader_for_suffix
from confiq.loader._toml import TomlLoader
from confiq.loader._yaml import YamlLoader


__all__: list[str] = [
    "JsonLoader",
    "Loader",
    "TomlLoader",
    "YamlLoader",
    "default_loaders",
    "loader_for_suffix",
]
