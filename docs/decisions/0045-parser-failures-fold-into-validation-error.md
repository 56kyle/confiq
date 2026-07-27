---
status: accepted
date: 2026-07-13
---
# Coerce-Step Parser Failures Fold into `ConfigValidationError`

## Context and Problem Statement

Stage 4's coerce step (`_apply_parsers`, design_d §6.2 step 5) applies each field's
`ConfigField.parser` to raw `str` leaves before validation. The first implementation let a
parser exception propagate raw: `ConfigField(parser=int)` fed `"notanint"` raised a bare
`ValueError` straight out of `resolve()`.

Every *other* failure mode in the resolver folds into the aggregated error contract
(ADR 0029): a `ConfigValidationError` (or `MissingConfigError`) carrying one
`ErrorContext(field_path, sources)` per failure, so the message names both the offending
field and the winning source (provenance, §6.4). Parser failure was the sole exception — and
it is arguably the mode where source attribution matters *most*, since the user wrote that
parser for that specific field and needs to know which source fed it the value the parser
choked on.

Three independent signals (the implementing dev, the test author, and the reviewer) flagged
the raw-exception behavior as an inconsistency rather than deliberate scoping.

## Decision Drivers

- **One failure contract (ADR 0029, design_d §13).** Parser application is coercion; its
  failure is the same category as pydantic's own coercion failures, which already map to
  `ConfigValidationError`. A caller should catch one taxonomy, not that plus arbitrary stdlib
  exceptions from user parsers.
- **Provenance on every failure (design_d §6.4).** "Which source supplied the bad value" is
  the resolver's signature diagnostic; dropping it for the one user-authored coercion path
  is the least defensible place to drop it.
- **Refusal over degradation (design_d §2).** The refusal must be *legible* — a bare
  `ValueError` with no field path is a degraded refusal.
- **Report everything (ADR 0029).** pydantic reports all validation failures in one raise;
  parser failures should likewise be collected across all fields, not fail-fast on the first.

## Considered Options

- **Option A (chosen): fold into `ConfigValidationError` now.** `_apply_parsers` catches each
  parser exception, collects all failures, and raises one `ConfigValidationError` with an
  `ErrorContext` per failed field.
- **Option B: keep raw, add a deferral ADR terminus.** Leave the raw exception but replace the
  test's "may be revisited" comment with a real ADR naming when it would be folded in.
- **Option C: keep raw as-is.** Treat a raising parser as user-code error surfacing natively.

## Decision Outcome

Chosen option: **Option A**. `_apply_parsers` regains a `provenance` parameter (stripped in the
original minimal signature — that removal was exactly what blocked the structured error) and:

- wraps each `field.parser(value)` in `try/except Exception` (a parser is arbitrary user code;
  `BaseException` — `KeyboardInterrupt`/`SystemExit` — still propagates);
- collects every `(field_path, exception)` rather than failing on the first;
- after the walk, if any failures exist, raises
  `ConfigValidationError(contexts, original=<first exception>)`, where each context is
  `ErrorContext(field_path, sources=_sources_for(provenance, field_path))` — the same
  provenance helper `_validate` uses.

**Ordering consequence (documented, not a defect):** coerce precedes validate, so a
parser-failed load reports parser errors and does *not* also report the downstream validation
errors those fields would have caused. This is consistent with pydantic's own behavior (a
field that fails to coerce is not separately re-reported for every constraint it also violates)
and keeps the failure set honest about what actually went wrong first.

### Consequences

**Positive:**
- A raising parser now surfaces as `ConfigValidationError` naming the field and winning source
   — uniform with pydantic coercion failures; callers catch one taxonomy.
- All parser failures across a load are reported in one raise (ADR 0029 fidelity).
- `_apply_parsers` is now the coerce step's own refusal locus, parallel to `_validate` being
  the validation step's — symmetric and legible.

**Negative:**
- `_apply_parsers` regains the `provenance` parameter the Stage 4 plan had trimmed for a
  minimal signature. Justified: the parameter is load-bearing for the error contract, so its
  absence was the smell, not its presence.
- A parser-failed field masks its own would-be validation error (ordering above). Acceptable
  and consistent with coerce-before-validate; the failed parser is the true first cause.

## Relationship to design_d and ADR 0029

Amends the Stage 4 coerce contract (design_d §6.2 step 5): parser failures are caught and
aggregated, not propagated raw. Extends ADR 0029's classification in spirit — parser failures
join validation failures under `ConfigValidationError` — though they are raised at the coerce
step and therefore not intermixed in the same context tuple as pydantic validation errors
(the ordering consequence above).
