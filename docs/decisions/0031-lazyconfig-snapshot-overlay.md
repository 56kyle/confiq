---
status: accepted
date: 2026-06-12
---
# LazyConfig Override Overlay Resolves a Full Validated Snapshot

## Context and Problem Statement

ADR 0019 / design_d §8.4 say the proxy "first checks the active `context.override()`
ContextVar; if an override is in scope it overlays it." The mechanism was unspecified,
and the obvious reading — intercept attribute access and substitute overridden values —
only works for the **first** attribute hop. `config.database.host` proxies
`__getattr__("database")`, which returns the real frozen `Database` instance; `.host` on
it bypasses the proxy entirely, so an override of `{"database": {"host": "x"}}` is
invisible. §11.3's whole proxy testing story ("the existing `config` fixture flows
straight through the proxy") rests on this mechanism working for nested access.

The candidate mechanisms each have problems: wrapping nested values in child proxies
propagates identity/`type()` edge cases to every nested model; returning raw override
dicts breaks typedness (`config.database` sometimes a dict); per-attribute substitution
breaks nested access as above.

## Decision Drivers

- Nested attribute access must see overrides — it is the common case
  (`config.database.host`), not an edge.
- Every read through the proxy must remain typed as the schema; an override must not
  change the *type* of anything a caller observes.
- An override is also subject to validation — a test overriding `port` with `"not-a-port"`
  should fail loudly at the validation boundary like any other source, not leak an
  unvalidated value into typed code.
- Proxy reads are a hot-ish path; per-access revalidation is unacceptable, but
  per-override-installation work is fine (overrides are test-scoped).

## Considered Options

- **Option A: Snapshot overlay** — when an override is active, resolve a full validated
  `T` from the base + override mapping via the spec's adapter; cache it per override
  mapping; forward all reads to it.
- **Option B: Per-attribute substitution** — intercept `__getattr__` and substitute
  overridden keys, recursing with child proxies for nested models.
- **Option C: Override must be a complete validated instance** — `override()` takes a
  full `T`, no merging.

## Decision Outcome

Chosen option: **Option A**, because it is the only mechanism where nested access,
typedness, and validation all hold simultaneously: the overlaid result *is* an ordinary
validated schema instance, so everything past the first hop is plain attribute access on
plain frozen values.

### Mechanism

When `_LazyProxy` finds `context.current_override()` non-`None`:

1. Deep-merge (the §6.3 `deep_merge`, list-replacement semantics) the override mapping
   over the bound base value's mapping form (pydantic `model_dump()` / `TypeAdapter`
   dump for other schema kinds).
2. Validate the merged mapping through the spec's `SchemaAdapter` into a fresh `T` —
   the same validation any source data receives. Validation failure raises
   `ConfigValidationError` at the read, naming the override as the source.
3. Cache the resolved snapshot keyed by the override mapping's identity (`id()` of the
   mapping installed by `override()` — installations are the cache key, so repeated
   reads inside one `override()` block validate once).
4. Forward the read to the snapshot. First hop through the proxy, everything deeper is
   ordinary frozen-value access.

With no active override, the proxy forwards to the bound base directly — production
reads stay one ContextVar check plus an attribute read (§8.4's stated cost).

First-hop-only interception (Option B's shape without recursion) is explicitly rejected
as a non-implementation of §8.4.

An override before `bind()` resolves against the spec-builder's sources without the CLI
layer if the design ever needs it — but the simple rule stands: reading an unbound proxy
raises "not bound" even under an active override **unless** pytest-confiq's `config`
fixture has established a base via `bind()` with test sources (§11.3's documented path).

### Consequences

**Positive:**
- `config.database.host` sees nested overrides; the §11.3 testing story is mechanically
  real.
- Overridden config is validated config — tests cannot accidentally inject values the
  schema would reject in production.
- Per-block validation cost only where overrides are used (tests); zero added cost on
  the no-override production path.

**Negative:**
- The proxy needs access to the spec's adapter and `deep_merge` at read time —
  `LazyConfig` holds the resolved spec, which it already does for `bind()`.
- Schema kinds without a rich dump (schemaless is already excluded from the proxy;
  `TypedDict` is a plain dict) degrade per the §3 gradient; the snapshot overlay is
  specified for the frozen-model path the proxy is built for.
- Two reads in the same override block return attributes of the same cached snapshot —
  consistent — but a mutation of the override mapping after installation is not
  observed. Override mappings are documented as immutable once installed.

## Pros and Cons of the Options

### Option A: Snapshot overlay (chosen)

- Good, because nested access, typedness, and validation hold with one mechanism.
- Good, because the cache makes cost per-installation, not per-read.
- Good, because "override = one more highest-precedence source" is conceptually exactly
  the resolver's existing merge semantics, reused.
- Bad, because it couples the proxy to the adapter (already held via the spec).

### Option B: Per-attribute substitution with child proxies

- Good, because no revalidation step.
- Bad, because child proxies propagate `type()`/identity/pickling edge cases to every
  nested model the user touches — multiplying §8.4's named cost (3) across the tree.
- Bad, because partial overrides skip validation entirely.

### Option C: Complete-instance overrides only

- Good, because trivially correct — the override is already a validated `T`.
- Bad, because it kills the ergonomic point: "production config but with this one value
  changed" (§11.2's layering requirement) would require constructing the full object in
  every test.
