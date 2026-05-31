from __future__ import annotations

import pluggy

from confiq._plugins import _make_plugin_manager


def test_make_plugin_manager_returns_plugin_manager() -> None:
    assert isinstance(_make_plugin_manager(), pluggy.PluginManager)


def test_plugin_manager_has_pydantic_adapter_for_base_model() -> None:
    from pydantic import BaseModel

    class MySchema(BaseModel):
        key: str

    pm = _make_plugin_manager()
    adapter = pm.hook.confiq_get_schema_adapter(schema=MySchema)
    assert adapter is not None


def test_plugin_manager_returns_none_adapter_for_plain_class() -> None:
    class NotAModel:
        pass

    pm = _make_plugin_manager()
    adapter = pm.hook.confiq_get_schema_adapter(schema=NotAModel)
    assert adapter is None
