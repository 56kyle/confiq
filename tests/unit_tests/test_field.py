from __future__ import annotations

import dataclasses

import pytest

from confiq.schema._field import ConfigField


def test_defaults() -> None:
    field = ConfigField()
    assert field.env is None
    assert field.file_key is None
    assert field.secret is False
    assert field.parser is None
    assert field.sources is None
    assert field.on_source_violation == "raise"
    assert field.description is None
    assert field.deprecated is None


def test_frozen_instance_raises_on_assignment() -> None:
    field = ConfigField()
    with pytest.raises(dataclasses.FrozenInstanceError):
        field.env = "NEW_VAR"  # type: ignore[misc]


def test_sources_as_tuple() -> None:
    field = ConfigField(sources=("vault", "env"))
    assert field.sources == ("vault", "env")


def test_sources_none_by_default() -> None:
    field = ConfigField()
    assert field.sources is None


def test_parser_accepts_callable() -> None:
    def parse_int(v: str) -> int:
        return int(v)

    field = ConfigField(parser=parse_int)
    assert field.parser is parse_int
    assert field.parser("42") == 42


def test_on_source_violation_warn_and_skip() -> None:
    field = ConfigField(on_source_violation="warn_and_skip")
    assert field.on_source_violation == "warn_and_skip"


def test_secret_flag() -> None:
    field = ConfigField(secret=True)
    assert field.secret is True


def test_env_stored() -> None:
    field = ConfigField(env="MY_VAR")
    assert field.env == "MY_VAR"


def test_deprecated_stored() -> None:
    field = ConfigField(deprecated="Use new_field instead.")
    assert field.deprecated == "Use new_field instead."
