---
status: accepted
date: 2026-07-12
---
# Loader/Source Error Taxonomy: Loader Raises, Source Wraps, Empty Is `{}`

## Context and Problem Statement

A file-backed source flows through two layers: a `Loader` turns raw bytes into a mapping,
and the `Source` (`FileSource`/`DotenvSource`) owns the file I/O around it. Several failure
and edge cases must be assigned to exactly one layer so behaviour is predictable and error
messages name the file:

1. **Malformed content** — `json.JSONDecodeError`, `tomllib.TOMLDecodeError`, `yaml.YAMLError`.
2. **Non-mapping top level** — a JSON array `[1, 2, 3]` or a bare scalar where a config
   object is required.
3. **Empty / whitespace-only content**, and YAML documents that parse to `None`.
4. **A missing optional dependency** — `pyyaml`, `tomli`, `python-dotenv`, `fsspec`.

design_d §5.3 and §13 sketch the layers but do not pin which one raises, which one wraps,
and what shape "empty" takes. This ADR fixes the taxonomy. (Presence — absent input — is a
separate concern, ADR 0040.)

## Decision Drivers

- **Errors are explicit and named at a choke point (operating ethos; Rust-lens).** The
  message a user sees should name the file. That is only possible at the source layer, which
  knows the path; the loader knows only bytes.
- **The loader stays reusable and path-agnostic.** A loader used directly (without a source)
  should still fail informatively, so it raises rather than swallowing — but it does not know
  a filename to name, so it must not manufacture a `SourceError`.
- **Refusal over degradation (ADR 0034).** A non-mapping top level cannot be merged as
  config; silently coercing or dropping it would be invisible corruption. The loader refuses.
- **Empty is data-absent-but-file-present, not an error.** An empty config file legitimately
  contributes nothing; the natural neutral element is `{}`, which merges as a no-op.
- **A missing extra is a programmer install-time error, not a config error (ADR 0006).** It
  must not be wrapped in `SourceError` — that would bury a `pip install` fix under a
  file-content error and let `except SourceError` swallow it.

## Considered Options

- **Option A (chosen): Loader raises; source wraps; empty → `{}`; missing-extra → `ImportError`.**
  - Loader lets stdlib decode errors surface; refuses a non-mapping via `ensure_mapping`
    raising `ValueError(f"top-level must be a mapping, got {type(x).__name__}")`; maps
    empty/whitespace and YAML-`None` to `{}`.
  - Source catches loader + IO errors and re-raises `SourceError(name, str(e)) from e` so the
    message names the file and the cause chains; it lets the missing-extra `ImportError`
    propagate unwrapped.
  - A shared `import_optional(module_name, *, extra)` helper is the single "import-or-raise-
    with-install-hint" boundary, reused by the toml/yaml loaders and `DotenvSource` (and
    ready for fsspec).
- **Option B: Loader wraps into `SourceError` itself.** Rejected: the loader has no filename,
  so the message could not name the file, and a directly-used loader would raise a
  source-flavoured error with an empty/placeholder name.
- **Option C: Non-mapping top level tolerated (coerce or ignore).** Rejected: silent
  degradation, contrary to ADR 0034; a list-or-scalar config file is a genuine mistake.

## Decision Outcome

Chosen option: **Option A**, pinned as:

- **Malformed content:** the loader does not catch decode errors; they surface for the source
  to wrap. `FileSource._decode`/`DotenvSource.fetch` catch loader + IO errors and re-raise
  `SourceError(name, str(e)) from e`.
- **Non-mapping top level:** `ensure_mapping(value: object) -> dict[str, Any]` raises
  `ValueError` on a non-`Mapping`. Used directly, a loader surfaces that raw `ValueError`;
  through a source it becomes a `SourceError`. (`ensure_mapping` takes `object`, not `Any`,
  which also serves as the boundary that launders the parser's `Any` result past
  `reportAny`.)
- **Empty / whitespace-only:** each loader returns `{}` before invoking its decoder; YAML
  additionally maps a parsed `None` to `{}`.
- **Missing extra:** `import_optional` re-raises `ImportError(f"confiq requires the '{extra}'
  extra for this feature: pip install confiq[{extra}]") from e`. `FileSource._decode` catches
  `ImportError` and re-raises it unchanged (not wrapped in `SourceError`); `DotenvSource`
  never wraps it because the import sits outside its IO-wrapping `try`.

### Consequences

**Positive:**
- Every user-facing content error names the file and chains the original cause.
- Loaders remain reusable and directly testable, failing informatively on their own.
- A `pip install confiq[...]` fix is never buried under a `SourceError` or swallowed by
  `except SourceError`.
- One `import_optional` boundary means one place owns the install-hint message.

**Negative:**
- The source-layer wrap uses `str(e)` for the detail, so the wrapped message is only as
  precise as the underlying exception's `str`. Enrichable later (e.g. line/column from decode
  errors) without changing the taxonomy.
- `except Exception` in the source's decode step is deliberately broad to catch any loader's
  decode error family uniformly; `ImportError` is re-raised first so the breadth does not
  swallow the install-hint path.

### Blast radius

Shapes `loader/_loader.py` (`ensure_mapping`), the three loaders' `parse`, `_imports.py`
(`import_optional`), and the `fetch`/`_decode` bodies of `FileSource`/`DotenvSource`. Cited
by `ensure_mapping`. Complements ADR 0040 (presence), ADR 0006 (missing-extra →
`ImportError`), ADR 0042 (suffix dispatch).
