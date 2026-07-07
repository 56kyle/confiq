"""Unit tests pinning the Stage 1 error interface (`confiq.exceptions`)."""

from __future__ import annotations

import pytest

from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError
from confiq.exceptions import ErrorContext
from confiq.exceptions import MissingConfigError
from confiq.exceptions import SourceError


def test_source_error_exposes_source_name() -> None:
    error = SourceError("env", "boom")

    assert error.source_name == "env"


def test_source_error_composes_message() -> None:
    error = SourceError("env", "boom")

    assert str(error) == "env: boom"


@pytest.mark.parametrize("error_type", [MissingConfigError, ConfigValidationError])
def test_aggregate_error_coerces_contexts_to_tuple(
    error_type: type[MissingConfigError | ConfigValidationError],
) -> None:
    contexts = [ErrorContext("db.host", ["env"])]

    error = error_type(contexts)

    assert error.contexts == (ErrorContext("db.host", ["env"]),)
    assert isinstance(error.contexts, tuple)


@pytest.mark.parametrize("error_type", [MissingConfigError, ConfigValidationError])
def test_aggregate_error_forwards_field_path_and_sources_to_first_context(
    error_type: type[MissingConfigError | ConfigValidationError],
) -> None:
    error = error_type(
        [
            ErrorContext("db.host", ["env"]),
            ErrorContext("db.port", ["file"]),
        ],
    )

    assert error.field_path == "db.host"
    assert error.sources == ("env",)


@pytest.mark.parametrize("error_type", [MissingConfigError, ConfigValidationError])
def test_aggregate_error_retains_all_contexts(
    error_type: type[MissingConfigError | ConfigValidationError],
) -> None:
    contexts = [ErrorContext("db.host", ["env"]), ErrorContext("db.port", ["file"])]

    error = error_type(contexts)

    assert error.contexts == tuple(contexts)


@pytest.mark.parametrize("error_type", [MissingConfigError, ConfigValidationError])
def test_aggregate_error_with_zero_contexts_raises_value_error_outside_confiq_tree(
    error_type: type[MissingConfigError | ConfigValidationError],
) -> None:
    with pytest.raises(ValueError) as exc_info:  # noqa: PT011
        error_type([])

    assert not isinstance(exc_info.value, ConfiqError)


def test_aggregate_errors_are_independently_catchable() -> None:
    contexts = [ErrorContext("db.host", ["env"])]

    cve = ConfigValidationError(contexts)
    mce = MissingConfigError(contexts)

    assert not isinstance(cve, MissingConfigError)
    assert not isinstance(mce, ConfigValidationError)
    assert isinstance(cve, ConfiqError)
    assert isinstance(mce, ConfiqError)


def test_config_validation_error_stores_original() -> None:
    original = RuntimeError("underlying")

    error = ConfigValidationError([ErrorContext("db.host", ["env"])], original=original)

    assert error.original is original


def test_config_validation_error_original_defaults_to_none() -> None:
    error = ConfigValidationError([ErrorContext("db.host", ["env"])])

    assert error.original is None
