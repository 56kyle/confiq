---
status: accepted
date: 2026-06-12
---
# `context.override()` Is a Data Overlay Consulted Only by the LazyConfig Proxy

## Context and Problem Statement

Two accepted artifacts disagree about `context.override()`'s contract:

- ADR 0016 says `context.override(sources)` "installs a scoped **source list**," and its
  autouse-isolation promise ("no environment variable or file source leaks in") only
  holds if `load()` itself consults the override.
- design_d §8.4/§11.2 and the skeleton (`context.py`:
  `override(data: Mapping[str, Any])`) describe a **data mapping** overlaid by the
  LazyConfig proxy on each read; nothing in the resolver consults the ContextVar.

The fork matters because it decides whether plain `load()` reads ambient state. The
design's second principle — "precedence is data, not magic" — and the §15 refusal of
hidden discovery argue that `load(schema, sources)` must be a pure function of its
arguments.

## Decision Drivers

- `load()`'s purity is the foundation of the testing story (§11.1): a value computed
  from explicit inputs needs no isolation machinery. An ambient hook in `load()` would
  re-import the very state-management problem the library exists to remove.
- The proxy (§8.4) is the one construct that *cannot* take config as a parameter — its
  reads are ambient by design — so it is the one legitimate consumer of a scoped
  ambient override.
- Test isolation from environment variables is achievable without intercepting
  `load()`: scrub `os.environ` itself (Rust Figment's `Jail` pattern, ADR 0016's own
  stated model).
- §11.2 requires "cheaply splicing or overriding a single key in an existing source
  list"; that capability needs a home that is explicit data flow, not ambient state.

## Considered Options

- **Option A: Data-mapping overlay, proxy-only** — `override(data)` is read by
  `_LazyProxy` (per ADR 0031's snapshot semantics); `load()` never reads it; splicing is
  a pure helper over `ResolutionSpec`.
- **Option B: Source-list override consulted by `load()`** — ADR 0016 as written;
  the autouse fixture swaps source lists out from under direct `load()` calls.
- **Option C: Both primitives** — a data overlay for the proxy and a separate
  source-list override consulted by `load()`.

## Decision Outcome

Chosen option: **Option A**, because it keeps `load()` a pure function of its arguments
(principle 2), confines ambient behavior to the one construct that is ambient by design,
and still delivers test isolation through environment scrubbing and explicit source-list
construction.

### Contract

```python
context.override(data: Mapping[str, Any])        # sync context manager
context.async_override(data: Mapping[str, Any])  # async context manager
context.current_override() -> Mapping[str, Any] | None
```

- The payload is a (possibly nested, possibly partial) **data mapping**, not sources.
- The only core reader is `_LazyProxy` (snapshot-overlay semantics, ADR 0031).
- `load()` / `load_async()` / `ConfigHandle.reload()` never consult the ContextVar.

### Source-list splicing is explicit data flow

The §11.2 requirement is met by a pure helper, not ambient state:

```python
def spec_with(spec: ResolutionSpec[T], overrides: Mapping[str, Any]) -> ResolutionSpec[T]:
    """Return a new spec with a MemorySource(overrides) appended at highest precedence."""
```

`pytest-confiq`'s layering helpers are sugar over `spec_with`.

### pytest-confiq isolation mechanism (amends ADR 0016)

The autouse isolation fixture isolates the *inputs*, not the loader: it scrubs
`os.environ` (Jail-style, via monkeypatch-equivalent machinery) and chdirs to a tmp path
so `EnvSource`/`FileSource` find nothing unless a test adds data explicitly. ADR 0016's
`override(sources)` wording is superseded by this contract; everything else in ADR 0016
(plugin packaging, fixture surface, thinness rule) stands.

### Consequences

**Positive:**
- `load()` remains referentially transparent; no hidden control flow in the core path.
- One ambient mechanism in the library instead of two, with one documented reader.
- The proxy testing story (§11.3) is unchanged — it was specified against the data
  overlay already.

**Negative:**
- Code that calls `load()` directly inside a test is not affected by
  `context.override()` — by design. Tests of such code pass sources explicitly (the
  §11.1 story) or use `spec_with`. This is a real, documented asymmetry between the
  value path and the proxy path.
- Env isolation by scrubbing is process-global rather than task-scoped; parallel async
  tests that mutate the environment were already unsupportable, so nothing is lost.

## Pros and Cons of the Options

### Option A: Data overlay, proxy-only (chosen)

- Good, because it preserves `load()`'s purity — the library's core differentiator.
- Good, because the ambient surface is minimal and matches the one ambient construct.
- Good, because skeleton, design_d §8.4/§11.3, and ADR 0019/0031 already assume it.
- Bad, because direct-`load()` callers get no ambient override (mitigated: they do not
  need one — they control their inputs).

### Option B: Source-list override consulted by `load()`

- Good, because autouse isolation would also catch direct `load()` calls.
- Bad, because `load(schema, sources)` would no longer mean what it says — a hidden
  ContextVar could replace the caller's explicit list, violating principle 2 exactly
  where the library promises it most.
- Bad, because it contradicts design_d §8.4/§11.3 and the skeleton, requiring a larger
  respecification than the contract it fixes.

### Option C: Both primitives

- Good, because maximum capability.
- Bad, because two ambient mechanisms with different payloads and different readers is
  the confusion this ADR exists to resolve, doubled.
