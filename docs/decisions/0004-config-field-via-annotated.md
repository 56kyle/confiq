---
status: accepted
date: 2026-05-29
---
# Use `Annotated[T, ConfigField(...)]` for Per-Field Metadata

## Context and Problem Statement

`confiq` fields need a mechanism to carry per-field behavior metadata:
explicit environment variable names, CLI flags, source restrictions, secret
marking, and custom parsers. The mechanism must be readable by confiq at load
time without requiring a confiq-specific base class in the schema file. It must
also be compatible with schema types other than pydantic — attrs classes and
msgspec structs are plausible via third-party `SchemaAdapter` plugins.

## Decision Drivers

- The schema file should have no mandatory confiq import; a plain `pydantic.BaseModel`
  must work without modification for callers who need no per-field metadata.
- Per-field metadata must survive `typing.get_type_hints(..., include_extras=True)`
  so the resolver can read it at load time.
- `ConfigField` must be orthogonal to pydantic's `FieldInfo` — the two have
  separate concerns and must not be coupled.
- The pattern must compose with type checkers: `host: Annotated[str, ConfigField(...)]`
  should be seen as `host: str` for purposes of field type resolution.

## Considered Options

- **Option A: `Annotated[T, ConfigField(...)]`** — stdlib `Annotated` wrapper
  carrying a frozen `ConfigField` dataclass as metadata.
- **Option B: Pydantic `Field(json_schema_extra=...)`** — encode confiq metadata
  inside pydantic's `FieldInfo` via its `json_schema_extra` escape hatch.
- **Option C: Class-level registry** — a separate `confiq.register_field()`
  decorator or class variable on the schema that stores per-field confiq
  configuration outside the type annotation.

## Decision Outcome

Chosen option: "Option A: `Annotated[T, ConfigField(...)]`", because it keeps
`ConfigField` orthogonal to pydantic, works with any schema type via
`typing.get_type_hints`, and follows the established stdlib pattern used by
Typer, FastAPI, and `dataclasses-json` for exactly this purpose.

### Consequences

- The schema file imports only `confiq.schema.ConfigField` for fields that
  carry confiq metadata. Fields with no per-field metadata require no confiq
  import at all — the schema file remains a plain pydantic `BaseModel`.
- `ConfigField` is a `@dataclass(frozen=True)` with no `**kwargs: Any` escape
  hatch. It carries only the fields that confiq defines; there is no mechanism
  to smuggle untyped data through it.
- Third-party `SchemaAdapter` implementations for attrs or msgspec can read the
  same `Annotated` metadata via `typing.get_type_hints(..., include_extras=True)`,
  giving them access to confiq's per-field behavior without any confiq-specific
  base class or metaclass.
- Type checkers see `host: str`, not `host: Annotated[str, ConfigField(...)]` —
  the `Annotated` wrapper is transparent to type narrowing, making IDE
  autocomplete and mypy/pyright inference unaffected.
- Schema files that need to be shared with code carrying no confiq dependency
  remain shareable: import `ConfigField` only in the files that declare
  confiq-annotated fields, not in callers.

## Pros and Cons of the Options

### Option A: `Annotated[T, ConfigField(...)]`

- Good, because it is the established stdlib pattern for attaching arbitrary
  metadata to types without coupling the type to the library.
  `typing.get_type_hints(..., include_extras=True)` is the documented retrieval
  mechanism.
- Good, because `ConfigField` is fully decoupled from pydantic. Pydantic reads
  `Annotated` for its own metadata (validators, constraints) via the same
  mechanism; the two layers compose without conflict.
- Good, because the schema file has no mandatory confiq import when no `ConfigField`
  annotations are used.
- Good, because it is consistent with how Typer (`Annotated[str, typer.Option(...)]`)
  and FastAPI (`Annotated[str, Depends(...)]`) solve the same problem.
- Neutral, because callers unfamiliar with `Annotated` must learn the pattern;
  it is not self-evident from the field declaration that `ConfigField` metadata
  is being attached.

### Option B: Pydantic `Field(json_schema_extra=...)`

- Good, because pydantic users are already familiar with `Field()`.
- Bad, because `json_schema_extra` carries `dict[str, Any]`, losing the
  type-safe structure that `ConfigField` provides.
- Bad, because pydantic `Field()` is a `FieldInfo` subclass; confiq metadata
  stored inside it is coupled to pydantic even for schema types that use a
  different `SchemaAdapter`.
- Bad, because pydantic reads `FieldInfo` during model construction, creating
  a surface for unintended interaction between confiq's metadata and pydantic's
  validation behavior.

### Option C: Class-Level Registry

- Good, because the schema class itself remains completely free of annotation
  changes.
- Bad, because per-field metadata is physically separated from the field
  declaration, creating a maintenance burden when fields are added, renamed, or
  removed.
- Bad, because it requires a confiq-specific mechanism with no stdlib precedent,
  increasing the conceptual surface for users.
- Bad, because it does not survive `typing.get_type_hints` — a separate lookup
  path is required for every `SchemaAdapter` that wants to read confiq metadata.
