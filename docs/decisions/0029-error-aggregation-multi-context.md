---
status: accepted
date: 2026-06-12
---
# Config Errors Aggregate Multiple `ErrorContext`s

## Context and Problem Statement

§4.5 mandates one validation engine: `TypeAdapter(schema).validate_python(merged)`.
pydantic's `ValidationError` aggregates **all** failures — N field paths in one raise.
But ADR 0025's `ErrorContext(field_path, sources)` is singular, `ConfigValidationError`
holds exactly one, and §6.2 step 6 says the error carries "the field path." As specified,
confiq could report only the first of N errors — a regression versus raw pydantic, whose
all-errors-at-once reporting is one of its best diagnostics.

Nothing yet specifies how the resolver decides between `MissingConfigError` and
`ConfigValidationError` when both kinds of failure (missing fields and invalid values)
arrive in the same `ValidationError`.

## Decision Drivers

- Reporting every failure in one raise is strictly better diagnostics and is what the
  underlying engine already produces; discarding it would be a deliberate loss.
- `err.field_path` / `err.sources` are already-published forwarding properties
  (ADR 0025); their meaning for multi-error exceptions must be defined, not left to
  accident.
- One raise per `load()` call: callers should never need to loop, re-validate, or catch
  two exception types for one failed load.
- A `tuple[ErrorContext, ...]` maps to `Vec<ErrorContext>` (ADR 0021 tiebreaker).

## Considered Options

- **Option A: `contexts: tuple[ErrorContext, ...]` on both errors; classify by
  homogeneity** — all-missing → `MissingConfigError`; anything else →
  `ConfigValidationError` carrying every context (missing ones included).
- **Option B: Keep single-context errors; raise on the first pydantic error** —
  ADR 0025 as written.
- **Option C: Raise an `ExceptionGroup` of single-context errors.**

## Decision Outcome

Chosen option: **Option A**, because it preserves pydantic's full diagnostic yield in
one exception, keeps the two-class taxonomy meaningful (`MissingConfigError` = "your
sources are incomplete", `ConfigValidationError` = "your sources are wrong"), and keeps
`except ConfiqError` handling flat.

### Shape (amends ADR 0025)

```python
class MissingConfigError(ConfiqError):
    def __init__(self, contexts: Sequence[ErrorContext]) -> None: ...
    @property
    def contexts(self) -> tuple[ErrorContext, ...]: ...
    @property
    def field_path(self) -> str: ...   # forwards to contexts[0].field_path
    @property
    def sources(self) -> Sequence[str]: ...  # forwards to contexts[0].sources

class ConfigValidationError(ConfiqError):
    def __init__(self, contexts: Sequence[ErrorContext], *, original: Exception | None = None) -> None: ...
    # same contexts / field_path / sources surface
```

- **Classification rule.** Map each pydantic error line to an `ErrorContext`
  (`field_path` = dot-joined `loc`, matching the ADR 0026 key space; `sources` = the
  provenance entries for that path). If **every** error has pydantic
  `type == "missing"`, raise `MissingConfigError(contexts)`; otherwise raise one
  `ConfigValidationError(contexts)` carrying all contexts, missing and invalid alike.
- **Forwarding semantics.** `field_path`/`sources` forward to `contexts[0]` — the
  first error in pydantic's stable reporting order — so existing single-error call
  sites and messages keep working. The human-readable message always renders *all*
  contexts; the singular properties are a convenience, not the report.
- `contexts` is non-empty by construction (constructing either error with zero
  contexts is a programming error and raises `ValueError`).

### Consequences

**Positive:**
- A failed load reports every problem at once, with per-field provenance — the §6.4
  promise at full fidelity.
- The all-missing case keeps its distinct, actionable type.
- Existing `err.field_path` call sites need no change.

**Negative:**
- Mixed missing+invalid failures surface as `ConfigValidationError`, so a handler
  catching only `MissingConfigError` will not see missing fields when an invalid value
  co-occurs. Documented: catch `ConfiqError` (or both) for completeness; per-context
  classification is recoverable from pydantic's `original` if ever needed.
- `field_path` on a multi-error exception names only the first failure. Acceptable
  because the property is a single-error convenience and the message carries the rest.

## Pros and Cons of the Options

### Option A: Aggregate contexts, classify by homogeneity (chosen)

- Good, because no diagnostic information is discarded.
- Good, because one raise, one flat `except`, one evolution point (`ErrorContext`).
- Good, because the dot-joined `loc` ties errors into the ADR 0026 key space and the
  provenance map directly.
- Bad, because the missing-vs-invalid taxonomy blurs in the mixed case (mitigated by
  documentation and by every context being present in the one exception).

### Option B: First error only

- Good, because no API change from ADR 0025.
- Bad, because fix-one-rerun-find-the-next loops are a known developer-experience
  failure, and the engine already computed the full list.

### Option C: `ExceptionGroup`

- Good, because each context keeps its own exception class.
- Bad, because `except*` handling is unfamiliar, awkward on the 3.10 floor
  (`exceptiongroup` backport), and heavier for the dominant single-error case.
- Bad, because callers want one structured report, not N exceptions to traverse.
