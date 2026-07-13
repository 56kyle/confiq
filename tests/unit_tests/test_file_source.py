"""Unit tests pinning the Stage 3 file source (`confiq.source._file`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from confiq.exceptions import SourceError
from confiq.exceptions import SourceNotFoundError
from confiq.loader._json import JsonLoader
from confiq.source._file import FileSource


if TYPE_CHECKING:
    from pathlib import Path


def test_file_source_fetch_with_json_file_selects_loader_by_suffix(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"host": "localhost", "port": 5432}')

    assert FileSource(path).fetch() == {"host": "localhost", "port": 5432}


def test_file_source_fetch_with_explicit_loader_overrides_suffix(tmp_path: Path) -> None:
    path = tmp_path / "config.txt"
    path.write_text('{"host": "localhost"}')

    assert FileSource(path, loader=JsonLoader()).fetch() == {"host": "localhost"}


def test_file_source_fetch_with_missing_required_file_raises_source_not_found(tmp_path: Path) -> None:
    with pytest.raises(SourceNotFoundError):
        FileSource(tmp_path / "absent.json").fetch()


def test_file_source_fetch_with_missing_optional_file_returns_empty(tmp_path: Path) -> None:
    assert FileSource(tmp_path / "absent.json", required=False).fetch() == {}


def test_file_source_fetch_with_unknown_suffix_raises_source_error(tmp_path: Path) -> None:
    path = tmp_path / "config.txt"
    path.write_text("irrelevant")

    with pytest.raises(SourceError):
        FileSource(path).fetch()


def test_file_source_fetch_with_malformed_content_raises_source_error_naming_path(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not valid json")

    with pytest.raises(SourceError) as excinfo:
        FileSource(path).fetch()

    assert str(path) in str(excinfo.value)


def test_file_source_fetch_with_non_mapping_top_level_raises_source_error(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]")

    with pytest.raises(SourceError):
        FileSource(path).fetch()


def test_file_source_fetch_with_remote_uri_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        FileSource("s3://bucket/key.json").fetch()


class _ImportErrorLoader:
    suffixes = frozenset({".json"})

    def parse(self, _raw: bytes) -> dict[str, object]:
        raise ImportError("confiq requires the 'yaml' extra for this feature")


def test_file_source_fetch_propagates_loader_import_error_unwrapped(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{}")

    with pytest.raises(ImportError) as excinfo:
        FileSource(path, loader=_ImportErrorLoader()).fetch()

    assert not isinstance(excinfo.value, SourceError)


def test_file_source_name_includes_path(tmp_path: Path) -> None:
    path = tmp_path / "config.json"

    assert FileSource(path).name == f"file:{path}"


def test_source_not_found_error_is_subclass_of_source_error() -> None:
    assert issubclass(SourceNotFoundError, SourceError)
