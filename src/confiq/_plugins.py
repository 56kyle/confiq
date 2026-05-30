"""Module containing built-in pluggy plugin implementations and the plugin manager factory used throughout the confiq package."""
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pluggy

from confiq._hookspecs import ConfiqSpecs
from confiq._hookspecs import SchemaAdapter
from confiq._hookspecs import hookimpl
from confiq.exceptions import SourceParseError


if TYPE_CHECKING:
    from pathlib import Path


class _JsonLoader:
    @hookimpl
    def confiq_load_file(self, path: Path) -> dict[str, Any] | None:
        if path.suffix != ".json":
            return None
        import json

        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise SourceParseError(f"JSON parse error in {path}: {exc}") from exc
        except FileNotFoundError:
            return None


class _IniLoader:
    @hookimpl
    def confiq_load_file(self, path: Path) -> dict[str, Any] | None:
        if path.suffix not in {".ini", ".cfg"}:
            return None
        import configparser

        cp: configparser.ConfigParser = configparser.ConfigParser()
        cp.read(path)
        return {s: dict(cp[s]) for s in cp.sections()}


class _PydanticAdapter:
    def __init__(self, schema: type) -> None:
        self._schema: type = schema

    def field_hints(self) -> dict[str, object]:
        from typing import get_type_hints

        return get_type_hints(self._schema, include_extras=True)

    def validate(self, data: dict[str, Any]) -> object:
        return self._schema.model_validate(data)


class _PydanticAdapterProvider:
    @hookimpl
    def confiq_get_schema_adapter(self, schema: type) -> SchemaAdapter | None:
        try:
            from pydantic import BaseModel
        except ImportError:
            return None
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return _PydanticAdapter(schema)
        return None


def _make_plugin_manager() -> pluggy.PluginManager:
    pm: pluggy.PluginManager = pluggy.PluginManager("confiq")
    pm.add_hookspecs(ConfiqSpecs)
    pm.register(_JsonLoader())
    pm.register(_IniLoader())
    pm.register(_PydanticAdapterProvider())
    _register_optional_loaders(pm)
    pm.load_setuptools_entrypoints("confiq")
    return pm


def _register_optional_loaders(pm: pluggy.PluginManager) -> None:
    try:
        import yaml

        class _YamlLoader:
            @hookimpl
            def confiq_load_file(self, path: Path) -> dict[str, Any] | None:
                if path.suffix not in {".yaml", ".yml"}:
                    return None
                try:
                    return yaml.safe_load(path.read_text())
                except yaml.YAMLError as exc:
                    raise SourceParseError(f"YAML parse error in {path}: {exc}") from exc
                except FileNotFoundError:
                    return None

        pm.register(_YamlLoader())
    except ImportError:
        pass

    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        class _TomlLoader:
            @hookimpl
            def confiq_load_file(self, path: Path) -> dict[str, Any] | None:
                if path.suffix != ".toml":
                    return None
                try:
                    return tomllib.load(path.open("rb"))
                except tomllib.TOMLDecodeError as exc:
                    raise SourceParseError(f"TOML parse error in {path}: {exc}") from exc
                except FileNotFoundError:
                    return None

        pm.register(_TomlLoader())
    except ImportError:
        pass
