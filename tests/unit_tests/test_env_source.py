"""Unit tests pinning the Stage 3 environment source (`confiq.source._env`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from confiq.source._env import EnvSource


if TYPE_CHECKING:
    import pytest


def test_env_source_fetch_nests_prefixed_vars_and_lowercases_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP__DATABASE__HOST", "localhost")

    assert EnvSource("APP").fetch() == {"database": {"host": "localhost"}}


def test_env_source_fetch_ignores_vars_outside_the_prefix_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP__PORT", "5432")
    monkeypatch.setenv("APPLE__PORT", "9999")

    assert EnvSource("APP").fetch() == {"port": "5432"}


def test_env_source_fetch_with_no_matching_vars_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTHER__PORT", "5432")

    assert EnvSource("CONFIQ_NOPE").fetch() == {}


def test_env_source_fetch_with_scalar_intermediate_replaced_by_deeper_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP__DB", "connstr")
    monkeypatch.setenv("APP__DB__HOST", "localhost")

    assert EnvSource("APP").fetch() == {"db": {"host": "localhost"}}


def test_env_source_fetch_with_custom_delimiter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DB_HOST", "localhost")

    assert EnvSource("APP", delimiter="_").fetch() == {"db": {"host": "localhost"}}


def test_env_source_fetch_with_alias_reads_named_var_into_declared_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    monkeypatch.setenv("APP__PORT", "5432")

    fetched = EnvSource("APP", aliases={"database.url": "DATABASE_URL"}).fetch()

    assert fetched == {"port": "5432", "database": {"url": "postgres://x"}}


def test_env_source_fetch_with_alias_beats_prefix_convention_at_same_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP__DATABASE__URL", "from-prefix")
    monkeypatch.setenv("DATABASE_URL", "from-alias")

    fetched = EnvSource("APP", aliases={"database.url": "DATABASE_URL"}).fetch()

    assert fetched == {"database": {"url": "from-alias"}}


def test_env_source_alias_targets_exposes_declared_config_paths() -> None:
    source = EnvSource("APP", aliases={"database.url": "DATABASE_URL", "port": "PORT"})

    assert set(source.alias_targets) == {"database.url", "port"}


def test_env_source_name_includes_prefix() -> None:
    assert EnvSource("APP").name == "env:APP"


def test_env_source_exposes_profile() -> None:
    assert EnvSource("APP", profile="test").profile == "test"
