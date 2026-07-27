"""Integration tests pinning env/dotenv alias resolution through load() (ADR 0048, 0049).

Alias translation is source-side and schema-blind, but alias *targets* are validated resolver-side
against the schema path table in the bind phase. These drive the whole chain via load(): a valid
alias lands its named var at the declared config path, and an alias target that is not a schema leaf
fails loudly with a SchemaError before merge — distinctly for unknown vs. intermediate-node targets.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from confiq import EnvSource
from confiq import load
from confiq.exceptions import IntermediateBindTargetError
from confiq.exceptions import SchemaError
from confiq.exceptions import UnknownBindTargetError


class Database(BaseModel):
    url: str


class AliasSchema(BaseModel):
    database: Database
    port: int


def test_load_with_env_alias_populates_field_from_named_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    monkeypatch.setenv("APP__PORT", "5432")

    result = load(AliasSchema, [EnvSource("APP", aliases={"database.url": "DATABASE_URL"})])

    assert isinstance(result, AliasSchema)
    assert result.database.url == "postgres://x"
    assert result.port == 5432


def test_load_with_unknown_alias_target_raises_unknown_bind_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://x")

    with pytest.raises(UnknownBindTargetError) as exc_info:
        load(AliasSchema, [EnvSource("APP", aliases={"databse.url": "DATABASE_URL"})])

    assert exc_info.value.target == "databse.url"
    assert isinstance(exc_info.value, SchemaError)


def test_load_with_intermediate_alias_target_raises_intermediate_bind_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://x")

    with pytest.raises(IntermediateBindTargetError) as exc_info:
        load(AliasSchema, [EnvSource("APP", aliases={"database": "DATABASE_URL"})])

    assert exc_info.value.target == "database"
