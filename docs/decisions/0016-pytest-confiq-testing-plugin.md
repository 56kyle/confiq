---
status: accepted
date: 2026-06-05
---
# First-Class Testing via a `pytest-confiq` Companion Plugin

> Amended by [ADR 0028](0028-context-override-data-overlay-proxy-only.md):
> `context.override()` takes a **data mapping** read only by the LazyConfig proxy, not a
> source list read by `load()`; the autouse isolation fixture works by scrubbing
> `os.environ` (Jail-style) rather than intercepting `load()`, and layering helpers are
> sugar over the pure `spec_with()` helper. The packaging and fixture-surface decisions
> below stand.

## Context and Problem Statement

design_d §11.

Testing code that uses a configuration library is notoriously awkward. The
canonical pain: a `pydantic-settings` singleton must be monkeypatched into
shape before each test, environment variables must be set and cleaned up, and
any test that forgets to restore state can poison subsequent tests — especially
under parallel execution.

`confiq`'s core design (configuration is a plain value, not an object with
global identity) eliminates the monkeypatching problem by construction. But
callers still need ergonomic primitives to:

- construct a config value from known test data without repeating
  `load(Settings, sources=[MemorySource({...})])` in every test;
- prevent environment variables and file sources from leaking into tests;
- override a single value in an otherwise complete source stack;
- work correctly in async tests where multiple tasks may need different config
  values concurrently.

The question is whether to ship these ergonomics in the core library or as a
separate pytest plugin.

## Decision Drivers

- The core primitives (`MemorySource`, `context.override()`) must be ergonomic
  on their own — the plugin must not be required for basic testing.
- pytest-specific concerns (fixtures, markers, autouse isolation) do not belong
  in the core library, which has no pytest dependency.
- A companion plugin can evolve independently without coupling pytest fixture
  API choices to core release cycles.
- Modelling on Rust Figment's `Jail` pattern — a per-test isolated environment
  that resets automatically — gives a well-understood reference point.

## Considered Options

- **Option A: Pytest fixtures in the core library** — `confiq` depends on
  pytest as an optional extra and ships fixtures directly.
- **Option B: `pytest-confiq` companion plugin** — a separate package that
  depends on both `confiq` and `pytest`, containing only fixture and isolation
  machinery.
- **Option C: Document the manual pattern only** — no plugin; callers write
  `load(Settings, sources=[MemorySource({...})])` themselves.

## Decision Outcome

Chosen option: **Option B: `pytest-confiq` companion plugin**, because it keeps
pytest out of confiq's dependency graph, allows the fixture API to evolve
without core releases, and ships the ergonomics the design promises without
coupling them to the core.

### Core primitives the plugin builds on

Two primitives in the core library must be ergonomic for the plugin to stay thin:

1. **`MemorySource(mapping)`** — an in-process source that contributes a
   known mapping. The testing workhorse: `load(Settings, sources=[MemorySource({...})])`.

2. **`context.override(sources)`** — a `ContextVar`-based context manager
   (and async context manager) that installs a scoped source list for the
   duration of a `with` block. Async-safe: each `asyncio` task sees its own
   override, consistent with `ContextVar` propagation semantics. This is what
   makes per-task config isolation in async tests possible.

### What the plugin provides

- **`config` fixture** — builds a config value from a `MemorySource` base;
  overridable per test via a `confiq_overrides` fixture or parametrize marker.
- **Autouse isolation fixture** — wraps each test in a `context.override()`
  so no environment variable or file source leaks in unless explicitly added.
  What `monkeypatch.setenv` + cleanup otherwise forces by hand.
- **Layering helpers** — `with_overrides(sources=[...])` lets a test say
  "the production source stack, but with this one value replaced" without
  rebuilding the full list.
- **Async support** — fixtures are `anyio`-compatible; `context.override()`
  provides per-task isolation in async tests.

### Consequences

- The core library has no pytest dependency. Users who do not use pytest
  install nothing extra.
- `pytest-confiq` installs as `pip install confiq[test]` (or separately
  as `pip install pytest-confiq`) and auto-registers via pytest's plugin
  discovery.
- The plugin is deliberately thin: it adds fixture wiring around `MemorySource`
  and `context.override()`. No business logic belongs in the plugin.
- If the core primitives are not ergonomic enough for the plugin to stay thin,
  that is a signal to improve the core, not to put logic in the plugin.

## Pros and Cons of the Options

### Option A: Fixtures in the core library

- Good, because there is one package to install.
- Bad, because pytest becomes a (optional) core dependency, complicating the
  dependency matrix for users who use a different test runner.
- Bad, because pytest fixture API decisions (autouse, parametrize markers,
  `anyio` integration) become coupled to confiq core release cycles.

### Option B: `pytest-confiq` companion plugin (chosen)

- Good, because the core library has zero test-runner dependency.
- Good, because the plugin can update its pytest/anyio integration
  independently.
- Good, because the separation makes the boundary explicit: primitives in core,
  ergonomics in the plugin.
- Neutral, because users must install a second package for the fixtures. The
  extra is clearly documented and the `confiq[test]` shorthand makes it a
  one-word addition.

### Option C: Document the manual pattern only

- Good, because no additional code ships in confiq or a companion.
- Bad, because the autouse isolation fixture and layering helpers require
  non-trivial boilerplate that every confiq user would duplicate independently.
  Shipping the plugin is the correct abstraction for repeated boilerplate.
