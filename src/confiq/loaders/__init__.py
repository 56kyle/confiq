"""Subpackage containing file format loader implementations used throughout the confiq package."""
from __future__ import annotations

from confiq.loaders._ini import IniLoader
from confiq.loaders._json import JsonLoader
from confiq.loaders._protocol import Loader


def default_loaders() -> list[Loader]:
    loaders: list[Loader] = [JsonLoader(), IniLoader()]
    try:
        from confiq.loaders._yaml import YamlLoader

        loaders.append(YamlLoader())
    except ImportError:
        pass
    try:
        from confiq.loaders._toml import TomlLoader

        loaders.append(TomlLoader())
    except ImportError:
        pass
    return loaders


__all__ = ["IniLoader", "JsonLoader", "Loader", "default_loaders"]
