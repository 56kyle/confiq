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
    """Every field error in the failed load was a missing-field error (ADR 0029).

    Raises ValueError if constructed with zero contexts.
    """

    def __init__(self, contexts: Sequence[ErrorContext]) -> None: ...

    @property
    def contexts(self) -> tuple[ErrorContext, ...]: ...

    @property
    def field_path(self) -> str:
        """Forwards to contexts[0].field_path (single-error convenience)."""
        ...

    @property
    def sources(self) -> Sequence[str]:
        """Forwards to contexts[0].sources (single-error convenience)."""
        ...


class ConfigValidationError(ConfiqError):
    """Validation/coercion failed; carries every failure from the load (ADR 0029).

    The message renders all contexts. Raises ValueError if constructed with zero
    contexts.
    """

    def __init__(
        self,
        contexts: Sequence[ErrorContext],
        *,
        original: Exception | None = None,
    ) -> None: ...

    @property
    def contexts(self) -> tuple[ErrorContext, ...]: ...

    @property
    def field_path(self) -> str:
        """Forwards to contexts[0].field_path (single-error convenience)."""
        ...

    @property
    def sources(self) -> Sequence[str]:
        """Forwards to contexts[0].sources (single-error convenience)."""
        ...
