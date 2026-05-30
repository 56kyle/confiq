from __future__ import annotations

import warnings
from typing import Annotated

import pytest
from pydantic import BaseModel

from confiq._resolver import resolve
from confiq._snapshot import ResolvedSnapshot
from confiq.exceptions import ConflictingSourceError
from confiq.schema._field import ConfigField


def test_single_source_merged_and_provenance() -> None:
    snapshot = resolve([("env", {"host": "pg"})], schema=None)
    assert snapshot.merged == {"host": "pg"}
    assert snapshot.provenance["host"] == "env"


def test_two_sources_later_wins() -> None:
    snapshot = resolve(
        [("file", {"host": "file-host"}), ("env", {"host": "env-host"})],
        schema=None,
    )
    assert snapshot.merged["host"] == "env-host"
    assert snapshot.provenance["host"] == "env"


def test_two_sources_non_overlapping_keys_merged() -> None:
    snapshot = resolve(
        [("file", {"host": "pg"}), ("env", {"port": 5432})],
        schema=None,
    )
    assert snapshot.merged == {"host": "pg", "port": 5432}


def test_returns_resolved_snapshot_type() -> None:
    result = resolve([("mem", {"k": "v"})], schema=None)
    assert isinstance(result, ResolvedSnapshot)


class SecretModel(BaseModel, frozen=True):
    password: Annotated[str, ConfigField(sources=("vault",))] = "default"


def test_config_field_sources_restriction_raises_conflicting_source_error() -> None:
    with pytest.raises(ConflictingSourceError) as exc_info:
        resolve([("env", {"password": "secret"})], schema=SecretModel)
    assert exc_info.value.field_path == "password"
    assert exc_info.value.source_name == "env"
    assert "vault" in exc_info.value.allowed_sources


class WarnModel(BaseModel, frozen=True):
    password: Annotated[str, ConfigField(
        sources=("vault",),
        on_source_violation="warn_and_skip",
    )] = "default"


def test_on_source_violation_warn_and_skip_removes_key_and_warns() -> None:
    with pytest.warns(RuntimeWarning, match="not in the allowed sources"):
        snapshot = resolve([("env", {"password": "secret"})], schema=WarnModel)
    assert "password" not in snapshot.merged


class DeprecatedModel(BaseModel, frozen=True):
    old_key: Annotated[str, ConfigField(deprecated="Use new_key instead.")] = "default"


def test_deprecated_field_emits_deprecation_warning() -> None:
    with pytest.warns(DeprecationWarning, match="deprecated"):
        resolve([("env", {"old_key": "value"})], schema=DeprecatedModel)


class ParsedModel(BaseModel, frozen=True):
    port: Annotated[int, ConfigField(parser=int)] = 5432


def test_parser_is_applied() -> None:
    snapshot = resolve([("env", {"port": "9000"})], schema=ParsedModel)
    assert snapshot.merged["port"] == 9000


class SimpleModel(BaseModel, frozen=True):
    host: str = "localhost"


def test_strict_true_emits_user_warning_for_unknown_key() -> None:
    with pytest.warns(UserWarning, match="not present in schema"):
        resolve([("env", {"host": "pg", "unknown": "x"})], schema=SimpleModel, strict=True)


def test_strict_false_suppresses_unknown_key_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        resolve([("env", {"host": "pg", "unknown": "x"})], schema=SimpleModel, strict=False)
