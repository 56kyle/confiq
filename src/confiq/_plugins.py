"""Module containing the Pydantic schema adapter and the plugin manager factory used throughout the confiq package."""
from __future__ import annotations

from typing import Any

import pluggy

from confiq._hookspecs import ConfiqSpecs
from confiq._hookspecs import SchemaAdapter
from confiq._hookspecs import hookimpl


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
    pm.register(_PydanticAdapterProvider())
    pm.load_setuptools_entrypoints("confiq")
    return pm
