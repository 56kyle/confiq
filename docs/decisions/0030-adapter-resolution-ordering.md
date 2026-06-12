---
status: accepted
date: 2026-06-12
---
# Adapter Resolution: Precise Detection in Built-ins, User Plugins Win

## Context and Problem Statement

Schema adapters are resolved through the pluggy hook `confiq_get_schema_adapter` with
`firstresult=True`: the first hookimpl returning non-`None` wins. Nothing specifies the
registration order of the built-in adapters or whether user plugins
(`ResolutionSpec.plugins`) run before or after them — and pluggy calls hookimpls in
LIFO registration order, so both questions are currently decided by accident.

The hazard is concrete: a pydantic dataclass satisfies `dataclasses.is_dataclass()`, so
a naive `DataclassAdapter` hookimpl would claim it if called first — silently routing it
to the `get_type_hints(include_extras=True)` metadata path that design_d §4.4 explicitly
confines to stdlib types, instead of pydantic's `FieldInfo.metadata` path. Wrong-adapter
selection is not a crash; it is missed `ConfigField` metadata and different
forward-reference semantics.

## Decision Drivers

- Correct adapter selection must not depend on call order — order-dependent dispatch is
  fragile under exactly the extension mechanism (plugins) the hook exists for.
- "Can a user plugin override a built-in adapter?" is an extensibility contract that
  must be stated, not emergent.
- The schemaless case (`schema=None`) needs a defined owner.

## Considered Options

- **Option A: Positive precise detection in every built-in + user plugins registered
  last** — each hookimpl claims only schemas it is definitively correct for; pluggy's
  LIFO order then gives user plugins first refusal.
- **Option B: Documented priority order of broad-match adapters** — built-ins may
  overlap; a registration-order contract arbitrates.
- **Option C: Replace the hook with an ordered registry list** — bespoke dispatch,
  no pluggy.

## Decision Outcome

Chosen option: **Option A**, because precise detection makes correctness
order-independent (ordering then only expresses *preference*, never *correctness*), and
registering spec plugins last turns pluggy's LIFO behavior into the documented guarantee
that user plugins can override built-ins.

### Contract

- **Built-in detection is mutually exclusive by construction:**
  - `PydanticAdapter` claims `BaseModel` subclasses and pydantic dataclasses
    (`pydantic.dataclasses.is_pydantic_dataclass`).
  - `DataclassAdapter` claims stdlib dataclasses **and returns `None` for pydantic
    dataclasses** (checked via the same predicate).
  - `TypedDictAdapter` claims `TypedDict` classes (`typing.is_typeddict`, with the
    `typing_extensions` fallback on the 3.10 floor).
  - `SchemalessAdapter` claims exactly `schema is None`.
  - Every built-in returns `None` for anything else; an unclaimed schema raises
    `SchemaError` naming the schema type.
- **Registration order in `make_plugin_manager`:** built-ins first, then
  `ResolutionSpec.plugins` in list order. Under pluggy's LIFO call order, user plugins
  are consulted before built-ins, and later entries in `plugins` beat earlier ones.
  This is a documented public guarantee: *a spec plugin can override any built-in
  adapter, including for pydantic models.*

### Consequences

**Positive:**
- A pydantic dataclass always gets pydantic-native metadata handling regardless of
  registration churn.
- The override story is one sentence and is testable (register a plugin claiming
  `BaseModel`; assert it wins).
- Detection predicates are named library calls, not heuristics.

**Negative:**
- Built-in adapters must keep their predicates mutually exclusive as new schema kinds
  are added — a stated invariant the test suite must pin.
- A user plugin that *broadly* claims schemas shadows built-ins for everything; that is
  the granted power, documented rather than prevented.

## Pros and Cons of the Options

### Option A: Precise detection + plugins-last registration (chosen)

- Good, because correctness is order-free; order only encodes the user-override
  preference.
- Good, because it uses pluggy's native LIFO semantics instead of fighting them.
- Good, because each predicate is locally testable per adapter.

### Option B: Broad matches + priority contract

- Good, because individual hookimpls stay one-liner `isinstance`-ish checks.
- Bad, because correctness depends on a global ordering invariant no single module can
  see — the classic action-at-a-distance bug-farm.
- Bad, because user-plugin override semantics get tangled into the same ordering rules.

### Option C: Bespoke ordered registry

- Good, because dispatch is fully explicit.
- Bad, because it abandons the already-decided pluggy surface (§12.3,
  `confiq_get_schema_adapter`) and its third-party extension story for no added
  capability.
