---
status: accepted
date: 2026-05-29
---
# Use `load()` Function Returning a Frozen BaseModel Instead of a Mutable Config Class

## Context and Problem Statement

`confiq` needs a primary entry point through which callers acquire configuration
values. The two realistic shapes for that entry point are: (a) a mutable object
whose state accumulates via builder calls, or (b) a pure function that accepts
everything it needs upfront and returns a complete, immutable value.

The predecessor design (Design A) used shape (a): a `Config` class with
`.add_dict()`, `.add_env()`, `.add_file()`, and a `.get("dotted.key")` method.
Callers built the object incrementally before reading from it.

## Decision Drivers

- Config values must be readable without risk of a missing-key error after the
  acquisition phase completes.
- Test isolation must be achievable without monkeypatching or resetting shared
  state.
- The read path must be fully typed — `config.database.host` should be `str`,
  not `Any`.
- Familiarity with the builder shape must not be a deciding factor if the
  tradeoffs favour the functional shape.

## Considered Options

- **Option A: Mutable `Config` builder class** — builder methods accumulate
  sources; `.get(key)` reads values; the object may or may not be frozen after a
  `.freeze()` call.
- **Option B: `load()` function returning a frozen pydantic `BaseModel`** — all
  sources declared at call time; the return value is a typed, immutable model
  instance.

## Decision Outcome

Chosen option: "Option B: `load()` function returning a frozen pydantic
`BaseModel`", because it eliminates the entire class of errors that arise from
reading config before all sources are applied, makes `Any` on the read path
structurally impossible, and allows test isolation without shared state.

### Consequences

- Config is a value in the same sense that a `datetime` or a `Path` is a value:
  it can be passed to functions, stored in dataclasses, compared structurally,
  and serialized. No special framework support is needed for any of these
  operations.
- Attribute access on the returned model cannot raise a `ConfiqError`. All
  errors are concentrated at the `load()` call boundary. Once `load()` returns,
  the value is safe to read unconditionally.
- Testing requires no monkeypatching. A fresh `load(Settings, sources=[MemorySource({...})])`
  call per test produces an isolated value from known inputs. Tests can run in
  any order and in parallel.
- Users who want module-level singleton ergonomics (`from myapp.config import
  config`) create that variable in their own module. confiq documents this
  pattern but does not own the variable.
- The builder's incremental nature, which some readers find familiar from
  `argparse.ArgumentParser` or `logging.basicConfig`, is not available. All
  sources must be known when `load()` is called. In practice this is not a
  constraint: sources are constructed from static configuration and environment
  context that is fully available at application startup.

## Pros and Cons of the Options

### Option A: Mutable `Config` Builder Class

- Good, because the builder is a familiar shape; readers who know `argparse` or
  `logging` understand it immediately.
- Good, because source addition can be conditional — callers can call
  `.add_file()` inside an `if` block before reading.
- Bad, because nothing prevents reading before all sources have been applied.
  A `.get()` call on a partially-built object returns a value that may be
  overridden by a later `.add_env()` call, and this is not detectable from the
  type signature.
- Bad, because `.get("dotted.key")` returns `Any` regardless of whether the
  schema declares the field as `str` or `int`. Every call site carries an
  implicit cast.
- Bad, because a mutable singleton in shared state requires monkeypatching or
  `.reset()` calls to isolate tests. Parallel test execution is unsafe without
  additional locking.
- Bad, because the boundary between "building" and "reading" is a convention,
  not a language invariant. `.freeze()` can enforce it at runtime but not at
  type-check time.

### Option B: `load()` Function Returning a Frozen `BaseModel`

- Good, because the boundary between acquisition and use is the function call
  itself — a language-level invariant, not a convention.
- Good, because the return type is fully known to the type checker. Attribute
  access is typed; there is no `Any` on the read path.
- Good, because the returned value is immutable by pydantic's `frozen=True`
  enforcement. No accidental mutation, no `.freeze()` ceremony.
- Good, because test isolation is free: each test constructs its own value from
  a `MemorySource`. No shared state exists to reset.
- Good, because the schema file does not need to import confiq. A plain pydantic
  `BaseModel` works without modification; confiq reads field metadata at load
  time via `typing.get_type_hints(schema, include_extras=True)`.
- Neutral, because conditional source inclusion requires an explicit `if` at the
  list construction site rather than a conditional method call. The behaviour is
  identical; the syntax is slightly more verbose.
- Bad, because callers must know all sources when they call `load()`. For
  applications where source availability is discovered lazily, this forces the
  discovery logic to complete before the `load()` call rather than during it.
  In practice this is not a real constraint for the addressed use cases.
