---
status: accepted
date: 2026-07-07
---
# Adapter-Owned Secret-Masking Refusal with a Dedicated `SecretMaskingError`

## Context and Problem Statement

ADR 0033 decided that `ConfigField(secret=True)` on a schema kind that cannot honor
masking (e.g. `TypedDict`) must refuse at load rather than proceed unmasked, and closed
with an unresolved obligation: "adapters must be able to answer 'can this schema kind honor
masking?' — one more obligation on the adapter contract." Stage 2 implements the adapters,
so the *locus* of that refusal must be settled now — the `SchemaAdapter` Protocol as
stubbed has only `field_metadata()` and `validate()`, no seam for it.

Two things are undecided:

1. **Who owns the "can this kind mask?" knowledge** — the adapter, or the resolver?
2. **What exception the refusal raises.** ADR 0033 says `SchemaError`, but so does the
   "no adapter claims this schema" case (ADR 0030). Both funnel into one `SchemaError`,
   distinguishable only by message text.

## Decision Drivers

- **Plugin extensibility (ADR 0030).** The whole point of the adapter/hook design is
  order-independent, plugin-extensible schema support. If the resolver hardcodes the
  unmaskable set (`isinstance(adapter, TypedDictAdapter)`), a third-party adapter for a
  dict-like schema could never be recognized as unmaskable — the resolver would silently
  fail to protect it. The adapter is the thing that knows its own kind.
- **DRY.** The scan for `secret=True` fields is identical across kinds; duplicating it into
  four adapters (and every plugin) is needless. The *capability* is per-kind; the *scan* is
  shared.
- **Failures should be distinguishable by type, not message text** (operating ethos). A
  test that pins "`secret=True` on a `TypedDict` is refused" should not have to match a
  message substring to tell it apart from "unknown schema type."
- **Sequencing.** Detection needs the path table already built — it scans
  `field_metadata()` for `ConfigField(secret=True)` — so the check runs after the table
  exists and before/around `validate()`.

## Considered Options

- **Option A: Adapter declares a masking capability; a shared scan enforces it.** Add a
  boolean capability member (`masks_secrets`) to the `SchemaAdapter` Protocol. A shared
  helper scans the adapter's `field_metadata()` for any `ConfigField(secret=True)`; if any
  exist and `masks_secrets` is `False`, it raises.
- **Option B: The resolver hardcodes the unmaskable set** via `isinstance` against the
  concrete built-in adapter types.
- **For the exception:** (i) reuse plain `SchemaError`; (ii) add a dedicated
  `SecretMaskingError(SchemaError)`.

## Decision Outcome

Chosen: **Option A**, with a dedicated **`SecretMaskingError(SchemaError)`**.

- **Capability on the adapter.** `SchemaAdapter` gains a `masks_secrets: bool` capability
  member. Built-ins: `PydanticAdapter` and `DataclassAdapter` → `True` (native masking /
  confiq-touched `__repr__`, per §3 gradient); `TypedDictAdapter` → `False` (resolves to a
  plain dict, nowhere to hang a masked repr); `SchemalessAdapter` → `False` (a plain
  mapping cannot mask — though it has no fields, so the refusal is structurally
  unreachable, per ADR 0033/0038). Plugin adapters declare their own capability.
- **Kind label on the adapter.** The refusal message must name the schema *kind* (per
  ADR 0033's remediation obligation), and that label must be adapter-owned for the same
  extensibility reason the capability is — deriving it in the shared helper (e.g. a
  hardcoded map, or `type(adapter).__name__` which yields `"TypedDictAdapter"` rather than
  the remediation-grade `"TypedDict"`) would re-import concrete-type knowledge and exclude
  plugins. So `SchemaAdapter` also gains a `kind: str` member supplying the human label.
  This is a second required member beyond `masks_secrets`; see Consequences.
- **Shared enforcement.** A single helper in the adapter layer performs the scan-and-raise
  against `field_metadata()` + `masks_secrets`; the resolver calls it at load time (wired
  in the resolver stage). No per-adapter duplication.
- **Dedicated error.** The unmaskable-secret refusal raises `SecretMaskingError(SchemaError)`
  naming the field path, the schema kind, and the remediation (use a pydantic model or a
  stdlib/pydantic dataclass, or drop `secret=True`). The "no adapter claims this schema"
  case keeps plain `SchemaError`. `except SchemaError` still catches both; callers and
  tests can catch the specific one.

### Consequences

**Positive:**
- The unmaskable-secret refusal is plugin-extensible: any adapter, built-in or third-party,
  declares whether it can honor masking.
- The scan lives in exactly one place.
- The two `SchemaError`-family failures are distinguishable by type.

**Negative:**
- The `SchemaAdapter` Protocol gains two members every adapter (and plugin) must provide:
  `masks_secrets: bool` (the ADR 0033 "one more obligation") and `kind: str` (the
  human-readable label the refusal message needs, adapter-owned for extensibility). Both
  are trivial constants per adapter, so the burden is minimal — but the plugin contract
  grew by two, not one; recorded here so it is not a silent expansion.

Amends **ADR 0033** (specifies the refusal locus it left open) and relates to ADR 0030
(the shared plugin-extensible resolution) and ADR 0026 (the path table the scan reads).
