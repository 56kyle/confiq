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


def test_dotenv_source_fetch_with_env_file_returns_flat_mapping(tmp_path: Path) -> None:
    pytest.importorskip("dotenv")
    path = tmp_path / ".env"
    path.write_text("HOST=localhost\nPORT=5432\n")

    assert DotenvSource(path).fetch() == {"HOST": "localhost", "PORT": "5432"}


def test_dotenv_source_name_includes_path(tmp_path: Path) -> None:
    path = tmp_path / ".env"

    assert DotenvSource(path).name == f"dotenv:{path}"
