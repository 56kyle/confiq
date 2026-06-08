"""Module containing error types used throughout the confiq package."""
from __future__ import annotations

from collections.abc import Sequence


class ConfiqError(Exception): ...


class SourceError(ConfiqError):
    def __init__(self, source_name: str, message: str) -> None: ...


class SchemaError(ConfiqError): ...


class MissingConfigError(ConfiqError):
    field_path: str
    sources: Sequence[str]

    def __init__(self, field_path: str, sources: Sequence[str]) -> None: ...


class ConfigValidationError(ConfiqError):
    field_path: str
    sources: Sequence[str]

    def __init__(
        self,
        field_path: str,
        sources: Sequence[str],
        *,
        original: Exception | None = None,
    ) -> None: ...
