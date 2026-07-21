---
status: accepted
date: 2026-06-12
---
# CLI Sources Snapshot Their Context Eagerly; `fetch()` Is a Pure Replay

## Context and Problem Statement

`ClickSource`/`TyperSource` read the active Click `Context` — ambient state
(`click.get_current_context()`) in a library whose principles are otherwise strictly
explicit. The skeleton says the context is captured "at construction time," but the
lifecycle is unspecified, and it collides with reload: a CLI source stored in a
`ResolutionSpec` inside a `ConfigHandle` or `LazyConfig` is re-fetched on every
`reload()` — potentially long after the Click context has unwound. Does `fetch()` hold a
live `Context` (keeping the context graph alive), re-resolve ambiently (`RuntimeError`
post-command), or replay a snapshot?

A second gap: `options_from`-generated commands build `click.Option` objects
imperatively, so there is no function annotation to carry `ConfigBind` — where does
binding metadata live for generated options?

## Decision Drivers

- Reload determinism: `ConfigHandle.reload()` exists to re-read *changeable* sources
  (files, env); the CLI invocation that started the process cannot change, so its
  contribution should be stable across reloads, not error or drift.
- No retained live framework objects: holding a `Context` pins the whole Click context
  graph (command, params, parent contexts) for the process lifetime of the spec.
- The ambient `get_current_context()` grab is unavoidable for the consumer path's
  ergonomics (`TyperSource()` with no arguments inside a command body); it should be
  confined to one well-named moment.
- Generated options must round-trip the ADR 0027 convention without annotations.

## Considered Options

- **Option A: Eager snapshot at construction** — the constructor reads everything it
  needs from the context into an immutable mapping; `fetch()` replays it; no `Context`
  reference survives construction.
- **Option B: Hold the `Context`; fetch lazily** — `fetch()` reads the live context
  each time.
- **Option C: Re-resolve `get_current_context()` inside every `fetch()`.**

## Decision Outcome

Chosen option: **Option A**, because it makes the CLI source a frozen fact about the
invocation — deterministic under reload, holding no framework objects — and confines the
ambient grab to the constructor, the one place the user visibly wrote `TyperSource()`.

### Contract

At construction, `ClickSource` (and `TyperSource`, which shares the mechanism since
Typer's context is a Click context — **premise falsified by typer 0.26.0's vendored Click;
acquisition amended by ADR 0054, snapshot contract below unchanged**):

1. Calls `click.get_current_context()` — raising `RuntimeError` with a clear message if
   no Click invocation is active (already specified), and `ImportError` with an install
   hint if click is absent. **(Amended by ADR 0054: the context is acquired from an
   ordered list of provider modules — Typer's vendored stack first for `TyperSource` —
   with the same failure modes.)**
2. Reads, for every parameter: its value, whether it was explicitly set
   (`ctx.get_parameter_source()` not in {`DEFAULT`, `DEFAULT_MAP`}), and its binding
   marker (`ConfigBind` from the command callback's annotations, or the attached path
   for generated options — below).
3. Stores the explicitly-set parameters and their markers as an immutable mapping.
   **No reference to the `Context` survives `__init__`.**

`fetch()` returns the snapshot (raw parameter names + markers; path mapping happens in
the resolver against the ADR 0026 path table per ADR 0027). Every call returns the same
data: reloads re-read files and env, while the CLI layer replays the invocation that is
still, in fact, the invocation.

**Generated options carry their path.** `options_from(schema)` sets the dotted path on
each emitted option object (a `ConfiqOption(click.Option)` subclass with a
`confiq_path: str` attribute). The snapshot step prefers `confiq_path` over annotations
over convention — the same precedence on both the consumer and generator paths.

### Consequences

**Positive:**
- Reload behavior is defined and deterministic; no post-command `RuntimeError`s, no
  retained context graphs.
- The ambient grab happens exactly where the user wrote the constructor call, inside an
  active command — the documented exception to the explicitness ethos, confined to one
  line.
- Generated options need no annotation machinery, and the binding metadata travels on
  the object that defines the option.

**Negative:**
- A `ClickSource` constructed in one command cannot observe a *different* later
  invocation — true by construction and correct: one process, one parse.
- The constructor does nontrivial work (full parameter sweep). Acceptable: it runs once
  per invocation and replaces equivalent work in every `fetch()`.
- `ConfiqOption` is a Click subclass third-party introspection tools will see;
  it adds one attribute and overrides nothing.

## Pros and Cons of the Options

### Option A: Eager snapshot (chosen)

- Good, because `fetch()` is pure and reload-stable.
- Good, because no framework objects outlive construction.
- Good, because failure modes (no context, no click) surface at the constructor, where
  the user's code visibly is.

### Option B: Hold the context, fetch lazily

- Good, because construction is trivial.
- Bad, because the context graph is pinned for the spec's lifetime.
- Bad, because `fetch()` behavior after the command returns is whatever Click's
  internals happen to allow — unspecified and version-dependent.

### Option C: Ambient re-resolve per fetch

- Good, because nothing is stored at all.
- Bad, because `reload()` outside command execution raises `RuntimeError`, making
  `ConfigHandle` + CLI source — an explicitly supported combination (§8.2 + §10) —
  unusable.
