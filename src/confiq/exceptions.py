"""Module containing error types used throughout the confiq package."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


class ConfiqError(Exception): ...


class SourceError(ConfiqError):
    def __init__(self, source_name: str, message: str) -> None:
        self.source_name = source_name
        super().__init__(f"{source_name}: {message}")


class SourceNotFoundError(SourceError):
    """A source's backing input is absent, distinct from malformed content (ADR 0040)."""


class SchemaError(ConfiqError): ...


class SecretMaskingError(SchemaError):
    """A schema kind that cannot mask secrets carries ConfigField(secret=True) (ADR 0039).

    Subclasses SchemaError, so `except SchemaError` still catches it; the offending
    field paths and schema kind are kept on attributes so callers need not parse the
    message.
    """

    def __init__(self, field_paths: tuple[str, ...], schema_kind: str) -> None:
        self.field_paths = field_paths
        self.schema_kind = schema_kind
        rendered = ", ".join(field_paths)
        super().__init__(
            f"{schema_kind} schema cannot mask secrets, but ConfigField(secret=True) is set on "
            f"{rendered}. Use a pydantic model or a stdlib/pydantic dataclass for that structure, "
            f"or drop secret=True.",
        )


class AmbiguousBindingError(SchemaError):
    """A CLI parameter's name matches more than one config-path leaf by convention (ADR 0027).

    Subclasses SchemaError, so `except SchemaError` still catches it; the parameter and the
    candidate paths are kept on attributes so callers need not parse the message.
    """

    def __init__(self, parameter: str, candidates: tuple[str, ...]) -> None:
        self.parameter = parameter
        self.candidates = candidates
        rendered = ", ".join(candidates)
        super().__init__(
            f"CLI parameter {parameter!r} is ambiguous: its name matches config paths "
            f"{rendered}. Disambiguate with ConfigBind('dotted.path').",
        )


class UnknownBindTargetError(SchemaError):
    """A declared bind or alias target names no field in the schema path table (ADR 0027, 0048).

    Subclasses SchemaError; the offending target is kept on an attribute so callers need not
    parse the message.
    """

    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__(
            f"config path {target!r} is not a field in the schema; it must name a leaf in the schema path table.",
        )


class IntermediateBindTargetError(SchemaError):
    """A declared bind or alias target names an intermediate node rather than a leaf (ADR 0027, 0048).

    Subclasses SchemaError; the offending target is kept on an attribute so callers need not
    parse the message.
    """

    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__(
            f"config path {target!r} binds to an intermediate node, not a leaf; bind a scalar leaf path.",
        )


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
