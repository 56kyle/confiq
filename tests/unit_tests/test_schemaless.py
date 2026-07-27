"""Unit tests pinning the Stage 2 read-only schemaless mapping (`confiq._schemaless`, ADR 0038)."""

from __future__ import annotations

from typing import cast

import pytest

from confiq._schemaless import SchemalessConfig


def test_schemaless_config_getitem_returns_value() -> None:
    config = SchemalessConfig({"host": "localhost"})

    assert config["host"] == "localhost"


def test_schemaless_config_getitem_with_nested_mapping_wraps_recursively() -> None:
    config = SchemalessConfig({"database": {"host": "localhost"}})

    nested = cast("object", config["database"])

    assert isinstance(nested, SchemalessConfig)
    assert nested["host"] == "localhost"


def test_schemaless_config_len_reflects_top_level_keys() -> None:
    config = SchemalessConfig({"a": 1, "b": 2})

    assert len(config) == 2


def test_schemaless_config_iter_yields_top_level_keys() -> None:
    config = SchemalessConfig({"a": 1, "b": {"c": 2}})

    assert list(config) == ["a", "b"]


def test_schemaless_config_is_read_only() -> None:
    config = SchemalessConfig({"host": "localhost"})

    with pytest.raises(TypeError):
        config["host"] = "other"  # pyright: ignore[reportIndexIssue]  # read-only by design; pins the runtime refusal


def test_schemaless_config_repr_is_readable() -> None:
    config = SchemalessConfig({"host": "localhost"})

    assert repr(config) == "SchemalessConfig({'host': 'localhost'})"
