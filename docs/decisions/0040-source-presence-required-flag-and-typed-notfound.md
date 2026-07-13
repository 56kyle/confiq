---
status: accepted
date: 2026-07-12
---
# Source Presence: Per-Source `required` Flag and Typed `SourceNotFoundError`

## Context and Problem Statement

As Stage 3 implements the concrete synchronous sources (`FileSource`, `DotenvSource`,
`EnvSource`, `MemorySource`), each source must decide what happens when its backing input
is *absent* — a config file that does not exist, a `.env` that was never written. This is
distinct from the input being *present but malformed* (a truncated JSON document, a TOML
syntax error), which ADR 0041 handles.

Two questions must be pinned:

1. **Is "absent" an error?** A missing primary config file is usually a real failure; a
   missing `.env` overlay is usually normal. The answer differs per source and, for
   file-backed sources, per usage.
2. **Can a caller distinguish "absent" from "malformed" without parsing message text?** The
   two cases warrant different handling (retry/scaffold vs. fix-the-file), so the type
   system should carry the distinction.

design_d §5.4 lists the sources but does not specify presence semantics; §13 (error
handling) is silent on missing-input. This ADR fills that gap.

## Decision Drivers

- **Refusal over degradation (ADR 0034)** argues a source that was *asked for* and cannot
  be found should refuse loudly by default, not silently contribute nothing.
- **Absent is not malformed.** Collapsing both into a bare `SourceError` forces callers to
  scrape the message to tell "write the file" from "fix the file." A distinct type is the
  Rust-lens contract: the failure mode belongs in the exception hierarchy, not in prose.
- **The default differs by source.** A primary `FileSource` should be strict; a `.env`
  overlay is conventionally optional. Encoding the common case as the default keeps the
  everyday call site free of ceremony.
- **The flag is a per-source concern, not a protocol concern.** `MemorySource` is always
  present; `EnvSource` treats an empty environment as normal (`{}`). Threading a `required`
  attribute through `BaseSource` or the `Source` protocol would put a knob on sources that
  have no absence to speak of — accidental surface (ADR 0035).

## Considered Options

- **Option A: Per-source `required: bool` kwarg (only where absence is meaningful) plus a
  typed `SourceNotFoundError(SourceError)`.** `FileSource(required=True)` default,
  `DotenvSource(required=False)` default. Missing + required → `SourceNotFoundError`;
  missing + not required → `{}`. No flag on `MemorySource`/`EnvSource`; none on
  `BaseSource`/`Source`.
- **Option B: One untyped `SourceError` for both absent and malformed.** Simpler hierarchy,
  but callers must parse messages to branch, and refusal vs. tolerance is not expressible
  per source.
- **Option C: A `required` attribute on the `Source` protocol / `BaseSource`.** Uniform, but
  puts a meaningless knob on always-present sources and pushes presence policy into the
  shared base.

## Decision Outcome

Chosen option: **Option A**.

- Add `class SourceNotFoundError(SourceError)` to `exceptions.py`, reusing the
  `(source_name, message)` `__init__`. `except SourceError` still catches it; a caller that
  wants to distinguish absence catches `SourceNotFoundError` specifically.
- `FileSource(path, loader=None, *, required=True, profile=None)`: missing local file →
  `SourceNotFoundError` when `required`, else `{}`.
- `DotenvSource(path=".env", *, required=False, profile=None)`: missing file → `{}` by
  default, `SourceNotFoundError` when `required`. The `[dotenv]` extra is imported only
  after the presence check, so a missing optional `.env` no-ops without requiring the extra.
- `MemorySource` and `EnvSource` carry no `required` flag: the former is always present, the
  latter treats an empty match set as the normal `{}`.
- `BaseSource` is stripped to a single `profile: str | None = None` default; it advertises
  no `name`/`fetch` stub, so a bare `BaseSource` does not structurally satisfy `SyncSource`
  (Rust-lens: do not advertise a contract that returns `None`).

### Remote deferral

`FileSource._read_remote` raises `NotImplementedError` unconditionally with a message
pointing at `confiq[remote]` and noting remote support lands in a later stage. This is
chosen over `import_optional("fsspec", ...)`-then-raise because the honest contract *this*
stage is "not wired yet" regardless of whether fsspec happens to be installed — masking that
behind an `ImportError` when fsspec is absent would misreport the reason. `fetch()` routes
to `_read_remote` before entering the `SourceError`-wrapping block, so the
`NotImplementedError` propagates raw rather than being wrapped as malformed content.

### Consequences

**Positive:**
- Callers branch on absence vs. malformation by exception type, not message text — which is
  also what lets tests assert against a contract rather than a string.
- The strict-by-default `FileSource` refuses a missing primary config loudly; the
  lenient-by-default `DotenvSource` keeps the common overlay call site clean.
- Always-present sources carry no vestigial `required` surface.

**Negative:**
- Presence policy lives on two constructors rather than one shared attribute; a future
  source with an absence concept must opt into the same convention deliberately. This is the
  intended trade — uniformity would put a dead knob on `MemorySource`/`EnvSource`.

### Blast radius

Adds `SourceNotFoundError` to `exceptions.py` and its re-export in `confiq/__init__.py`.
Adds a `required` kwarg to `FileSource` and `DotenvSource`. Strips `BaseSource` to the
`profile` default. Relates to design_d §5.4/§13; complements ADR 0041 (malformed-content
taxonomy).
