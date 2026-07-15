"""Unit tests pinning the Stage 3 file source (`confiq.source._file`)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from confiq.exceptions import SourceError
from confiq.exceptions import SourceNotFoundError
from confiq.loader._json import JsonLoader
from confiq.source._file import FileSource


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import ModuleType


@pytest.fixture
def require_remote() -> None:
    _ = pytest.importorskip("fsspec")  # pyright: ignore[reportAny]


@pytest.fixture
def write_memory() -> Callable[[str, bytes], None]:
    fsspec: ModuleType = pytest.importorskip("fsspec")  # pyright: ignore[reportAny]

    def _write(path: str, data: bytes) -> None:
        with fsspec.filesystem("memory").open(path, "wb") as handle:  # pyright: ignore[reportAny]
            _ = handle.write(data)  # pyright: ignore[reportAny]

    return _write


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


def test_file_source_fetch_with_remote_json_selects_loader_by_uri_suffix(write_memory: Callable[[str, bytes], None]) -> None:
    write_memory("/remote/json/app.json", b'{"host": "localhost", "port": 5432}')

    assert FileSource("memory://remote/json/app.json").fetch() == {"host": "localhost", "port": 5432}


def test_file_source_fetch_with_remote_yaml_selects_loader_by_uri_suffix(write_memory: Callable[[str, bytes], None]) -> None:
    pytest.importorskip("yaml")
    write_memory("/remote/yaml/app.yaml", b"host: localhost\nport: 5432\n")

    assert FileSource("memory://remote/yaml/app.yaml").fetch() == {"host": "localhost", "port": 5432}


@pytest.mark.usefixtures("require_remote")
def test_file_source_fetch_with_missing_required_remote_raises_source_not_found() -> None:
    uri = "memory://remote/missing/absent.json"

    with pytest.raises(SourceNotFoundError) as excinfo:
        FileSource(uri).fetch()

    assert uri in str(excinfo.value)


@pytest.mark.usefixtures("require_remote")
def test_file_source_fetch_with_missing_optional_remote_returns_empty() -> None:
    assert FileSource("memory://remote/missing/optional.json", required=False).fetch() == {}


def test_file_source_fetch_with_unknown_remote_suffix_raises_source_error(write_memory: Callable[[str, bytes], None]) -> None:
    uri = "memory://remote/unknown/app.txt"
    write_memory("/remote/unknown/app.txt", b"irrelevant")

    with pytest.raises(SourceError) as excinfo:
        FileSource(uri).fetch()

    assert uri in str(excinfo.value)


def test_file_source_fetch_with_malformed_remote_content_raises_source_error_naming_uri(write_memory: Callable[[str, bytes], None]) -> None:
    uri = "memory://remote/malformed/app.json"
    write_memory("/remote/malformed/app.json", b"{not valid json")

    with pytest.raises(SourceError) as excinfo:
        FileSource(uri).fetch()

    assert uri in str(excinfo.value)


def test_file_source_fetch_with_missing_cloud_backend_raises_branded_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "s3fs", None)

    with pytest.raises(ImportError) as excinfo:
        FileSource("s3://bucket/key.json").fetch()

    assert "confiq[s3]" in str(excinfo.value)
    assert not isinstance(excinfo.value, SourceError)


def test_file_source_init_with_storage_options_on_local_path_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "app.json"

    with pytest.raises(ValueError, match="remote") as excinfo:
        _ = FileSource(path, storage_options={"key": "v"})

    assert repr(str(path)) in str(excinfo.value)


def test_file_source_init_with_storage_options_on_remote_uri_constructs() -> None:
    source = FileSource("s3://bucket/key.json", storage_options={"key": "v"})

    assert source.name == "file:s3://bucket/key.json"


def test_file_source_fetch_with_remote_permission_error_raises_source_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fsspec: ModuleType = pytest.importorskip("fsspec")  # pyright: ignore[reportAny]
    uri = "memory://remote/denied/app.json"

    def _raise_permission(_uri: str, _mode: str, **_kwargs: object) -> object:
        raise PermissionError("denied")

    monkeypatch.setattr(fsspec, "open", _raise_permission)

    with pytest.raises(SourceError) as excinfo:
        FileSource(uri).fetch()

    assert uri in str(excinfo.value)
    assert not isinstance(excinfo.value, SourceNotFoundError)


def test_file_source_fetch_with_remote_non_oserror_raises_source_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fsspec: ModuleType = pytest.importorskip("fsspec")  # pyright: ignore[reportAny]
    uri = "memory://remote/throttled/app.json"

    def _raise_runtime(_uri: str, _mode: str, **_kwargs: object) -> object:
        raise RuntimeError("throttled")

    monkeypatch.setattr(fsspec, "open", _raise_runtime)

    with pytest.raises(SourceError) as excinfo:
        FileSource(uri).fetch()

    assert uri in str(excinfo.value)


def test_file_source_fetch_passes_storage_options_to_fsspec(monkeypatch: pytest.MonkeyPatch) -> None:
    fsspec: ModuleType = pytest.importorskip("fsspec")  # pyright: ignore[reportAny]
    captured: dict[str, object] = {}

    class _Handle:
        def __enter__(self) -> _Handle:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

        def read(self) -> bytes:
            return b'{"host": "localhost"}'

    def _fake_open(_uri: str, _mode: str, **kwargs: object) -> _Handle:
        captured.update(kwargs)
        return _Handle()

    monkeypatch.setattr(fsspec, "open", _fake_open)

    result = FileSource("memory://remote/opts/app.json", storage_options={"key": "val"}).fetch()

    assert captured == {"key": "val"}
    assert result == {"host": "localhost"}


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        pytest.param("s3://b/k.json?versionId=abc", ".json", id="query-string-stripped"),
        pytest.param("s3://b/k.yaml", ".yaml", id="plain-yaml"),
        pytest.param("s3://b/dir.d/k.toml", ".toml", id="dotted-dir"),
    ],
)
def test_file_source__remote_suffix_derives_suffix_immune_to_query_and_path(uri: str, expected: str) -> None:
    assert FileSource._remote_suffix(uri) == expected


def test_file_source_name_includes_remote_uri_without_mangling() -> None:
    assert FileSource("s3://b/k.json").name == "file:s3://b/k.json"


class _ImportErrorLoader:
    suffixes = frozenset({".json"})

    def parse(self, raw: bytes) -> dict[str, object]:
        _ = raw
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
