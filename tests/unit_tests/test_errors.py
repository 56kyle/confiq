from __future__ import annotations

from confiq.exceptions import ConfigLoadError
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError
from confiq.exceptions import ConflictingSourceError
from confiq.exceptions import MissingConfigError
from confiq.exceptions import PluginError
from confiq.exceptions import SourceParseError
from confiq.exceptions import SourceUnavailableError


def test_confiq_error_is_exception() -> None:
    assert issubclass(ConfiqError, Exception)


def test_config_load_error_is_confiq_error() -> None:
    assert issubclass(ConfigLoadError, ConfiqError)


def test_source_unavailable_error_is_config_load_error() -> None:
    assert issubclass(SourceUnavailableError, ConfigLoadError)


def test_source_parse_error_is_config_load_error() -> None:
    assert issubclass(SourceParseError, ConfigLoadError)


def test_plugin_error_is_confiq_error() -> None:
    assert issubclass(PluginError, ConfiqError)


def test_config_validation_error_with_field_path() -> None:
    exc = ConfigValidationError(
        "bad value",
        field_path="database.host",
        source_names=["env", "file"],
        pydantic_errors=[],
    )
    assert exc.field_path == "database.host"
    assert exc.source_names == ["env", "file"]
    assert exc.pydantic_errors == []
    assert str(exc) == "bad value"


def test_config_validation_error_is_confiq_error() -> None:
    exc = ConfigValidationError(
        "bad",
        field_path="x",
        source_names=[],
        pydantic_errors=[],
    )
    assert isinstance(exc, ConfiqError)


def test_missing_config_error_with_field_path() -> None:
    exc = MissingConfigError(
        "missing field",
        field_path="api.key",
        consulted_sources=["env", "file", "memory"],
    )
    assert exc.field_path == "api.key"
    assert exc.consulted_sources == ["env", "file", "memory"]
    assert str(exc) == "missing field"


def test_missing_config_error_is_confiq_error() -> None:
    exc = MissingConfigError("m", field_path="f", consulted_sources=[])
    assert isinstance(exc, ConfiqError)


def test_conflicting_source_error_with_fields() -> None:
    exc = ConflictingSourceError(
        "conflict",
        field_path="password",
        source_name="env",
        allowed_sources=("vault",),
    )
    assert exc.field_path == "password"
    assert exc.source_name == "env"
    assert exc.allowed_sources == ("vault",)
    assert str(exc) == "conflict"


def test_conflicting_source_error_is_confiq_error() -> None:
    exc = ConflictingSourceError(
        "c",
        field_path="f",
        source_name="s",
        allowed_sources=(),
    )
    assert isinstance(exc, ConfiqError)
