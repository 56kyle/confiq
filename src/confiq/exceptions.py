"""Module containing error types used throughout the confiq package."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


class ConfiqError(Exception): ...


class SourceError(ConfiqError):
    def __init__(self, source_name: str, message: str) -> None:
        self.source_name = source_name
        super().__init__(f"{source_name}: {message}")


class SchemaError(ConfiqError): ...


@dataclass(frozen=True)
class ErrorContext:
    field_path: str
    sources: Sequence[str]

    def __post_init__(self) -> None:
        """Coerce sources to a tuple so a frozen instance holds no mutable field."""
        object.__setattr__(self, "sources", tuple(self.sources))


def _render_contexts(contexts: tuple[ErrorContext, ...]) -> str:
    return "; ".join(f"{context.field_path} (from {', '.join(context.sources)})" for context in contexts)


class _AggregateError(ConfiqError):
    def __init__(self, contexts: Sequence[ErrorContext]) -> None:
        coerced = tuple(contexts)
        if not coerced:
            raise ValueError(f"{type(self).__name__} requires at least one context")
        self._contexts = coerced
        super().__init__(_render_contexts(coerced))

    @property
    def contexts(self) -> tuple[ErrorContext, ...]:
        return self._contexts

    @property
    def field_path(self) -> str:
        """Forwards to contexts[0].field_path (single-error convenience)."""
        return self._contexts[0].field_path

    @property
    def sources(self) -> Sequence[str]:
        """Forwards to contexts[0].sources (single-error convenience)."""
        return self._contexts[0].sources


class MissingConfigError(_AggregateError):
    """Every field error in the failed load was a missing-field error (ADR 0029).

    Raises ValueError if constructed with zero contexts.
    """


class ConfigValidationError(_AggregateError):
    """Validation/coercion failed; carries every failure from the load (ADR 0029).

    The message renders all contexts. Raises ValueError if constructed with zero
    contexts.
    """

    def __init__(
        self,
        contexts: Sequence[ErrorContext],
        *,
        original: Exception | None = None,
    ) -> None:
        self.original = original
        super().__init__(contexts)
