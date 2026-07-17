"""Unit tests pinning the Stage 3 loaders (`confiq.loader._json`/`_toml`/`_yaml`/`_registry`)."""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from confiq.loader._json import JsonLoader
from confiq.loader._loader import _NON_MAPPING_MESSAGE
from confiq.loader._registry import default_loaders
from confiq.loader._registry import loader_for_suffix
from confiq.loader._toml import TomlLoader
from confiq.loader._yaml import YamlLoader


_TOML_AVAILABLE = sys.version_info >= (3, 11) or importlib.util.find_spec("tomli") is not None
_EMPTY_INPUTS = [
    pytest.param(b"", id="empty"),
    pytest.param(b"   ", id="spaces"),
    pytest.param(b"\n\t ", id="whitespace"),
]


def test_json_loader_parse_with_valid_mapping_round_trips() -> None:
    parsed = JsonLoader().parse(b'{"host": "localhost", "port": 5432}')

    assert parsed == {"host": "localhost", "port": 5432}


@pytest.mark.parametrize("raw", _EMPTY_INPUTS)
def test_json_loader_parse_with_empty_input_returns_empty_mapping(raw: bytes) -> None:
    assert JsonLoader().parse(raw) == {}


def test_json_loader_parse_with_malformed_content_raises_json_decode_error() -> None:
    with pytest.raises(json.JSONDecodeError):
        JsonLoader().parse(b"{not valid json")


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b"[1, 2, 3]", id="list"),
        pytest.param(b"42", id="scalar"),
    ],
)
def test_json_loader_parse_with_non_mapping_top_level_raises(raw: bytes) -> None:
    with pytest.raises(ValueError, match=_NON_MAPPING_MESSAGE):
        JsonLoader().parse(raw)


@pytest.mark.skipif(not _TOML_AVAILABLE, reason="toml backend (tomllib 3.11+ / tomli extra) unavailable")
def test_toml_loader_parse_with_valid_mapping_round_trips() -> None:
    parsed = TomlLoader().parse(b'host = "localhost"\nport = 5432')

    assert parsed == {"host": "localhost", "port": 5432}


@pytest.mark.skipif(not _TOML_AVAILABLE, reason="toml backend (tomllib 3.11+ / tomli extra) unavailable")
@pytest.mark.parametrize("raw", _EMPTY_INPUTS)
def test_toml_loader_parse_with_empty_input_returns_empty_mapping(raw: bytes) -> None:
    assert TomlLoader().parse(raw) == {}


@pytest.mark.skipif(not _TOML_AVAILABLE, reason="toml backend (tomllib 3.11+ / tomli extra) unavailable")
def test_toml_loader_parse_with_malformed_content_raises_toml_decode_error() -> None:
    if sys.version_info >= (3, 11):
        import tomllib as toml_module
    else:
        import tomli as toml_module

    with pytest.raises(toml_module.TOMLDecodeError):
        TomlLoader().parse(b"key = = 1")


def test_yaml_loader_parse_with_valid_mapping_round_trips() -> None:
    pytest.importorskip("yaml")

    parsed = YamlLoader().parse(b"host: localhost\nport: 5432")

    assert parsed == {"host": "localhost", "port": 5432}


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"   ", id="spaces"),
        pytest.param(b"# comment only", id="comment"),
        pytest.param(b"---", id="empty document"),
        pytest.param(b"null", id="explicit null"),
    ],
)
def test_yaml_loader_parse_with_empty_or_null_returns_empty_mapping(raw: bytes) -> None:
    pytest.importorskip("yaml")

    assert YamlLoader().parse(raw) == {}


def test_yaml_loader_parse_with_malformed_content_raises_yaml_error() -> None:
    yaml = pytest.importorskip("yaml")  # pyright: ignore[reportAny]  # optional-dep module attr is Any

    with pytest.raises(yaml.YAMLError):  # pyright: ignore[reportAny]  # optional-dep module attr is Any
        YamlLoader().parse(b"key: : bad")


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b"- 1\n- 2\n- 3", id="list"),
        pytest.param(b"42", id="scalar"),
    ],
)
def test_yaml_loader_parse_with_non_mapping_top_level_raises(raw: bytes) -> None:
    pytest.importorskip("yaml")

    with pytest.raises(ValueError, match=_NON_MAPPING_MESSAGE):
        YamlLoader().parse(raw)


@pytest.mark.parametrize(
    ("suffix", "expected_type"),
    [
        pytest.param(".json", JsonLoader, id=".json"),
        pytest.param(".toml", TomlLoader, id=".toml"),
        pytest.param(".yaml", YamlLoader, id=".yaml"),
        pytest.param(".yml", YamlLoader, id=".yml"),
    ],
)
def test_loader_for_suffix_maps_known_suffix_to_loader(suffix: str, expected_type: type) -> None:
    assert isinstance(loader_for_suffix(suffix), expected_type)


def test_loader_for_suffix_normalises_case_before_lookup() -> None:
    assert isinstance(loader_for_suffix(".JSON"), JsonLoader)


@pytest.mark.parametrize(
    "suffix",
    [
        pytest.param(".txt", id=".txt"),
        pytest.param(".ini", id=".ini"),
        pytest.param("", id="no suffix"),
    ],
)
def test_loader_for_suffix_with_unknown_suffix_returns_none(suffix: str) -> None:
    assert loader_for_suffix(suffix) is None


def test_default_loaders_registers_every_builtin_suffix() -> None:
    registry = default_loaders()

    assert isinstance(registry[".json"], JsonLoader)
    assert isinstance(registry[".toml"], TomlLoader)
    assert isinstance(registry[".yaml"], YamlLoader)
    assert isinstance(registry[".yml"], YamlLoader)
