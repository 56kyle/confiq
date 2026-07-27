---
status: accepted
date: 2026-06-05
---
# Accept Multiple Schema Types with an Explicit Guarantee Gradient

## Context and Problem Statement

design_d §3–4.

`confiq` must decide which Python types it accepts as a schema. The simplest
answer — frozen pydantic `BaseModel` only — gives the strongest guarantees but
forces callers to rewrite existing dataclasses and `TypedDict`s. A broader
answer accepts more types but must be honest about which guarantees apply to
which types.

The specific question: should `confiq` accept stdlib dataclasses, `TypedDict`s,
and schemaless usage, or should it require pydantic?

## Decision Drivers

- Existing projects often have schema types that predate confiq. Requiring a
  rewrite to `BaseModel` would make adoption a larger migration than it needs to be.
- Pydantic's `TypeAdapter` natively handles `BaseModel`, pydantic dataclasses,
  stdlib dataclasses, and `TypedDict`s with one validation call. A single engine
  is cleaner than per-type bespoke validators.
- The guarantees confiq can offer (immutability, secret masking, rich
  serialization) genuinely differ by schema type. Pretending they do not — by
  advertising all guarantees regardless of schema — would be dishonest.
- The `SchemaAdapter` protocol and pluggy hook (`confiq_get_schema_adapter`)
  should allow third-party schema kinds without modifying the core.

## Considered Options

- **Option A: Frozen pydantic `BaseModel` only** — one schema type, all
  guarantees always on, simple contract.
- **Option B: Multiple schema types with an explicit gradient** — accept
  `BaseModel`, pydantic dataclass, stdlib dataclass, `TypedDict`, and schemaless
  (`None`); document which guarantees apply to each.

## Decision Outcome

Chosen option: **Option B**, because forcing all callers to pydantic creates
unnecessary migration friction, `TypeAdapter` handles all supported types
uniformly, and honest documentation of the guarantee gradient is better than
silently offering weaker guarantees under a strong-sounding contract.

### The gradient

| Schema type | Access | Mutability | Secret-masked `repr` | Rich serialization |
|---|---|---|---|---|
| `BaseModel(frozen=True)` | attribute | immutable | full | full (`model_dump`) |
| `BaseModel` (default) | attribute | mutable | full | full |
| `@dataclass(frozen=True)` | attribute | immutable | invasive | via `TypeAdapter` |
| `@dataclass` | attribute | mutable | invasive | via `TypeAdapter` |
| `TypedDict` | subscript | mutable dict | none | already a dict |
| schemaless (`None`) | subscript | read-only `Mapping` | none | none |

Frozen pydantic is the "all guarantees on" choice. Each step away from it trades
one named guarantee for one named convenience. The gradient is stated in the
documentation rather than buried.

Two consequences are stated prominently:

- **The immutability pillar holds only when the schema is frozen.** The
  lock-free-read guarantee for `ConfigHandle` (see ADR 0010) applies only to
  frozen schemas. A non-frozen dataclass returning mutable config is a
  legitimate informed choice, not a bug.
- **Secret masking is pydantic-strong and degrades on other schema types.**
  Pydantic's `repr` suppression for `secret=True` fields is not available on
  stdlib dataclasses or `TypedDict`s.

### Validation engine

All schema types coerce and validate through pydantic's `TypeAdapter`:
`TypeAdapter(schema).validate_python(merged)`. This gives one engine and one
set of validation semantics across all supported types. There is no per-type
bespoke validator and no use of `model_validate` as the universal path. pydantic
is therefore a genuine, mandatory core dependency.

### Extension surface

The `SchemaAdapter` protocol and `confiq_get_schema_adapter` pluggy hook allow
new schema kinds to be registered without touching the core:

```python
class SchemaAdapter(Protocol[T]):
    def field_metadata(self) -> Mapping[str, list[Any]]: ...
    def validate(self, data: Mapping[str, Any]) -> T: ...
```

Adapters are resolved via the hook; `schema=None` selects the schemaless adapter
that returns a read-only `Mapping`.

### Consequences

- `load(schema, sources) -> T` is honest: the return type is the exact type the
  caller declared. `isinstance(config, YourType)` holds unconditionally.
- Callers who bring a frozen pydantic model get all guarantees. Callers who
  bring a stdlib dataclass get type safety and validation but not immutability
  or pydantic-grade secret masking — and the documentation says so.
- Third parties can add support for attrs, msgspec, or other schema kinds by
  registering a `SchemaAdapter` via the `confiq_get_schema_adapter` hook.

## Pros and Cons of the Options

### Option A: Frozen pydantic `BaseModel` only

- Good, because the contract is simple: one type, all guarantees, no gradient.
- Bad, because callers with existing dataclasses or `TypedDict`s must rewrite
  them — a barrier to adoption that has no technical justification given
  `TypeAdapter`'s multi-type support.
- Bad, because locking to one schema type forecloses the extension surface
  without offering any implementation simplification (pydantic `TypeAdapter`
  handles all types equally).

### Option B: Multiple schema types with explicit gradient (chosen)

- Good, because existing schemas work without modification — adoption is a
  configuration change, not a migration.
- Good, because the `TypeAdapter` engine is shared; no per-type validator to
  maintain.
- Good, because the gradient is an honest description of what confiq actually
  provides, not a marketing simplification.
- Neutral, because callers must understand which guarantees apply to their
  chosen schema type. The gradient table makes this a quick reference check.
