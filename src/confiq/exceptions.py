"""Module containing exception types used throughout the confiq package."""
from __future__ import annotations

from pydantic_core import InitErrorDetails


class ConfiqError(Exception):
    """Base class for all confiq errors."""


class ConfigLoadError(ConfiqError):
    """Source I/O or parse failure."""


class SourceUnavailableError(ConfigLoadError):
    """Source could not be reached: file missing, network failure, or auth rejected."""


class SourceParseError(ConfigLoadError):
    """Source returned data that could not be parsed: malformed YAML, TOML, or JSON."""


class ConfigValidationError(ConfiqError):
    """Pydantic validation failure for a resolved config value."""

    def __init__(
        self,
        message: str,
        *,
        field_path: str,
        source_names: list[str],
        pydantic_errors: list[InitErrorDetails],
    ) -> None:
        super().__init__(message)
        self.field_path: str = field_path
        self.source_names: list[str] = source_names
        self.pydantic_errors: list[InitErrorDetails] = pydantic_errors


class MissingConfigError(ConfiqError):
    """Required field had no value in any consulted source and has no default."""

    def __init__(
        self,
        message: str,
        *,
        field_path: str,
        consulted_sources: list[str],
    ) -> None:
        super().__init__(message)
        self.field_path: str = field_path
        self.consulted_sources: list[str] = consulted_sources


class ConflictingSourceError(ConfiqError):
    """A source not permitted by ConfigField.sources attempted to set a field."""

    def __init__(
        self,
        message: str,
        *,
        field_path: str,
        source_name: str,
        allowed_sources: tuple[str, ...],
    ) -> None:
        super().__init__(message)
        self.field_path: str = field_path
        self.source_name: str = source_name
        self.allowed_sources: tuple[str, ...] = allowed_sources


class PluginError(ConfiqError):
    """A hookimpl raised an exception; wraps the original."""
