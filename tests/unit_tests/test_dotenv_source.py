"""Unit tests pinning the Stage 3 dotenv source (`confiq.source._dotenv`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from confiq.exceptions import SourceNotFoundError
from confiq.source._dotenv import DotenvSource


if TYPE_CHECKING:
    from pathlib import Path


def test_dotenv_source_with_missing_optional_file_returns_empty(tmp_path: Path) -> None:
    assert DotenvSource(tmp_path / ".env").fetch() == {}


def test_dotenv_source_with_missing_required_file_raises_source_not_found(tmp_path: Path) -> None:
    with pytest.raises(SourceNotFoundError):
        DotenvSource(tmp_path / ".env", required=True).fetch()


def test_dotenv_source_fetch_with_env_file_nests_and_lowercases(tmp_path: Path) -> None:
    pytest.importorskip("dotenv")
    path = tmp_path / ".env"
    path.write_text("HOST=localhost\nPORT=5432\n")

    assert DotenvSource(path).fetch() == {"host": "localhost", "port": "5432"}


def test_dotenv_source_fetch_with_alias_reads_named_var_into_declared_path(tmp_path: Path) -> None:
    pytest.importorskip("dotenv")
    path = tmp_path / ".env"
    path.write_text("SERVER__HOST=localhost\nDATABASE_URL=pg://x\n")

    fetched = DotenvSource(path, aliases={"database.url": "DATABASE_URL"}).fetch()

    assert fetched == {
        "server": {"host": "localhost"},
        "database_url": "pg://x",
        "database": {"url": "pg://x"},
    }


def test_dotenv_source_alias_targets_exposes_declared_config_paths(tmp_path: Path) -> None:
    source = DotenvSource(tmp_path / ".env", aliases={"database.url": "DATABASE_URL"})

    assert tuple(source.alias_targets) == ("database.url",)


def test_dotenv_source_name_includes_path(tmp_path: Path) -> None:
    path = tmp_path / ".env"

    assert DotenvSource(path).name == f"dotenv:{path}"
