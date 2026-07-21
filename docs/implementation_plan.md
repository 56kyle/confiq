# confiq — Phased Implementation Plan

## Context

`confiq` is a config-reconciliation library whose architecture is fully specified in [`design_d.md`](design_d.md) + the 35 ADRs under [`decisions/`](decisions/) (`0001`–`0035`), but exists today as a **signature-only skeleton**: every module, dataclass, enum, protocol, and `__all__` is written and real, while every *behavioral* method body is `...`. There are zero tests. This plan sequences the filling of those stubs in a dependency-correct order, so each layer is pinned by tests against a solidified contract before the next builds on it.

It defines **stages and agent orchestration** — the order work happens, which development agent owns each piece, and where the design's deliberately-deferred scope questions get resolved (at the moment each becomes concrete, not up front).

**Governing ordering fact:** the `SchemaAdapter.field_metadata()` **path table** (ADR 0026) is the load-bearing wall — provenance, env/CLI binding, parser application, secret masking, and error field-paths all key off its dotted-path key space. It lands early (Stage 2). `ResolutionSpec` (ADR 0017) is the hub shared by `load()`, `ConfigHandle`, and `LazyConfig`, so the resolver is factored **color-agnostic except at the fetch step** (ADR 0035) before any public entry point — async is a thin shell, never a hand-maintained twin.

## Decisions baked in

- **Open scope questions (§14) — decided at each stage's gate.** FILL / schemaless / async-fetch are *not* resolved up front. Each gets a design-questioner pass when its stage is reached; until resolved, its branch stays out of scope (no speculative branches or their tests). Each resolution lands as an ADR update/addition when decided.
- **Coverage — the `fail_under=100` gate is ignored during the build.** Tests are written to make sense for the contract, driven by test-authoring judgment, not by chasing line coverage. Restoring/tuning the gate is deferred to after the surface stabilizes.
- **Agent cadence — questioner only on residual ambiguity.** The design-questioner runs only where real ambiguity remains (§14 items, the §14.1 provisional signatures). Stages that are pure mechanical fills of a locked ADR contract skip it.

## Standing orchestration rules (every stage)

1. **Source code → `python-dev`.** Committed Python is not hand-written outside this agent. Design is clarified first (questioner) when ambiguity exists.
2. **Tests → `python-test-writer`.** Owns unit + integration tests only — never acceptance tests. The three-tier `tests/` dirs (`unit_tests/`, `integration_tests/`, `acceptance_tests/`) exist but are empty; `acceptance_tests/` stays user-owned.
3. **Review → `python-reviewer`** (read-only) after each stage's source and test work, before any commit.
4. **Design gate → `python-design-questioner`** only where a stage below flags residual ambiguity.
5. **`python-dev-quick`** only for trivial, explicitly-vetted mechanical bits — never for stub bodies with behavior.
6. Commit per stage (or per coherent sub-unit) only when asked; work proceeds on `feature/implementation-attempt`.

## Stage sequence

### Stage 1 — Pure data core: merge + error aggregation
- **Modules:** `_merge.py` (`deep_merge`, `merge_sources` — deep merge, list-replacement, per-leaf provenance side-map); `exceptions.py` (`SourceError.__init__`, `MissingConfigError`/`ConfigValidationError` `__init__` + `contexts`/`field_path`/`sources` forwarding + zero-context guard + multi-context message, ADR 0029).
- **Depends on / enables:** depends only on real `_types`; everything downstream produces `FetchedEntry` and raises these errors.
- **Contract pinned:** merge precedence, list replacement, FILL only-if-absent, provenance winner; error classification (missing vs invalid), aggregation, `contexts[0]` forwarding, empty-context refusal.
- **Design gate:** **YES — `MergeMode.FILL` keep/remove (§14.2 #1).** Resolve before writing `deep_merge`; building then culling wastes the provenance branch.
- **Test checkpoint: YES (checkpoint #1).** Pure total functions, no schema dependency — exhaustive/property-style.

### Stage 2 — Schema adapters + adapter resolution (the path table)
- **Modules:** `adapter/_pydantic.py`, `_dataclass.py`, `_typeddict.py`, `_schemaless.py` (`field_metadata()` recursing fixed dotted paths per §4.4 reading rules; `validate()` via pydantic `TypeAdapter`); `_hookspecs.py` `make_plugin_manager()` + built-in `confiq_get_schema_adapter` hookimpls (positive mutually-exclusive detection, built-ins first / spec plugins last → LIFO user-plugin win, unclaimed → `SchemaError`, ADR 0030).
- **Depends on / enables:** depends on `_field`/`_types`/`SchemaError`; the path table underpins env/CLI binding, parsers, masking, error paths.
- **Contract pinned:** path-table shape per kind (nested + intermediate present, collection/union excluded, ADR 0026); `validate()` per kind; resolution order + user-plugin-wins + unclaimed-`SchemaError`.
- **Design gate:** **YES — schemaless keep/remove (§14.2 #2)** decides whether `_schemaless` adapter + the `schema=None` branch exist; and **secret-masking refusal locus (ADR 0033)** — TypedDict+`secret=True` → `SchemaError` in the adapter vs at load.
- **Test checkpoint: YES (checkpoint #2).** Pin the foundational key space hard, per schema-kind.

### Stage 3 — Sources (core, sync) + loaders
- **Modules:** `loader/_json.py` (core), `_toml.py` (`[toml]`), `_yaml.py` (`[yaml]`); `source/_base_source.py`, `_memory.py`, `_env.py` (prefix/delimiter → paths + `ConfigField.env` override, uses Stage 2 table), `_file.py` (local stdlib + loader dispatch), `_dotenv.py` (`[dotenv]`).
- **Depends on / enables:** `MemorySource` needs nothing; `EnvSource`/`FileSource` need the path table + loaders. Resolver consumes source output. CLI sources deferred to Stage 7; remote `FileSource` (fsspec `[remote]`) out of scope here.
- **Contract pinned:** each `fetch()` + `name`/`mode`/`profile`; `Loader.parse()` per format; env mapping + `ConfigField.env` override. `MemorySource` becomes the primary test primitive.
- **Design gate:** NO (mechanical fills of locked contracts) — straight to `python-dev`.
- **Test checkpoint:** per-source/per-loader unit tests as each lands.

### Stage 4 — Color-agnostic resolver pipeline (sync path)
- **Modules:** `_resolve.py` `resolve()`, `_filter_by_profile()`, `_apply_parsers()`, `_assert_no_async_sources()` — wire §6.2 steps 1–7 (profile filter → fetch → merge → adapter → coerce → validate → return), provenance surfaced in errors. `resolve_async` stays stubbed.
- **Depends on / enables:** integrates Stages 1–3. **Factor the fetch step as the single color-bearing seam now** (ADR 0035) so Stage 6 is a shell.
- **Contract pinned:** end-to-end `resolve()` — profile filter, parser application, validation, provenance naming in errors.
- **Design gate:** **YES — `explain()`/observability (§14.2 #4).** Decide now whether `resolve()` retains vs. discards the snapshot after validation; retrofitting later is expensive.
- **Test checkpoint:** integration tests of the assembled pipeline.

### Stage 5 — Public sync API + test primitives (PRIMARY checkpoint)
- **Modules:** `_load.py` (`ResolutionSpec.__post_init__` + `.schemaless()`, `spec_with()`, `load()` overload dispatch + async-source rejection → `load_async`); `_schemaless.py` `SchemalessConfig`; `context.py` (`override`/`async_override`/`current_override` — read only by the proxy per ADR 0028; `load()` never consults it).
- **Depends on / enables:** `load()` wraps Stage 4 `resolve()`; `ResolutionSpec` is the ADR 0017 hub for Stages 7–8; `spec_with` + `MemorySource` + `override` is the ADR 0028 test triad and must solidify together.
- **Contract pinned:** full public sync surface — both `load()` forms, `ResolutionSpec` immutability, `spec_with` splice, `override` scoping, schemaless subscript.
- **Design gate:** **YES — `load()` positional `schema`/`sources` (§14.1 #2)**; schemaless recurs in the `load(None, …)` overload + `.schemaless()`.
- **Test checkpoint: YES (checkpoint #3, strongest).** Author the full three-tier unit + integration suite against the frozen public surface here.

### Stage 6 — Async shell over the shared pipeline
- **Modules:** `_resolve.py` `resolve_async()`; `_load.py` `load_async()` — thin shells differing only at the fetch step (gather async, sync inline).
- **Depends on / enables:** depends on the Stage 4 factoring holding; kept separate so sync is proven first and async is demonstrably drift-free.
- **Design gate:** **YES — async fetch scope (§14.2 #3), the biggest gate.** Decide whether v1 ships `AsyncSource`/`load_async` at all. If deferred, skip this stage — but `load()` still keeps the Stage 5 async-rejection guard.
- **Test checkpoint:** `load_async` contract + sync-inline behavior + `load()`-rejects-async refusal message.

### Stage 7 — CLI integration (`[cli]`)
- **Modules:** `_cli.py` (`ConfigBind`, `options_from()` — Click layer, ADR 0032); `source/_argparse.py` (core), `_click.py`/`_typer.py` (`[cli]`) — eager `Context` snapshot at construction (ADR 0032), explicit-set detection, convention binding validated against the path table (candidate dottings ∩ leaf paths; >1 → `SchemaError`; 0 → plain flag, ADR 0027).
- **Depends on / enables:** needs the path table (Stage 2) + Source/resolver (3–4); isolated from core sources for its ambient-Context machinery.
- **Contract pinned:** consumer binding (`database_host` ↔ `database.host`), ambiguity `SchemaError`, `ConfigBind`/`ConfigBind(None)`, eager-snapshot replay determinism, `options_from` forward-convention agreement.
- **Design gate:** NO new §14 items (confirm Typer→Click asymmetry stays documented-not-promised, §10.5).
- **Test checkpoint:** binding + replay integration tests.

### Stage 8 — Reload + lazy proxy (`[reload]`)
- **Modules:** `_locks.py` `ReentrancyGuard`; `_handle.py` `ConfigHandle` (frozen-schema rejection, copy-on-write reload/reload_async, atomic swap, blinker `on_reload`, inline subscribers); `_lazy.py` `LazyConfig` + `_LazyProxy` (bind/reset/bound; override-aware validated snapshot overlay, ADR 0031).
- **Depends on / enables:** depends on `ResolutionSpec`/`load` + `context.override` (Stage 5). Pulls the only optional runtime dep (blinker); last runtime code so core stays dependency-clean (§12.4).
- **Contract pinned:** reload swap + reentrancy fast-fail, `on_reload` connect/disconnect, frozen-schema refusal, proxy override-awareness + unbound-read error.
- **Design gate:** **YES — `ConfigHandle.current` property vs method (§14.1 #1); `on_reload(fn)` `(old,new)` arity + disconnect-return (§14.1 #3); async-reload scope (§14.2 #3, distinct from Stage 6 — async reload is argued essential to `[reload]`).**
- **Test checkpoint:** reload/reentrancy/proxy integration tests.

### Stage 9 — Remote `FileSource` via fsspec (`[remote]` + `[s3]`/`[gcs]`/`[adl]`) — DONE
*(Added post-Stage-8 audit; the original "remote + cloud" stage was narrowed to remote file
reading only — fsspec is installed so it's real+testable, whereas the cloud SDKs are absent and
`moto` isn't in the dev deps, so the cloud stores became their own Stage 10.)*
- **Modules:** wired the remote branch of `source/_file.py` (was a raw `NotImplementedError`) to
  read bytes via `fsspec.open`, reusing the existing loader dispatch. Raw-URI preservation (Windows
  `Path` mangling fix), `storage_options` kwarg, proactive scheme→extra `import_optional` for a
  confiq-branded install hint, exception mapping (missing→`SourceNotFoundError`/`{}` by `required`,
  operational→`SourceError`). Sync-only (ADR 0047). → **ADR 0052** (amends 0040).
- **Test checkpoint:** remote read/missing/malformed/branded-hint/`storage_options` tests against
  fsspec `memory://` (dependency-free). Done.

### Stage 10 — Cloud secret/param sources (split per backend; test methodology differs)
Split into per-backend sub-stages because each backend's local test story differs sharply (moto
in-process for AWS; `-dev`-server binaries for Vault/Consul; NO local emulator for GCP/Azure —
Azurite does not cover Key Vault, GCP ships none). Cloud sources are built-in `SyncSource`s behind
`import_optional` (ADR 0006), error taxonomy per ADR 0040/0041, sync-only (ADR 0047/0035). The
reusable cloud-source pattern is established by 10a → **ADR 0053**.

- **Stage 10a — AWS Secrets Manager (`[aws]`, `moto`) — DONE.** `source/_aws.py`
  `AwsSecretsManagerSource` — structured (JSON `SecretString` decoded via a reused `Loader`),
  `ResourceNotFoundException`→`SourceNotFoundError`/`{}`, `profile_name` (credential) vs `profile`
  (confiq tag) convention, binary-only→`SourceError`. Tested in-process with `moto` (in the `dev`
  group since 2026-07-20; `boto3` from the `[aws]` extra, which `nox -s tests-python` now installs
  via the `[all]` extra — tests still `importorskip` so a bare `uv sync` skips them). → ADR 0053.
- **Deferred to a later stage — real integration tests, not boundary fakes** (user decision):
  - **AWS Parameter Store** — a *flat* source (`get_parameters_by_path` → `flat_to_nested`+`aliases`,
    ADR 0048), joins `_aws.py`; moto-testable.
  - **Consul KV** (`[consul]`) + **HashiCorp Vault KV** (`[vault]`) — flat; tested via
    `consul agent -dev` / `vault server -dev` subprocess fixtures (a new fixture pattern; skip if the
    binary is absent). Vault adds a KV v1/v2 envelope knob.
  - **GCP Secret Manager** (`[gcp]`) + **Azure Key Vault** (`[azure]`) — **no local emulator exists**,
    so gated **live-integration tests** (real creds, skipped by default) rather than hand-written
    fakes. GCP structured (simplest); Azure has a structured-vs-flat fork + the `azure-identity`
    credential chain.
- **Design gate:** YES per remaining source — an ADR each, inheriting the ADR 0053 pattern.

### Stage 11 — `pytest-confiq` companion plugin (new module, FINAL)
- **Modules:** new package (the one piece with no skeleton yet) — `config` fixture over `MemorySource`, autouse isolation (scrub `os.environ`, chdir tmp — isolate *inputs*, never intercept `load()`, ADR 0016/0028), layering helpers over `spec_with`, autouse `LazyConfig.reset()` between tests, async support via `context.override`.
- **Depends on / enables:** `MemorySource` (3), `spec_with`/`override` (5), `LazyConfig.reset` (8) — thin because the core carries the primitives.
- **Design gate:** confirm package boundary + `pytest11` entry-point name (absent from `pyproject.toml` today) + the `[test]` extra (ADR 0016); behavior constrained by ADR 0028.
- **Test checkpoint:** fixture contract + cross-test isolation.

*(Deferred, user-timed — not a stage: backfill tests for the thin modules (`_imports.py`, `adapter/_kinds.py`, `_base_source.py`, the protocols) and re-enable the `fail_under=100` coverage gate once the whole surface, including these two stages, is present.)*

## Cross-cutting build guidance

- **Resolver color:** build **sync-first, then async shell** over a pipeline factored color-agnostic from the start (Stage 4 → 6). Do **not** build an async core with a sync shell — design_d §7.2 explicitly rejects a sync entry point driving an event loop. One merge→validate path only; async cannot drift.
- **Deferred branches stay unwritten.** Because open questions resolve at their stage gate, do not pre-build FILL bookkeeping, the schemaless adapter/overloads, or async fetch until the corresponding gate rules them in. This keeps coverage from ever becoming the reason a provisional capability survives.
- **Draft ADRs alongside code** for any *new* non-trivial decision surfaced during implementation; the §14 resolutions themselves each land as an ADR update/addition when decided.

## Critical files

| File | Stage | Role |
| --- | --- | --- |
| `src/confiq/_merge.py` | 1 | pure merge + provenance core |
| `src/confiq/exceptions.py` | 1 | error aggregation (ADR 0025/0029) |
| `src/confiq/adapter/_schema_adapter.py` + the four impls under `src/confiq/adapter/` | 2 | ADR 0026 path table |
| `src/confiq/_resolve.py` | 4/6 | the ADR 0035 color-agnostic seam |
| `src/confiq/_load.py` | 5 | `ResolutionSpec` hub + `load()` (ADR 0017) |
| `src/confiq/context.py` | 5 | the `override` primitive unifying testing + proxy |

## Verification

Per stage, end-to-end rather than test-only:

1. **Unit/integration tests** authored by `python-test-writer` at the stage's checkpoint, run via `pytest tests/unit_tests tests/integration_tests` (nox `tests-python` session available). Ignore the `fail_under=100` gate for now; if it blocks the run, invoke pytest without the coverage gate (e.g. `--no-cov` or a temporary `--cov-fail-under=0`) rather than padding tests.
2. **Real-usage smoke** at the checkpoints: construct a small schema and drive `load()` with a `MemorySource` (Stage 5) and a `FileSource` + `EnvSource` combo (Stage 3/4), asserting `isinstance(result, Schema)` and correct provenance-in-error messages on a deliberate bad value.
3. **Typecheck** each stage with basedpyright (nox `typecheck`) — the design leans hard on typing; regressions here are contract regressions.
4. **`python-reviewer`** pass on source + tests before commit each stage.
5. **CLI/reload stages (7/8):** drive an actual Click command and an actual `ConfigHandle.reload()` cycle, not just unit mocks — these are the stages where mocking would mask a real boundary.
