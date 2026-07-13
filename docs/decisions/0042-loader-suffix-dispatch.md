---
status: accepted
date: 2026-07-12
---
# Loader Suffix Dispatch: Bytes-Based `parse` + `default_loaders()` Supersedes ADR 0009

## Context and Problem Statement

ADR 0009 introduced the `confiq.loaders` subpackage with a `Loader` protocol whose method
was `load(path) -> dict | None`, and a `FileSource` that accepted `loaders: list[Loader]`
and dispatched by forward-iterating the list, returning on the first non-`None` result
(chain-of-responsibility). Each loader owned both the *format decode* and the *path read*.

Stage 3's implementation surfaced a cleaner split. design_d §5.3 already reframes the
protocol as `parse(raw: bytes) -> Mapping[str, Any]` — a loader is *what format* bytes are
in, and the source is *where the bytes come from*. That separation makes the ADR-0009
design stale in two ways:

1. **The loader should not read the path.** Reading (local stdlib vs. remote fsspec) is the
   source's job; a loader that took a path duplicated I/O and coupled format to transport.
2. **List-scan dispatch is the wrong shape once loaders parse bytes.** With `parse(raw)`, a
   loader cannot "decline by returning `None` after sniffing the path" — the source must
   pick the loader up front, by suffix, before it has bytes to hand over.

The open question is how `FileSource` selects a loader when the caller does not pass one.

## Decision Drivers

- **Format/transport separation (design_d §5.3).** `parse(raw: bytes)` is the protocol;
  path reading belongs to the source. Dispatch must key off something the source knows
  before reading — the suffix.
- **Deterministic, legible selection.** A suffix→loader map is a direct lookup with an
  obvious answer, versus a list scan whose outcome depends on loader order and each loader's
  private "do I handle this?" logic.
- **Explicit refusal on an unknown format (ADR 0034).** An unrecognised suffix should
  produce a clear `SourceError` naming the path, not an opaque `KeyError` or a silent
  fall-through to the end of a list.
- **Single-loader override is the common custom case.** A caller with a bespoke format wants
  `FileSource(path, loader=MyLoader())`, not to reassemble and reorder a whole list.

## Considered Options

- **Option A (chosen): suffix→loader map + single-loader override.** A `default_loaders() ->
  dict[str, Loader]` builds the map from each built-in loader's `suffixes` frozenset; a
  `loader_for_suffix(suffix) -> Loader | None` does the lookup (case-insensitive). `FileSource`
  takes `loader: Loader | None`; when `None`, it calls `loader_for_suffix(path.suffix)` and
  raises `SourceError` on `None`.
- **Option B: keep ADR 0009's `loaders: list` + list-scan.** Rejected: with `parse(raw)` a
  loader can no longer sniff-and-decline, so the scan degenerates to "match by suffix anyway"
  — a list is a worse-typed map.
- **Option C: keep `Loader.load(path)`.** Rejected: couples format to transport, blocks the
  remote/fsspec path (ADR 0040), and duplicates I/O across loaders.

## Decision Outcome

Chosen option: **Option A**. The bytes-based `Loader.parse(raw)` (design_d §5.3), the
`default_loaders()`/`loader_for_suffix()` suffix registry, and the single `loader: Loader |
None` parameter on `FileSource` together **supersede ADR 0009's** path-based
`Loader.load(path)` and `loaders: list[Loader]` design.

- Each built-in loader carries a `suffixes: frozenset[str]` class attribute; the registry
  folds those into a `dict[str, Loader]`.
- `loader_for_suffix` lowercases the suffix before lookup, so `.YAML` resolves.
- `FileSource(path, loader=None, ...)`: an explicit `loader` wins; otherwise
  `loader_for_suffix(path.suffix)`; a `None` result raises `SourceError(name, "no loader for
  suffix ...")`.
- `default_loaders`/`loader_for_suffix` are exported from `confiq.loader` (the custom-loader
  composition surface), not from top-level `confiq`.

### Consequences

**Positive:**
- Loader is format-only and transport-agnostic; the source owns reads, unblocking the
  local/remote split (ADR 0040).
- Loader selection is a deterministic map lookup; an unknown suffix refuses explicitly with
  a path-naming `SourceError`.
- Custom formats are a one-argument override (`loader=...`).

**Negative:**
- A file whose format does not match its extension cannot be auto-detected by content; the
  caller must pass an explicit `loader`. Acceptable — content-sniffing is out of scope and
  extension-based dispatch is the predictable convention.
- Registering additional formats globally is no longer a list mutation; it is either a
  per-`FileSource` `loader=` or a future registry extension point. This is the intended
  narrowing from ADR 0009's global-list model.

### Relationship to ADR 0009

This ADR **amends/supersedes ADR 0009**: the `Loader` protocol method changes from
`load(path) -> dict | None` to `parse(raw: bytes) -> Mapping[str, Any]`; `FileSource`'s
`loaders: list[Loader]` parameter is replaced by `loader: Loader | None`; and dispatch moves
from list-scan to suffix-map lookup. ADR 0009's core structural wins — a `loaders`
subpackage of one-class-per-file loaders, independently testable, decoupled from the plugin
manager — are retained. Cited by `default_loaders`.
