---
status: accepted
date: 2026-07-13
---
# CLI Binding Reorders the Resolver: Adapter-Before-Merge, a Bind Step, and a Widened Boundary

## Context and Problem Statement

ADR 0027 makes CLI sources surface **raw parameter names + binding markers** (`ConfigBind`, or a
generated option's `confiq_path`), with the **resolver** mapping names → config paths against the
schema path table — because binding needs the schema, which the source does not have. ADR 0032
confirms `fetch()` replays that raw snapshot. But the current shared resolver core
(`_resolve_from_fetched`, design_d §6.2) runs **merge first**, then resolves the adapter, then
coerces — so the path table (`adapter.field_metadata()`) does not exist until *after* merge, and a
CLI source's raw `database_host` key would merge as a *distinct* leaf from a file's `database.host`,
so the highest-precedence CLI override silently lands at the wrong key and never wins.

Binding therefore has to happen *after* the adapter (needs the path table) and *before* merge (so
raw names become config paths before precedence and provenance are computed). This reshapes the
§6.5 named-boundary types and the §6.2 step order.

## Decision Drivers

- **Correct precedence.** A CLI-bound value must occupy the *same* leaf as a file/env value at that
  path, or merge cannot resolve the collision. That requires config-path shape before merge.
- **Provenance for free.** If binding rewrites the CLI source's entry into config-path shape
  *before* merge, merge/provenance work unchanged and a CLI-bound value records the CLI source as
  its origin in errors — no special-casing.
- **No color drift (ADR 0035).** Binding must live in the shared color-agnostic core, not in the
  per-color fetch step, or sync and async grow a hand-maintained twin.
- **The adapter does not depend on merged data.** `resolve_schema_adapter(manager, schema)` needs
  only `schema` + `plugins`, so moving it before merge introduces no new coupling.

## Decision Outcome

Reorder the shared core `_resolve_from_fetched` from `merge → adapter → coerce → validate` to:

```
adapter (resolve + path table) → BIND binding-source entries into config-path shape → merge → coerce → validate
```

- **`BindingSource` protocol.** A structural protocol the resolver `isinstance`-detects. A binding
  source surfaces raw external names + markers (rather than config-path data); the resolver binds
  them. Normal sources (`MemorySource`, `FileSource`, `EnvSource`) are unaffected and continue to
  emit config-path data merged directly.
- **Widened boundary.** `FetchedEntry` gains a sibling (or a widened form) able to ferry raw
  name → (value, marker) plus the "needs binding" signal from fetch into the core. This is a §6.5
  named-boundary change, made deliberately.
- **The bind step** resolves each raw name to a config path: an explicit marker
  (`confiq_path` > `ConfigBind`) wins; otherwise the ADR 0027 convention (candidate dottings ∩
  path-table leaf paths; exactly one binds; **> 1 → `SchemaError`** naming candidates; **0 → the
  parameter does not participate**). `ConfigBind(None)` opts a matching parameter out. The bound
  entry is rewritten into config-path shape, then merged normally.
- **Shared path-table validation.** Env/dotenv `aliases` (ADR 0048) declare config-path *targets*
  the user writes directly; the resolver validates those targets against the path table in the
  same phase (unknown target → `SchemaError`), so a typo'd alias fails loudly rather than silently
  dropping under `extra="ignore"`. Env/dotenv translation itself stays source-side and
  schema-blind; only target *validation* is resolver-side.
- Binding remains in the color-agnostic core, so `resolve()` and `resolve_async()` stay drift-free.

### Consequences

**Positive:**
- CLI precedence and provenance are correct and require no merge/provenance changes.
- One bind phase serves CLI convention, explicit `ConfigBind`/`confiq_path`, and env/dotenv
  alias-target validation — all "resolve/validate a claimed config path against the path table."
- Adapter-before-merge is a clean reorder (no new dependency).

**Negative:**
- A §6.5 boundary type changes and the core gains a stage — more moving parts in the resolver's
  most load-bearing function. Justified: binding cannot be correct anywhere else.
- The resolver now `isinstance`-checks a source protocol, a small amount of source-type awareness
  in the core (confined to "does this entry need binding?").

## Considered Options

- **Option A (chosen): bind-before-merge with adapter moved up; widened boundary.**
- **Option B: bind inside the per-color fetch step.** Rejected: forces adapter resolution across
  the sync/async split — the exact drift ADR 0035 forbids.
- **Option C: bind post-merge and re-place values.** Rejected: redoes precedence by hand after
  merge already computed it, and loses clean provenance.

## Relationship to design_d and other ADRs

Implements the fetch/resolve split ADR 0027 mandated and ADR 0032 assumed. Updates design_d §6.2
(step order) and §6.5 (boundary types). Preserves ADR 0035 (color-agnostic core) and ADR 0043
(retained snapshot). Provides the shared path-table validation env/dotenv aliases need (ADR 0048).
