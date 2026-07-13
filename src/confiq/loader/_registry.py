"""Module mapping file suffixes to loader instances for FileSource dispatch."""

from __future__ import annotations

from confiq.loader._json import JsonLoader
from confiq.loader._loader import Loader
from confiq.loader._toml import TomlLoader
from confiq.loader._yaml import YamlLoader


_LOADER_CLASSES: tuple[type[Loader], ...] = (JsonLoader, TomlLoader, YamlLoader)


def default_loaders() -> dict[str, Loader]:
    """Map each known file suffix to a fresh loader instance (ADR 0042)."""
    registry: dict[str, Loader] = {}
    for loader_class in _LOADER_CLASSES:
        instance = loader_class()
        for suffix in instance.suffixes:
            registry[suffix] = instance
    return registry


def loader_for_suffix(suffix: str) -> Loader | None:
    """Return a loader for the given file suffix, or None if unrecognised.

    Unknown suffixes return None so FileSource can raise a SourceError naming the
    path rather than surfacing an opaque KeyError.
    """
    return default_loaders().get(suffix.lower())
