---
status: accepted
date: 2026-05-29
---
# Exclude `confiq_transform_value` Hook from v1.0

## Context and Problem Statement

During the design of confiq's plugin system, a `confiq_transform_value` hook was
specified to allow plugins to transform per-field values after source merging but
before pydantic validation. The intended use cases were cross-cutting transforms —
secret decryption, base64 decoding — that apply to many fields based on their
metadata (e.g. `secret=True`) without requiring the caller to annotate every
field with a `parser`.

The hook was specified in `ConfiqSpecs` and documented in the design reference,
but never wired into the resolution pipeline. By the time v1.0 reached code
review, the hook existed as a no-op specification with a comment in `_load.py`
noting it was "not driven inline in v1." No timeline or wiring plan existed.

The question is whether to ship the hook as a defined-but-unimplemented
specification, implement it now, or remove it until a real use case drives it.

## Decision Drivers

- The two motivating examples are already served without the hook. Secret
  decryption is handled at the source layer: AWS, GCP, Azure, and Vault sources
  all return plaintext from their respective KMS or secret manager APIs.
  Per-field base64 decoding is three words on the affected field:
  `ConfigField(parser=base64.b64decode)`.
- The only genuine gap is cross-cutting transforms that apply to many fields
  based on metadata. That pattern is real but speculative: no current user or
  plugin author has requested it.
- Wiring the hook requires threading the plugin manager (`pm`) into `_resolver.py`,
  which currently has no plugin system dependency. That coupling has a cost and
  must justify itself against a concrete use case.
- A defined-but-unimplemented hook creates a silent contract violation: a plugin
  author who registers `confiq_transform_value` today receives no error and no
  effect. The failure mode is invisible.
- The hook fires between `field.parser` and pydantic validation. Plugin authors
  must understand the pre-validation data shape to implement it correctly. That
  contract needs real-world usage to stabilise before it is documented as a
  supported surface.

## Considered Options

- **Option A: Keep defined but unimplemented** — ship the hookspec in
  `ConfiqSpecs`; wire it in a future minor version.
- **Option B: Remove until a concrete use case drives it** — delete the
  hookspec; revisit when a plugin author or user requests the capability.
- **Option C: Implement now** — wire the hook in the resolution pipeline so that
  after `field.parser` and before pydantic validation, registered implementations
  are called in `firstresult` order.

## Decision Outcome

Chosen option: "Option B: Remove until a concrete use case drives it", because
no current use case requires the hook, the existing tools (`ConfigField.parser`
and source-layer decryption) cover the stated examples, and shipping a
permanently silent hook is a worse outcome than shipping without it.

### Consequences

- `confiq_transform_value` is removed from `ConfiqSpecs`. Plugin authors who
  attempt to register an implementation receive a pluggy `AttributeError` rather
  than silent no-ops.
- `ConfigField.parser` remains the supported path for per-field value
  transformation.
- When a real use case arrives, the hook can be re-introduced. The design is
  straightforward: `firstresult=True`, fires after `field.parser`, receives
  `(field_path, raw_value, field_info)`, returns the replacement value or `None`
  to pass. The main open question — where exactly `pm` is threaded in — will be
  answered by the specific wiring context at that time.

## Pros and Cons of the Options

### Option A: Keep Defined but Unimplemented

- Good, because plugin authors can write implementations against the spec today
  and have them work when wiring lands without changing their code.
- Bad, because any plugin that registers the hook today silently does nothing.
  The failure mode is invisible and produces no diagnostic.
- Bad, because "later" is undefined. Without a named terminus the hook becomes
  permanent dead code that future contributors must rediscover.
- Bad, because the inline comment required to explain the absence is itself a
  code smell that signals unresolved design work.

### Option B: Remove Until Needed

- Good, because the public API surface is honest: every specified hook does
  something. Plugin authors who attempt to register an unrecognised hook get an
  explicit error.
- Good, because `_resolver.py` retains zero plugin system coupling. Its contract
  stays narrow and testable in isolation.
- Good, because the decision not to include the hook is explicit and documented,
  rather than implied by a comment.
- Neutral, because re-introducing the hook later is a minor addition. The
  `firstresult` hookspec pattern is established; the design is understood.

### Option C: Implement Now

- Good, because the hook does what it says. The stepping-stone ambiguity and the
  inline comment disappear.
- Good, because the cross-cutting transform use case becomes available to plugin
  authors immediately.
- Bad, because no current use case justifies the added coupling between
  `_resolver.py` and the plugin manager.
- Bad, because the pre-validation data contract that plugin authors must
  understand to use the hook correctly is unstabilised. Shipping it without real
  users means designing the contract in a vacuum.
