---
status: accepted
date: 2026-05-29
---
# Name the Source Protocol Method `fetch()`, Not `load()`

## Context and Problem Statement

The `Source` and `AsyncSource` protocols define a single method through which a
source delivers its raw data to the resolver. Two candidates for that method
name are `load()` and `fetch()`. The name matters because it appears in every
source implementation, every error message that names a source, and every piece
of documentation that explains how sources work.

## Decision Drivers

- `load()` is already the name of the primary public function in `confiq`. Using
  the same word for a structurally different abstraction — one orchestrates full
  config resolution and returns a validated model; the other retrieves raw data
  from one backend — creates ambiguity in error messages, documentation, and
  the mental model of both users and contributors.
- A source method name should describe precisely what that method does, without
  implying responsibility for validation, orchestration, or type coercion.
- The name should be neutral about transport mechanism — file I/O, network, and
  in-memory sources all implement the same protocol.

## Considered Options

- **`load()`** — familiar verb; matches what the method does from a data-flow
  perspective (data flows in).
- **`fetch()`** — equally common verb; unambiguous about transport direction;
  does not collide with the public API name.
- **`read()`** — considered briefly; implies file I/O specifically, which
  excludes network and in-memory sources semantically.

## Decision Outcome

Chosen option: **`fetch()`**, because it names what a source does — retrieve raw
data from a backend — without implying validation or orchestration, and without
colliding with `confiq.load()` at the reader level.

`read()` was rejected because it carries a file I/O connotation that is
inaccurate for `EnvSource`, `MemorySource`, and cloud sources.

`load()` was rejected because identical words at different abstraction levels
produce confusion proportional to how often the two levels appear together in
documentation and error output. They appear together constantly in confiq.

### Consequences

- Every source implementation in `confiq.sources` defines `fetch()`. Third-party
  sources conforming to the `Source` protocol do the same.
- Error messages that name a source method refer to `fetch()`, eliminating
  ambiguity with `load()` call-site errors.
- `confiq.load()` and `source.fetch()` can appear on the same line of
  documentation without requiring disambiguation prose.

## Pros and Cons of the Options

### `load()`

- Good, because callers can read "this source loads data" as natural English.
- Bad, because `confiq.load()` is the orchestration entry point. Two uses of the
  same word at different levels of abstraction compound in error messages:
  "load() called source.load(), which failed" is harder to parse than
  "load() called source.fetch(), which failed."
- Bad, because `load()` implies the method may perform validation or produce a
  final value — it does neither.

### `fetch()`

- Good, because it is unambiguous about what a source does: retrieve raw data
  from a backend, nothing more.
- Good, because it does not collide with `confiq.load()`, keeping the two
  abstraction levels lexically distinct.
- Good, because it is transport-neutral — equally appropriate for file I/O,
  HTTP, environment variables, and in-memory dicts.
- Neutral, because it is a slightly less common verb in pure Python library
  surfaces than `load`, though it is standard in HTTP and async contexts
  (`asyncio`, `urllib`, `httpx`).
