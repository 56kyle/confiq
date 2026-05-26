"""Pluggy plugin-manager factory and built-in loader/adapter registrations."""

from __future__ import annotations

import configparser
import json
from typing import TYPE_CHECKING
from typing import Any

import pluggy

from confiq._hookspecs import ConfiqSpecs
from confiq._hookspecs import hookimpl


if TYPE_CHECKING:
    from pathlib import Path


def _make_plugin_manager() -> pluggy.PluginManager:
    pm = pluggy.PluginManager("confiq")
    pm.add_hookspecs(ConfiqSpecs)
    pm.register(_BuiltinLoaders(), name="confiq.builtin.loaders")
    pm.register(_BuiltinAdapters(), name="confiq.builtin.adapters")
    pm.load_setuptools_entrypoints("confiq")
    return pm


def _register_optional_loaders(pm: pluggy.PluginManager) -> None:
    try:
        from confiq.loaders import yaml_loader

        pm.register(yaml_loader, name="confiq.builtin.yaml")
    except ImportError:
        pass
    try:
        from confiq.loaders import toml_loader

        pm.register(toml_loader, name="confiq.builtin.toml")
    except ImportError:
        pass


class _BuiltinLoaders:
    @hookimpl
    def confiq_load_file(self, path: Path, suffix: str) -> dict[str, Any] | None:
        if suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        if suffix == ".ini":
            cp = configparser.ConfigParser()
            cp.read(path, encoding="utf-8")
            return {s: dict(cp.items(s)) for s in cp.sections()}
        return None


def _is_typeddict(tp: object) -> bool:
    return isinstance(tp, type) and hasattr(tp, "__required_keys__") and hasattr(tp, "__optional_keys__")


class _BuiltinAdapters:
    @hookimpl
    def confiq_get_schema_adapter(self, schema: type) -> Any | None:
        from dataclasses import is_dataclass

        from pydantic import BaseModel

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            from confiq.schema.pydantic_adapter import PydanticAdapter

            return PydanticAdapter(schema)
        if is_dataclass(schema):
            from confiq.schema.dataclass_adapter import DataclassAdapter

            return DataclassAdapter(schema)
        if _is_typeddict(schema):
            from confiq.schema.typeddict_adapter import TypedDictAdapter

            return TypedDictAdapter(schema)
        return None
