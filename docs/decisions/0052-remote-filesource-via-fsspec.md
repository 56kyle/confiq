---
status: accepted
date: 2026-07-15
amends: "0040"
---
# Remote `FileSource` Wired via fsspec

## Context and Problem Statement

ADR 0040 shipped `FileSource` with the remote branch stubbed: `_read_remote` raised an
unconditional `NotImplementedError` pointing at `confiq[remote]` and deferring the wiring to "a
later stage." design_d §5.4 lists `FileSource` as reading local files via stdlib and remote URIs
via fsspec (`[remote]` + per-backend `[s3]`/`[gcs]`/`[adl]`). This stage fills that stub: read
remote bytes via fsspec and reuse the existing loader dispatch (`parse(bytes) -> Mapping`, §5.3).

The framework contracts are already fixed (source protocol, the `import_optional` missing-extra
boundary, the `SourceNotFoundError`/`SourceError` taxonomy of ADR 0040/0041). What this ADR
decides is the concrete wiring, plus one correctness fact that forced a small structural change.

## Decision Drivers

- **Reuse, not reinvention.** Remote reading is "get the bytes from somewhere else"; the
  bytes→`Mapping` decode (loader-by-suffix) is identical to local and must be shared.
- **The confiq extras UX (ADR 0006).** Every optional dependency surfaces a missing extra as
  `pip install confiq[X]`. fsspec's own missing-backend error names the raw package (`s3fs`), not
  `confiq[s3]` — a break in that promise if left unhandled.
- **The absent/operational/install-time taxonomy (ADR 0040/0041)** must hold for remote exactly
  as for local: a missing object is `SourceNotFoundError` (honoring `required`), an operational
  failure is a wrapped `SourceError`, and a missing extra stays a raw `ImportError`.
- **Sync-first built-ins (ADR 0047/0035).** fsspec's sync API bridges async backends, so remote
  `FileSource` stays a `SyncSource`; a built-in `AsyncSource` here would be false structure.
- **Cross-platform correctness.** A verified fact drives the shape (below).

## Decision Outcome

`_read_remote` reads via `fsspec.open(uri, "rb", **storage_options).read()`, reusing `_decode`
for the parse. Five concrete decisions:

1. **Preserve the raw URI string.** On Windows, `str(Path("s3://bucket/key.json"))` mangles to
   `s3:\bucket\key.json`, which breaks *both* fsspec and `Path.suffix` (and a query string leaks
   into `Path.suffix`). So `FileSource` keeps the unmangled original string (`self._raw`) for the
   fsspec call and derives the loader suffix from `PurePosixPath(urlsplit(uri).path).suffix`, not
   `self._path.suffix`. `_decode` gains an optional `suffix=` param so the local decode is
   unchanged and only the remote branch passes the URI-derived suffix. `name` becomes
   `f"file:{self._raw}"` (the real URI remotely; for a local `Path` input identical to the prior
   `f"file:{self._path}"`, and for a local `str` input it preserves the caller's spelling rather
   than normalizing separators — an error-message improvement, not a regression).

2. **`storage_options` plumbing.** A keyword-only `storage_options: Mapping[str, Any] | None =
   None` (the fsspec/pandas convention) is splatted into `fsspec.open` on the remote branch — the
   channel for credentials/region/endpoint kwargs. It applies only to remote URIs; passing it with
   a **local** path raises `ValueError` at construction rather than silently dropping it
   (refusal over degradation — a declared-but-unhonored option is the silent degradation this
   project refuses, §2).

3. **Proactive backend `import_optional` with a confiq-branded hint.** A small module-level
   `_REMOTE_BACKENDS` maps known schemes → (backend module, confiq extra) — `s3`/`s3a`→(s3fs,`s3`),
   `gs`/`gcs`→(gcsfs,`gcs`), `abfs`/`abfss`/`adl`/`az`→(adlfs,`adl`). `_read_remote` calls
   `import_optional(module, extra=...)` *before* touching fsspec, so a missing backend raises the
   `pip install confiq[X]` hint (raw `ImportError`, never wrapped). Other schemes fsspec supports
   natively (http/ftp/memory/file) are left to fsspec.

4. **Exception mapping.** `FileNotFoundError` → `SourceNotFoundError` if `required` else `{}`
   (a `None` sentinel from `_read_remote` → `{}`); then `OSError` → `SourceError(name, …) from e`;
   plus a final `except Exception` → `SourceError` — a deliberate widening of the operational-error
   rule so non-`OSError` backend failures (e.g. a botocore `ClientError` on auth/throttle) become
   a wrapped `SourceError` rather than propagating raw. `required` applies to remote identically.

5. **Sync-only.** No `fetch_async`; `FileSource` stays a `SyncSource`. An async remote source over
   fsspec's `AsyncFileSystem` remains the future `AsyncSource` possibility ADR 0047 already names.

### Consequences

**Positive:**
- Remote reads reuse the loader dispatch — a new format or backend stays "one small object."
- Missing backends fail with the confiq-branded install hint; missing objects honor `required`;
  operational SDK errors are wrapped — the ADR 0040/0041 taxonomy holds for remote.
- Testable today against fsspec's `memory://`/`file://` filesystems with no cloud SDK installed.

**Negative:**
- The `_REMOTE_BACKENDS` scheme→extra map is a small maintained table; a scheme confiq doesn't
  list falls back to fsspec's own (non-branded) error. Accepted — the table covers the declared
  extras and the fallback is still correct, just less on-brand.
- The `except Exception` fallback is broad. Justified: the alternative is a raw backend exception
  escaping the source boundary, which the taxonomy forbids; the message + chained cause preserve
  the detail.

## Relationship to prior ADRs

**Amends ADR 0040**: the `_read_remote` `NotImplementedError` deferral is now wired; the `required`
+ `SourceNotFoundError` contract it defined extends to remote objects unchanged. Reaffirms
ADR 0047 (still a `SyncSource`). Reuses ADR 0041's loader-raises/source-wraps split and ADR 0006's
`import_optional` boundary. design_d §5.4 is updated to drop the `NotImplementedError` caveat.
Cloud *secret* stores remain unbuilt (a separate stage); this ADR covers remote *files* only.
