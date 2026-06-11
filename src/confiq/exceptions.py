"""Module containing error types used throughout the confiq package."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


class ConfiqError(Exception): ...


class SourceError(ConfiqError):
    def __init__(self, source_name: str, message: str) -> None: ...


class SchemaError(ConfiqError): ...


@dataclass(frozen=True)
class ErrorContext:
    field_path: str
    sources: Sequence[str]


class MissingConfigError(ConfiqError):
    def __init__(self, context: ErrorContext) -> None: ...

    @property
    def field_path(self) -> str: ...

    @property
    def sources(self) -> Sequence[str]: ...


class ConfigValidationError(ConfiqError):
    def __init__(
        self,
        context: ErrorContext,
        *,
        original: Exception | None = None,
    ) -> None: ...

    @property
    def field_path(self) -> str: ...

    @property
    def sources(self) -> Sequence[str]: ...
