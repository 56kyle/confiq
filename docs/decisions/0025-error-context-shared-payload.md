---
status: accepted
date: 2026-06-07
---
# `ErrorContext` Extracts the Shared Diagnostic Payload from Config Errors

## Context and Problem Statement

`MissingConfigError` and `ConfigValidationError` both carry:

```python
field_path: str
sources: Sequence[str]
```

The duplication is tolerable at two fields. It becomes a maintenance liability
once the diagnostic payload is expected to grow: structured provenance detail
in error messages, secret-masking (suppressing source values for fields marked
`secret=True`), and machine-readable structured error output are all natural
extensions. Each extension would need to be added to both error classes
independently.

Extracting a named `ErrorContext` dataclass gives the payload a single
evolution point, makes it passable and inspectable as a standalone value, and
aligns with the multi-value boundary naming principle (ADR 0023): `field_path`
and `sources` are correlated because they express the same diagnostic concept
— "which field, from which sources, failed."

## Decision Drivers

- The two fields are correlated because they jointly describe a diagnostic
  event. They belong together structurally, not just by convention.
- A named frozen dataclass maps to a Rust struct (ADR 0021); a mixin maps to
  a trait with fields — a weaker concept that is harder to pass around as a
  value or reference as a standalone type.
- Forwarding properties (`err.field_path`, `err.sources`) on both error
  classes preserve the existing public API with no call-site churn.
- **Deferability note.** If the payload were frozen at two fields with no
  expected growth, a shared `_DiagnosticMixin` would suffice. The growth
  expectation is what tips the decision toward a named struct now rather than
  deferring.

## Considered Options

- **Option A: `ErrorContext(field_path, sources)` frozen dataclass** — held as
  an attribute on both error classes; forwarding properties expose
  `err.field_path` and `err.sources`.
- **Option B: `_DiagnosticMixin` base class** — shared `field_path` and
  `sources` attributes defined once in a mixin; both error classes inherit it.
- **Option C: Status quo** — `field_path` and `sources` declared separately
  on each error class.

## Decision Outcome

Chosen option: **Option A**, because a standalone named dataclass is
passable, inspectable, and a natural home for future diagnostic payload growth,
whereas a mixin is coupled to the inheritance chain and harder to reference as
an independent value.

### Shape

```python
@dataclass(frozen=True)
class ErrorContext:
    field_path: str
    sources: Sequence[str]
```

Both `MissingConfigError` and `ConfigValidationError` hold an `ErrorContext`
instance and expose forwarding properties:

```python
class MissingConfigError(ConfiqError):
    context: ErrorContext

    def __init__(self, field_path: str, sources: Sequence[str]) -> None:
        self.context = ErrorContext(field_path, sources)

    @property
    def field_path(self) -> str:
        return self.context.field_path

    @property
    def sources(self) -> Sequence[str]:
        return self.context.sources
```

The public API (`err.field_path`, `err.sources`) is unchanged.

### Consequences

**Positive:**
- The diagnostic payload evolves in one place. Adding provenance detail,
  secret-masking flags, or a structured representation requires one change
  to `ErrorContext`, not two changes to two error classes.
- `ErrorContext` is passable as a value — an error reporter, logger, or
  formatter can accept `ErrorContext` directly without needing the full
  exception object.
- Forwarding properties ensure no existing call site breaks.

**Negative:**
- Error construction gains one indirection: `ErrorContext(field_path, sources)`
  is created inside `__init__`. For callers constructing errors directly, the
  signature is unchanged.

## Pros and Cons of the Options

### Option A: `ErrorContext` frozen dataclass (chosen)

- Good, because the payload is a standalone named type — passable, inspectable,
  and directly referenceable in docs, formatters, and future serialisation.
- Good, because it maps to a Rust struct (ADR 0021 tiebreaker).
- Good, because forwarding properties preserve the existing `err.field_path` /
  `err.sources` API.
- Good, because future payload growth touches one type instead of two.
- Neutral, because both error classes now hold a `context` attribute. Callers
  that want the raw `ErrorContext` can use `err.context`; others use the
  forwarding properties.

### Option B: `_DiagnosticMixin` base class

- Good, because the two attributes are defined once and inherited.
- Bad, because a mixin is coupled to the class hierarchy — it cannot be passed
  around as a standalone value without the error object.
- Bad, because mixins are a weaker pattern for growing a shared payload:
  adding a method or derived property requires the mixin to import things it
  may not otherwise need.
- Bad, because it maps to a trait with fields in Rust, not a struct — a harder
  concept to represent cleanly.

### Option C: Status quo

- Good, because no change is required now.
- Bad, because the next payload extension (provenance detail, secret-masking)
  requires editing both error classes in parallel, creating drift risk.
- Bad, because `field_path` and `sources` have no named concept — they are
  coincidentally identical rather than explicitly shared.
