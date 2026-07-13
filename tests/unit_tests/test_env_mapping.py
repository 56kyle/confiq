"""Unit tests pinning the shared flat→nested env translation (`confiq.source._env_mapping`, ADR 0048)."""

from __future__ import annotations

from confiq.source._env_mapping import flat_to_nested


def test_flat_to_nested_splits_prefixed_key_and_lowercases_segments() -> None:
    result = flat_to_nested({"APP__DB__HOST": "h"}, prefix="APP", delimiter="__", aliases={})

    assert result == {"db": {"host": "h"}}


def test_flat_to_nested_ignores_keys_outside_the_prefix_boundary() -> None:
    result = flat_to_nested({"OTHER__PORT": "9999"}, prefix="APP", delimiter="__", aliases={})

    assert result == {}


def test_flat_to_nested_with_empty_prefix_nests_every_key() -> None:
    result = flat_to_nested({"DB__HOST": "h"}, prefix="", delimiter="__", aliases={})

    assert result == {"db": {"host": "h"}}


def test_flat_to_nested_alias_overrides_prefix_convention_at_same_path() -> None:
    result = flat_to_nested(
        {"APP__DATABASE__URL": "from-prefix", "RAW": "from-alias"},
        prefix="APP",
        delimiter="__",
        aliases={"database.url": "RAW"},
    )

    assert result == {"database": {"url": "from-alias"}}


def test_flat_to_nested_alias_with_absent_named_var_contributes_nothing() -> None:
    result = flat_to_nested({}, prefix="APP", delimiter="__", aliases={"database.url": "MISSING"})

    assert result == {}
