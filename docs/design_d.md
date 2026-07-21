# `confiq` — Design Specification (`design_d`)

> A configuration library for Python that treats configuration as an immutable, typed
> value computed from an explicit, ordered list of sources — and treats the command line
> and the test suite as first-class parts of that computation rather than afterthoughts.

This is a complete, standalone specification. It supersedes `design_c.md`. Decision
rationale lives in the ADRs under `docs/decisions/`. A small number of signature-level
choices are marked **(provisional)** and collected in §14; everything else is settled.

---

## 1. Purpose and scope

`confiq` reconciles three things that are normally wired together by hand and break
independently: **configuration**, the **command line**, and the **test suite**.

Stated sharply: when an application has a typed config schema and an existing CLI, a
single value can end up declared in up to **three places** — the schema default, the CLI
option default, and the test fixture — and the wiring between those places is
hand-maintained state that breaks invisibly.

The motivating pain is concrete: building an application with `pydantic-settings` and a CLI
framework means maintaining the state relationship between config and CLI by hand, and then
fighting that same global state in `pytest` — rebuilding fixtures, leaking environment
variables between tests, monkeypatching settings into shape. Each corner is individually
solved; the seams are where the time goes.

`confiq` treats the triangle as one problem. Configuration is computed once into an ordinary
typed value; the CLI is just another source feeding that computation; and because the result
is a plain value with no global identity, testing it means constructing values, not mutating
and restoring shared state.

Four solution criteria fall out of the problem, and every capability in this document
should be traceable to at least one of them:

1. **One declaration point.** A value's default lives in the schema and nowhere else.
2. **The CLI folds in without double-declaration.** An existing command contributes
   exactly what the user explicitly set.
3. **Tests construct values.** No mutate-and-restore of shared state.
4. **Every value's origin is visible.** When something is wrong, the resolution says
   which source supplied what.

---

## 2. Design principles

The principles are ranked: an identity, then governing considerations, then supporting
habits in their service. They are judgment guides for arguing specific cases, not
decision rules — everything depends on the situation. Full rationale: ADR 0034.

**The identity:**

1. **Reconciliation comes first.** confiq exists to reconcile config, CLI, and tests
   (§1). The principles below are good habits in service of that; a capability serving
   none of the three corners must earn its place explicitly.

**Governing considerations:**

2. **User experience is the most important factor — weighed by severity, case by case.**
   Writing, debugging, and testing are different user moments; when they conflict, the
   worse the potential failure, the more the failure moment dominates. UX is never an
   excuse for poor development practice.
3. **Legibility: magic is permitted when auditable.** The enemy is invisible coupling —
   an effect with no traceable cause. Deterministic, documented, inspectable convention
   (e.g. name binding validated against the path table, loud on ambiguity) is acceptable;
   hidden priority and ambient mutation are not. Precedence is the list you pass to
   `load()`; provenance (§6.4) is this principle made executable.
4. **Refusal over degradation.** Never silently provide a weaker guarantee than the user
   believes they have. Where a promise cannot be kept, fail loudly at the earliest
   moment — and every refusal names a remediation path in its message (a "no" without a
   "do this instead" is a bug). See §3 (secrets, ADR 0033), §7.2 (async rejection), §8.2
   (frozen-schema requirement).
5. **Complexity is judged by inherence, not burden.** Complexity inherent to the problem
   (including the language environment) is simply the work, and is paid willingly;
   complexity that is an artifact of representation, false structure, or out-of-problem
   users is what gets refused. Maintenance burden never decides whether a capability
   belongs — at most, capacity sequences when essential work happens. Duplication pain
   is a representation smell: refactor so the duplicates cannot drift, rather than
   deleting the capability. (ADR 0035.)

**Supporting habits:**

6. **The library owns no mutable state.** `load()` returns an instance of the schema you
   declared; there is no ambient `confiq.config` and no library-owned singleton. Where
   ambient state exists (§8.3, §8.4), the application owns it knowingly.
7. **Config is a fact, not a variable.** Immutability's value in the common path is
   reasoning — test determinism, no aliasing surprises; on the live `ConfigHandle` path
   it additionally buys lock-free thread safety (§9.1). The only mutation is opt-in live
   reload.
8. **Schema non-invasion.** confiq never appears in your domain types: no base class, no
   decorator; per-field metadata rides in `Annotated` as additive freight. (Which schema
   *kinds* are supported is a separate scope question — see §4.1.)
9. **Type safety by default, opt-out on purpose.** The common path is fully typed with no
   `Any` on reads. Every relaxation is an explicit, named choice.
10. **No DSL in the values.** No string interpolation, computed expressions, or object
    instantiation inside config values. Computed values are the job of a *source*.
11. **Boundaries are named contracts.** Multi-value pipeline boundaries get named types;
    domain variants get enums (ADR 0023, ADR 0024) — on legibility merits alone. That
    these forms also map cleanly to Rust is an acknowledged side benefit, not a driver
    (ADR 0021 as amended by ADR 0034).

---

## 3. The configuration value

`load(schema, sources) -> T` returns an instance of the **declared type** — not a library
wrapper, not a forced pydantic value. `isinstance(config, YourType)` holds; the `-> T`
annotation is honest; the type checker sees your exact type.

Because the returned type is the one you declared, `confiq`'s guarantees form an explicit
**gradient** rather than a constant. This is intentional:

| Schema type | Access | Mutability | Secret-masked `repr` | Rich serialization |
|---|---|---|---|---|
| `BaseModel(frozen=True)` | attribute | immutable | full | full (`model_dump`) |
| `BaseModel` (default) | attribute | mutable | full | full |
| `@dataclass(frozen=True)` | attribute | immutable | invasive¹ | via `TypeAdapter` |
| `@dataclass` | attribute | mutable | invasive¹ | via `TypeAdapter` |
| `TypedDict` | subscript | mutable dict | refused at load² | already a dict |
| schemaless | subscript | read-only `Mapping` | n/a³ | none |

¹ Masking a secret on a stdlib dataclass requires `confiq` to generate a custom `__repr__`.
² A `TypedDict` resolves to a plain dict with nowhere to hang a masked repr — so
  `ConfigField(secret=True)` on a `TypedDict` field raises `SchemaError` at load rather
  than silently not masking. A declared secret is a guarantee or an error, never a
  decoration. (ADR 0033.)
³ Schemaless mode has no fields and therefore no `ConfigField` at all; the question
  cannot arise.

Three consequences are stated loudly, not buried:

- **The immutability pillar holds only when the schema is frozen.** Frozen pydantic is the
  safe default; a non-frozen dataclass yielding mutable config is a legitimate informed
  choice. The lock-free-read guarantee in §9 applies only to frozen schemas.
- **Richer per-field features are pydantic-strong** and degrade on other schema types.
- **The gradient covers capabilities, not requested guarantees.** A capability the user
  did not ask for may be absent; a guarantee the user *declared* (`secret=True`) is
  honored or refused at load — never silently dropped (§2 principle 4, ADR 0033).

The honest pitch: bring any structure; frozen pydantic is where every guarantee is on, and
each step away trades one named guarantee for one named convenience, visibly.

---

## 4. Schemas

### 4.1 Accepted schema types

`BaseModel`, pydantic dataclass, stdlib dataclass, `TypedDict`, and schemaless (`schema=None`).
No `confiq` base class is required. An existing dataclass or `TypedDict` is accepted without
rewriting it as a pydantic model.

### 4.2 Field annotations

Per-field configuration metadata travels in `Annotated[...]` as a frozen `ConfigField`:

```python
@dataclass(frozen=True)
class ConfigField:
    secret: bool = False                       # mask in repr and in error output
    parser: Callable[[str], Any] | None = None # pre-validation coercion from a raw string
```

There is no `cli` member and no `env` member: both CLI binding and custom env-var naming
live on the *source*, not the schema field. A field never declares where it is read from —
that would make precedence a per-field property invisible in the source list. CLI binding
lives on the CLI parameter (see §10); a custom env-var name is an `EnvSource`/`DotenvSource`
`aliases` entry (§5.4). This is the positional-cascade identity: sources translate their key
space, fields do not bind (ADR 0048). Example schema, with no `confiq` import required for the types themselves:

```python
class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432
    password: Annotated[str, ConfigField(secret=True)] = ""

class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    database: Database = Database()
    debug: bool = False
```

### 4.3 The `SchemaAdapter`

A `SchemaAdapter` abstracts the two operations the rest of the system needs from a schema:
reading per-field metadata, and validating a mapping into an instance of the declared type.
It is the load-bearing wall behind multi-schema support.

```python
class SchemaAdapter(Protocol[T]):
    def field_metadata(self) -> FieldAnnotations: ...
        # dotted path → the Annotated *extras* for that field (incl. ConfigField). Not the
        # bare type — callers that need the type hold the schema class directly.
        # FieldAnnotations is a TypeAlias for Mapping[str, list[Any]].
    def validate(self, data: Mapping[str, Any]) -> T: ...
        # validate/coerce the merged mapping into an instance of the declared type.
```

`field_metadata` returns the schema's **path table**: one entry per fixed dotted path
reachable from the root (`"database"`, `"database.host"`, `"database.password"`, …),
with adapters recursing through nested models, dataclasses, and `TypedDict`s. This is
the canonical key space shared by provenance (§6.4), parser application (§6.2 step 6),
secret masking, CLI binding and env/dotenv `aliases` target validation (§6.2 step 4, §10.2),
and error field paths (§13). Recursion covers fixed paths only — elements of `list[Model]` fields and union
branches contribute no per-element paths. (ADR 0026.)

Adapters are resolved through a pluggy hook (`confiq_get_schema_adapter`), so new schema
kinds can be added without touching the core. Each built-in adapter claims only schemas
it is definitively correct for (in particular, the dataclass adapter declines pydantic
dataclasses, which belong to the pydantic adapter), so correctness never depends on call
order; plugins from `ResolutionSpec.plugins` are registered last and therefore — under
pluggy's LIFO call order — win `firstresult` over the built-ins, which is the documented
override guarantee. An unclaimed schema raises `SchemaError`. (ADR 0030.)

### 4.4 Metadata reading is per-adapter

- **pydantic** schemas read `ConfigField` from pydantic's own `FieldInfo.metadata` — the
  same view the validator uses, with no second introspection path and none of the PEP 563 /
  forward-reference fragility that comes from calling `get_type_hints` independently.
- **stdlib dataclass and `TypedDict`** adapters read `Annotated` metadata via
  `get_type_hints(include_extras=True)`, which those types require. The fragility is
  accepted because it is confined to them.

### 4.5 Validation engine

All schema types validate and coerce through pydantic's **`TypeAdapter`**, which natively
handles models, pydantic and stdlib dataclasses, and `TypedDict`s
(`TypeAdapter(schema).validate_python(merged)`). One engine, one set of validation
semantics. There is no per-type bespoke validator and no use of `model_validate` as the
universal path. pydantic is therefore a genuine, mandatory core dependency.

### 4.6 Type safety and the typed-open middle ground

The default is fully typed with no `Any` on reads. The typed-open middle ground — a typed
core plus a permissive extra section — is available via `ConfigDict(extra="allow")` on
pydantic schemas (extras land in `__pydantic_extra__`) and via an explicit
`extra: dict[str, Any]` field on dataclasses and `TypedDict`s. Schemaless mode (§7.3) is the
full opt-out.

---

## 5. Sources and loaders

### 5.1 `Source` / `SyncSource` / `AsyncSource`

A source is *where* configuration comes from. The protocol hierarchy has three levels:

```python
@runtime_checkable
class Source(Protocol):
    """Read-only base for all configuration sources."""
    @property
    def name(self) -> str: ...                  # for provenance and error messages
    @property
    def profile(self) -> str | None: ...        # default None (see §5.6)

@runtime_checkable
class SyncSource(Source, Protocol):
    """A source that delivers data synchronously."""
    def fetch(self) -> Mapping[str, Any]: ...
```

The members are declared as read-only properties, not plain attributes: sources are
conceptually immutable, and a plain protocol attribute demands settability under strict
type checking — which a concrete source's read-only `name` property would fail. Both
plain class attributes and properties satisfy the property form.

`Source` is the shared base for mixed-source collections; `SyncSource` and `AsyncSource`
(§5.2) each add the matching fetch contract without re-declaring the shared attributes.
A `BaseSource` convenience class supplies the `profile=None` default so concrete sync
sources need only implement `name` and `fetch`.

The protocol carries no merge-`mode`: precedence is entirely the source list order (§6.1),
and the merge is a single uniform overwrite (§6.3). An earlier `MergeMode.FILL` /
`OVERRIDE` distinction was removed because FILL was position-redundant — the same effect
is expressible by list position — so it earned no permanent second merge mode. (ADR 0036,
retiring ADR 0024.)

### 5.2 `AsyncSource`

Async sources extend `Source` rather than duplicating its attributes:

```python
@runtime_checkable
class AsyncSource(Source, Protocol):
    """A source that delivers data asynchronously."""
    async def fetch_async(self) -> Mapping[str, Any]: ...
```

Sources carry no output generic. The pipeline is "typed at the edges, dynamic in the middle":
`T` lives at `SchemaAdapter` (post-merge); a source-level generic would be erased at the merge
boundary and adds no static guarantees. `ResolutionSpec[T]` keeps `T` cleanly at the schema
level; sources are `Sequence[Source]`, not `Sequence[Source[???]]`. (ADR 0022.)

### 5.3 `Loader`

A loader is *what format* raw bytes are in. The split (Koanf-style) means a new file format
is one small object and a new backend is another, with no combinatorial explosion.

```python
class Loader(Protocol):
    def parse(self, raw: bytes) -> Mapping[str, Any]: ...
```

### 5.4 Built-in sources and their extras

| Source | Purpose | Dependency / extra |
|---|---|---|
| `EnvSource(prefix=..., delimiter="__", *, aliases=...)` | environment variables | core (stdlib) |
| `DotenvSource(path=".env", *, aliases=..., required=False)` | `.env` files | `[dotenv]` (python-dotenv) |
| `FileSource(path, loader=..., *, required=True, storage_options=...)` | local + remote files | core for local I/O; `[remote]` (fsspec) for remote URIs — per-backend extras `[s3]`, `[gcs]`, `[adl]` pull the matching fsspec filesystem |
| `MemorySource(mapping)` | in-process data; the testing workhorse | core |
| `ClickSource` / `TyperSource` | consume an existing Click/Typer command | `[click]` / `[typer]` — `[cli]` installs both (ADR 0054) |
| `ArgparseSource` | consume an argparse namespace | core (argparse is stdlib) |
| `AwsSecretsManagerSource(secret_id, ...)` | AWS Secrets Manager | `[aws]` (boto3) |
| cloud secret/param stores *(PLANNED)* | GCP/Azure/Vault/Consul + AWS Parameter Store | `[gcp]`, `[azure]`, `[vault]`, `[consul]` |

Everything above is shipped **except the rows marked *(PLANNED)***: **AWS Secrets Manager is wired**
(ADR 0053 — the built-in cloud-source pattern; JSON `SecretString` decoded via a reused `Loader`,
`ResourceNotFoundError`→`SourceNotFoundError`, `import_optional`-guarded), but the remaining cloud
stores (GCP/Azure/Vault/Consul + AWS Parameter Store) have no code yet — they land per-backend in a
later stage (their local test stories differ, so each is built and integration-tested on its own).
Remote
`FileSource` **is** wired (ADR 0052) — a remote URI reads via fsspec, reusing the same loader
dispatch as local; `storage_options` passes fsspec backend kwargs (credentials/region/endpoint),
and a URI whose scheme needs an uninstalled backend (`s3://` without `[s3]`) raises the
`pip install confiq[s3]` hint. A missing required remote object raises `SourceNotFoundError` just
like a local one. (Local + remote files, loaders, CLI, and the `aliases` machinery are fully
implemented.)

Loaders: JSON (core), YAML (`[yaml]`), TOML (stdlib `tomllib` on 3.11+, `[toml]` otherwise).

`EnvSource` and `DotenvSource` are the same flat `KEY=VALUE` shape (differing only in input —
`os.environ` vs a parsed `.env`) and share one flat→nested translation. `aliases` maps a config
path to the external var name that fills it — `aliases={"database.url": "DATABASE_URL"}` reads
`$DATABASE_URL` and places it at `database.url`, overriding the prefix convention for that path.
This is the source-side home for externally-fixed var names (`DATABASE_URL`, `PORT`) that do not
fit an app's prefix; a field never declares its own var name (ADR 0048). Alias *targets* are
validated against the schema path table (§6.2 step 4), so a typo fails loudly. (Structured
sources — `FileSource`, `MemorySource` — already speak config paths and take no aliases.)

### 5.5 `required`: source presence

A source's backing input may be absent (a config file that does not exist, a `.env` that
was never written). That "absent" case is a first-class condition, distinct from "present
but malformed" (§5.7). Sources for which absence is meaningful carry a `required: bool`
kwarg; absence of a required source raises `SourceNotFoundError` (a `SourceError`
subclass, §13), and absence of a non-required one contributes `{}`:

- `FileSource(path, *, required=True)` — strict by default; naming a file you do not have
  is almost always a mistake, so a missing file raises. `required=False` → `{}`.
- `DotenvSource(path=".env", *, required=False)` — lenient by default; a missing `.env` is
  the common case. `required=True` → raises.
- `MemorySource` and `EnvSource` carry no flag: an in-process mapping is always present,
  and an env prefix matching nothing is legitimately `{}`, never an error.

Presence is per-source, not a protocol member — only the sources above can be absent, so
the flag stays off the `Source` protocol (§5.1). (ADR 0040.)

### 5.6 `profile`

A source may carry a `profile` tag. When `load(..., profile="prod")` is called, a source
participates only if its `profile` is `None` (untagged sources always participate) or equals
the selected profile. Nothing is auto-discovered; the user composes the list and names the
profile explicitly. Profiles are sugar over the explicit list, not a new precedence
mechanism — the same outcome is expressible by composing different lists.

### 5.7 Malformed input and the loader/source error contract

Distinct from absence (§5.5), an input that is present but broken fails loudly, and the
failure names its source (§2 legibility; §6.4 provenance):

- **The loader raises; the source wraps.** A `Loader.parse` surfaces the format library's
  own error on malformed bytes (`json.JSONDecodeError`, `tomllib.TOMLDecodeError`,
  `yaml.YAMLError`), and rejects a non-mapping top level (a bare list or scalar) with a
  `ValueError`. The owning source catches loader and I/O errors and re-raises
  `SourceError(name, …) from <original>`, so the message names the file and the cause
  chains. A `SourceNotFoundError` and the missing-extra `ImportError` below are *not*
  wrapped — they pass through as themselves.
- **Empty is not malformed.** An empty or whitespace-only file parses to `{}` (YAML's
  `None` result is normalised to `{}`), because "this file supplies nothing" is a valid
  contribution, not an error.
- **A missing optional dependency is a stdlib `ImportError`** naming the extra
  (`pip install confiq[yaml]`), raised at the point the loader/source needs it — an
  install-time programmer error, deliberately not dressed up as a data error. A shared
  `import_optional(name, extra=…)` helper produces these. (ADR 0006, ADR 0041.)

---

## 6. Composition and resolution

### 6.1 Precedence

Precedence is the source list, lowest first. The list is the complete precedence
specification. Higher-index sources win on collision.

### 6.2 The resolver algorithm

Given a `ResolutionSpec` (schema — possibly `None` — sources, profile, plugins):

1. **Profile filter.** If `profile` is given, drop any source whose `profile` is set and
   does not equal it.
2. **Fetch.** Drive each remaining source in order, pairing each source with its output so the
   bind step can detect the *producing* source, not just its name. A normal source's `fetch()`
   (or `fetch_async()`) returns a config-path-shaped `Mapping[str, Any]`. File-backed sources
   read bytes (stdlib for local paths, fsspec for remote) through their `Loader`. Env/dotenv
   sources translate their flat key space to config paths **source-side** (prefix + delimiter
   convention, plus any `aliases`, §5.4). A **binding source** (the CLI sources) instead
   surfaces *raw parameter names + binding markers* via `raw_bindings()` — its config paths
   depend on the schema, so no data is produced here (ADR 0027, 0032).
3. **Adapter.** Resolve the `SchemaAdapter` for the schema type via the pluggy hook
   (`schema=None` selects the schemaless adapter). This moves ahead of merge because the
   next step needs the path table, and the adapter depends only on `schema` + `plugins`
   (ADR 0049).
4. **Bind.** Read `field_metadata` (the path table). Rewrite each binding source's raw names
   into config-path shape: an explicit marker (`ConfigBind` / a generated option's
   `confiq_path`) wins; otherwise the name↔path convention (§10.2) binds against the leaf
   paths (ambiguity → `SchemaError`, no match → non-participating). Validate any source-side
   `aliases` *targets* against the path table here too (a bad target → `SchemaError`). A
   bound entry becomes config-path-shaped like any other before merge, so its leaves collide
   correctly and provenance names the binding source (ADR 0049, 0027, 0048).
5. **Merge.** Deep-merge the resulting entries low → high: later wins, uniformly. Lists
   are replaced, not concatenated, and a type conflict (scalar over map, or vice versa)
   replaces wholesale rather than raising — validation (step 7) is the sole refusal locus
   for a genuinely wrong shape. A parallel `Provenance` map (`Mapping[str, str]`: dotted
   field path → source name) records the winning source name per leaf. The step produces a
   `ResolvedSnapshot(merged, provenance)`. (ADR 0037.)
6. **Coerce.** Apply each field's `ConfigField.parser` to raw string values before validation;
   a raising parser folds into `ConfigValidationError` with the field path + provenance
   (ADR 0045).
7. **Validate.** `adapter.validate(merged)` constructs the typed value. On failure, raise
   `ConfigValidationError` carrying the field path and the provenance (which source supplied
   the offending value) in the human-readable message.
8. **Return** the value; the `ResolvedSnapshot` is retained at the color-agnostic seam for a
   future `explain()` (ADR 0043).

### 6.3 Merge semantics

Deep-merge, list-replacement, uniform overwrite. List-replacement is deliberate and legible:
a higher source's list replaces a lower one's rather than accumulating, so "reset this list"
is expressible. `None` from a higher source is data — it overwrites a lower non-`None` value
(unset is modelled at the source: env/CLI omit the key, they do not send `None`). A
type conflict overwrites wholesale and the merge never raises on structure; the merge stays
schema-agnostic, and a wrong shape is caught at validation, which can name the field and its
winning source. (ADR 0037.)

### 6.4 Provenance

Provenance is tracked during the merge **and surfaced in error messages** — a validation or
missing-field error names the source responsible, rather than provenance being internal
bookkeeping only.

### 6.5 Named pipeline boundary types

Multi-value boundaries in the resolver pipeline are named when their fields constitute a
contract. Single-value intermediates remain plain types. (ADR 0023.)

| Name | Kind | Fields / alias target | Purpose |
|------|------|-----------------------|---------|
| `ContributedEntry` | frozen dataclass | `source: Source`, `data: Mapping[str, Any] \| None` | Unit passed from fetch step to the bind step; carries the *source* (not just its name) so the bind step can detect binding sources. `data` is `None` for a binding source, whose contribution the bind step computes (ADR 0049) |
| `FetchedEntry` | frozen dataclass | `name: str`, `data: Mapping[str, Any]` | Config-path-shaped unit passed from the bind step to merge; a binding source's rewritten entry and a normal source's data are indistinguishable here |
| `RawBinding` | frozen dataclass | `name: str`, `value: object`, `bind: ConfigBind \| None` | One explicitly-set CLI parameter surfaced by a `BindingSource.raw_bindings()` for the bind step (ADR 0027, 0032) |
| `ResolvedSnapshot` | frozen dataclass | `merged: Mapping[str, Any]`, `provenance: Provenance` | Output of the merge step |
| `Provenance` | `TypeAlias` | `Mapping[str, str]` | Dotted field path → winning source name |
| `FieldAnnotations` | `TypeAlias` | `Mapping[str, list[Any]]` | Return type of `SchemaAdapter.field_metadata`; keyed by dotted field path (the path table, ADR 0026) |
| `PluginList` | `TypeAlias` | `tuple[object, ...]` | Ordered immutable sequence of pluggy plugins in `ResolutionSpec` |

---

## 7. Loading API

### 7.1 The resolution spec

Everything that determines a load — the schema, the ordered sources, the selected profile,
and any plugins — is bundled into one immutable value:

```python
@dataclass(frozen=True)
class ResolutionSpec(Generic[T]):
    schema: type[T] | None                       # None selects schemaless resolution
    sources: Sequence[Source]
    profile: str | None = None
    plugins: PluginList = ()                     # custom sources / adapters / transforms
```

`load()` (§7.2) and `ConfigHandle` (§8) both take a spec, so they cannot drift: a handle is
exactly "hold this spec and re-run it." Plugins live here, not on the handle, because they
describe *how to resolve*, not the reload lifecycle — and they therefore persist across a
handle's reloads for free, because the spec persists.

### 7.2 `load` (synchronous)

```python
@overload
def load(spec: ResolutionSpec[T]) -> T: ...
@overload
def load(schema: type[T], sources: Sequence[SyncCapable], *,   # SyncCapable = SyncSource | BindingSource
         profile: str | None = None, plugins: PluginList = ()) -> T: ...
@overload
def load(schema: None, sources: Sequence[SyncCapable], *,      # schema=None → SchemalessConfig
         profile: str | None = None, plugins: PluginList = ()) -> SchemalessConfig: ...
```

The sync entry points accept `Sequence[SyncCapable]` (`SyncSource | BindingSource`) rather than
`Sequence[SyncSource]`, so the eager-snapshot CLI sources (which are `BindingSource`s, not
`SyncSource`s) type-check into `load()` while an `AsyncSource` stays a static type error.
`ResolutionSpec.schemaless(sources, ...)` pins `T = SchemalessConfig` for the schemaless spec
form, and `spec_with(spec, overrides)` (§11.2) returns a new spec with a highest-precedence
`MemorySource(overrides)` appended.

The convenience form builds a `ResolutionSpec` internally; both forms run the same resolver
(§6.2). `load()` accepts only synchronous sources. Handed an `AsyncSource`, it raises a clear
error directing the caller to `load_async()`. There is no `ThreadPoolExecutor` +
`asyncio.run()` bridge — that approach is explicitly rejected for its event-loop and
`ContextVar`-propagation hazards.

### 7.3 `load_async`

```python
@overload
async def load_async(spec: ResolutionSpec[T]) -> T: ...
@overload
async def load_async(schema: type[T], sources: Sequence[Source], *,
                     profile: str | None = None, plugins: PluginList = ()) -> T: ...
```

Drives `AsyncSource`s natively (gathered on the running loop) and sync sources inline.

### 7.4 Schemaless

A spec with `schema=None` (or `load(None, sources)`) returns a `SchemalessConfig` — a
read-only `Mapping` supporting `config["a"]["b"]` subscript access. No types, no validation,
no nesting guarantees beyond the merged structure.

---

## 8. Configuration lifecycle: value vs handle

### 8.1 The default

Call `load()`, receive a value, use it. This covers the overwhelming majority of cases and
is what makes testing trivial.

### 8.2 `ConfigHandle`

For applications that must pick up configuration changes at runtime, `ConfigHandle[T]` is the
explicit opt-in. It holds a `ResolutionSpec`, recomputes it on `reload()`, swaps the current
snapshot atomically, and notifies subscribers. It ships in the `[reload]` extra (§12.4), so
the load-once majority — and the core itself — carry none of its machinery.

```python
class ConfigHandle(Generic[T]):
    def __init__(self, spec: ResolutionSpec[T]) -> None: ...
        # rejects a non-frozen schema — see below

    @property
    def current(self) -> T: ...                            # property (§14.1 #1, resolved)

    def reload(self) -> T: ...                             # returns the new snapshot (ADR 0051)
    async def reload_async(self) -> T: ...                 # async reload ships (ADR 0050)

    def on_reload(self, fn: Callable[[T, T], Any]) -> Callable[[], None]: ...
        # fn receives (old, new); returns a disconnect callable (§14.1 #3, resolved)
```

A handle is constructed from a spec (`ConfigHandle(ResolutionSpec(Settings, sources=[...]))`),
so it shares the resolution surface with `load()` and cannot drift from it.

- **A handle requires a frozen schema.** Its lock-free read guarantee (§9.1) depends on each
  snapshot being immutable, so the constructor rejects a non-frozen schema (non-frozen pydantic
  model, non-frozen dataclass, TypedDict, or schemaless) with a `SchemaError` naming the frozen
  remediation — in the §13 taxonomy, not a bare `ValueError` (ADR 0051). Plain `load()` still
  accepts non-frozen schemas per the §3 gradient; only the *live, shared* path is constrained.
- **No `loop` parameter and no per-handle plugin registry.** Plugins come from the spec
  (§7.1) and persist across reloads because the spec persists. `reload()`/`reload_async()`
  return the freshly-computed snapshot (ADR 0051). Async subscribers are driven by
  `reload_async()`; a live async subscriber makes sync `reload()` refuse with a `RuntimeError`
  pointing to `reload_async()` (registering one commits the handle to the async path) rather than
  silently skipping it — the dispatch conditions only on facts knowable at each call site
  (ADR 0051). There is no scheduling of async subscribers from sync `reload()` (§9.3).

### 8.3 Ambient access (user-owned)

`confiq` never owns a global, but an application may build its own. Two cases decide the shape:

- If config draws on **no runtime-derived source** (env and files only), an eager module-level
  value works directly:
  ```python
  # myapp/config.py
  settings = load(Settings, sources=[EnvSource("APP"), FileSource("config.toml")])
  ```
- If config draws on the **CLI**, the value cannot exist at import time (the CLI is not parsed
  until a command runs), so the singleton is *initialized in the entry point* — typically the
  app callback, once for the whole command tree (§10.6):
  ```python
  # myapp/config.py
  _settings: Settings | None = None
  def init_settings(*, cli: SyncSource | None = None) -> Settings:
      global _settings
      _settings = load(settings_spec(cli=cli)); return _settings
  def settings() -> Settings:
      if _settings is None: raise RuntimeError("call init_settings() in your entry point")
      return _settings
  ```
  This keeps immutability (each value is frozen) and is type-honest, at the cost of an accessor
  call (`settings()`) rather than a bare name. The holder is the user's; it is not
  `ConfigHandle` and carries none of its reload machinery.

### 8.4 Ambient access via `LazyConfig` (the proxy option)

For applications that want a literal `from myapp.config import config` bare name that still
reflects CLI overrides, `confiq` offers an opt-in lazy proxy. It is the only construct that
places a `confiq` object on the read path (§2 principle 6, the library owns no mutable
state), and is deliberately marked as such.

The singleton is one object — **`LazyConfig[T]`**, a lifecycle handle and a sibling to
`ConfigHandle` (§8.2). It exposes the read surface and the lifecycle controls as named members,
so nothing is returned as a tuple:

```python
class LazyConfig(Generic[T]):
    def __init__(self, spec_builder: Callable[..., ResolutionSpec[T]]) -> None: ...
    @property
    def value(self) -> T: ...                                  # the proxy, typed as the schema
    def bind(self, *, cli: SyncSource | None = None) -> None: ...  # resolve the base value once
    def reset(self) -> None: ...                               # clear it (used by pytest-confiq, §11.3)
    @property
    def bound(self) -> bool: ...
```

`bind`/`reset`/`bound` live on the handle, not on the proxy, on purpose: `value` forwards every
attribute to the wrapped config, so a `bind` method on *it* would shadow a schema field named
`bind` (a plausible field). Putting control on the handle keeps a clean, well-named `bind` with
no shadowing and no invented dunder.

```python
# myapp/config.py
from confiq import LazyConfig

config_handle = LazyConfig(settings_spec)   # the lazy handle; bind it in the entry point
config = config_handle.value                # the proxy, typed Settings, for everyday imports
```

```python
# myapp/__main__.py
from myapp.config import config_handle

@app.callback()
def _bootstrap(database_host: Annotated[str | None, typer.Option()] = None):
    config_handle.bind(cli=TyperSource())   # resolve the base once, post-parse (§10.6)
```

```python
# anywhere
from myapp.config import config
host = config.database.host                 # type-checked at use sites; CLI-aware after binding
```

`LazyConfig` takes the same spec-builder the rest of the app uses
(`settings_spec(*, cli=...) -> ResolutionSpec[T]`) and is generic in `T`, so `value` — and the
re-exported `config` — is typed as the schema with no manual `cast`. `config_handle.value`
returns the same stable proxy on every call; you grab it once, import it everywhere, and
binding/override changes happen inside it.

**Resolution is override-aware, not cache-only.** On each access the proxy first checks the
active `context.override()` ContextVar (§11); if an override is in scope it overlays it,
otherwise it returns the base value set by `bind(...)`. The overlay is a **snapshot
overlay**: the override mapping is deep-merged (§6.3 semantics) over the base value's
mapping form and validated through the spec's adapter into a fresh `T`, cached per
override installation — so nested access (`config.database.host`) sees overrides, every
read stays typed as the schema, and an override that violates the schema fails validation
loudly instead of leaking an unvalidated value. First-hop attribute substitution is
explicitly rejected (it cannot see past the first attribute hop). This is what keeps the
testing story unified (§11.3) — the same `context.override()` primitive flows through the
proxy, so tests need no separate proxy-lifecycle machinery. (ADR 0031.)

What the proxy keeps and what it costs:

- **Keeps:** immutability of the resolved value (the base is frozen); static type safety at use
  sites (`config` is typed as the schema everywhere — `LazyConfig`'s generic return removes the
  earlier manual `cast`).
- **Costs:** (1) reads can raise before `bind()` runs — mitigated by binding in the app callback,
  after which reads do not raise; (2) a discipline of not dereferencing `config` at literal
  import time (the proxy raises a clear "not bound" error if violated, rather than returning
  pre-CLI values); (3) it is a proxy, so `isinstance` works (via `__class__` forwarding) but
  identity edges are imperfect; (4) the §9.1 single-atomic-read property does not hold on the
  proxy path — each access is a `ContextVar` check plus the base read (cheap, and a no-op when no
  override is active, i.e. normal production).

  The proxy contract, stated precisely (it is a read-*through* handle, not a value):
  - `isinstance(config, Settings)` is `True`; but `type(config) is Settings` is `False`, and
    `==`/`hash` are the proxy's own identity — compare `config.field`, not `config` itself.
  - The proxy is **read-only** (`config.x = v` raises `AttributeError`) and **not copyable**
    (`copy`/`deepcopy` raise `TypeError` — copy `config_handle.value`'s target instead).
  - A direct attribute read on an **unbound** proxy raises `AttributeError` naming the `bind()`
    fix; because that is an `AttributeError` (deliberately *outside* the `ConfiqError` tree — it
    is a programmer usage error surfaced through attribute-access semantics), `hasattr(config, x)`
    and `getattr(config, x, default)` degrade normally rather than crashing third-party code.

If you would rather the control be discoverable *through* the proxy than via a separate handle
name, the collision-safe form is a single reserved attribute, `config.__confiq__.bind(...)` —
the dunder namespace cannot clash with a schema field. The handle above is preferred for its
cleaner surface.

The value and accessor forms (§8.1, §8.3) remain the recommended, maximally-testable defaults;
`LazyConfig` is the ergonomic option carrying the named costs above.

---

## 9. Concurrency and async model

### 9.1 Lock-free reads

A `ConfigHandle` requires a frozen schema (§8.2), so its current snapshot is always immutable
and `current` is a single atomic attribute read under CPython — no torn-read hazard, no lock.
Thread safety is a property of immutability, not of a locking discipline. (Plain `load()` may
return a mutable value per the §3 gradient, but that value has no shared identity to protect;
the live, shared path is the one held to frozenness.)

### 9.2 Reload is copy-on-write

`reload()` recomputes a fresh snapshot off to the side, then takes a short write lock only to
swap the reference. A `ReentrancyGuard` fast-fails if a reload triggers a reload. All
concurrency cost lives here, in the opt-in path — never in the common `load()` case.

### 9.3 Notifications

`on_reload` is modeled on a **blinker** signal: weak-referenced subscribers (a handler's
lifetime is not accidentally extended) and documented connect/disconnect semantics, instead
of a bespoke callback list. (blinker is pulled in by the `[reload]` extra, not the core.)
`on_reload` returns a disconnect callable; note that callable holds `fn` *strongly*, so the
weak-ref auto-cleanup only applies once the disconnect handle is discarded (a subscriber you
neither disconnect nor otherwise keep alive is collected and stops firing). This "a *collected*
subscriber silently stops firing" is deliberate and correct — it is a *dead* observer vanishing,
categorically different from *skipping a live* subscriber, which the sync-`reload()`-with-an-
async-subscriber path refuses loudly rather than silently skips (ADR 0051). Refusal-over-
degradation applies to the live case; GC of a dead observer is not a degradation.

Subscribers may be sync or async, but each kind is tied to the matching reload entry point —
there is no cross-scheduling and no stored event-loop reference. `reload()` performs the swap,
releases the lock, then runs sync subscribers **inline in the caller's thread**; reload is not
a hot path, so no daemon thread is needed. `reload_async()` performs the swap and then awaits
async subscribers (gathered) on the running loop, running any sync subscribers inline. An
async subscriber registered on a handle that is only ever driven by sync `reload()` is a usage
error and is reported as one, rather than supported via a background loop. No subscriber may
call `reload()` synchronously (the `ReentrancyGuard` fast-fails).

### 9.4 Async entry points

Async is a clean second entry point, not a colored twin of every method. `SyncSource` and
`AsyncSource` share the read-only base `Source`; `load`/`reload` accept `Sequence[SyncCapable]`
(`SyncSource | BindingSource` — the synchronously-drivable sources); `load_async`/`reload_async`
accept `Sequence[Source]` (the shared base, covering both sync and async sources). Sync entry
points reject async sources rather than bridging them.

Implementation requirement: the resolver pipeline (§6.2) is **color-agnostic except at
the fetch step** — profile filtering, merge, provenance, adapter resolution, coercion,
and validation are the same functions on both paths, and the entry points are thin
shells over them. Hand-maintained sync/async twins that can drift are accidental
complexity of the representation, not of async support (ADR 0035); Python's two calling
colors are the environment's essential complexity, accepted rather than litigated.
(Whether async entry points ship at all, and where, remains the §14.2 open question.)

---

## 10. CLI integration

### 10.1 Philosophy

`confiq` is a **consumer** of whichever CLI framework the application already uses — Typer,
Click, or argparse. It never owns or generates the command by default. This keeps integration
seamless and keeps the framework's full option surface out of `confiq`'s maintenance burden.
The CLI is just another source, slotted into the precedence list at the position the
application chooses (typically highest).

### 10.2 Consumer path (default)

The application writes its command as normal. `confiq` reads only the parameters the user
**explicitly set** and folds them in as a source. Two rules make this painless:

- **Defaults live only in the schema.** Consumer-path CLI options omit their defaults (or use
  an unset sentinel), so a value is never declared in two places.
- **Convention binding.** A parameter maps to its config path by its exact
  underscore-joined name, validated against the schema's path table (§4.3): the candidate
  paths are every dotting of the parameter's underscores, intersected with the table's
  leaf paths. Exactly one match binds (`database_host` ↔ `database.host`); more than one
  is a `SchemaError` naming the candidates; zero matches means the parameter is an
  ordinary CLI flag and does not participate. An explicit `ConfigBind("database.host")`
  annotation (Typer/Click) — or a `bind={...}` dict entry (argparse) — is needed when the
  CLI name and the config path genuinely diverge (abbreviations like `db_host`), and
  `ConfigBind(None)` opts a matching parameter out. (ADR 0027, superseding ADR 0011's
  opt-in model.)

```python
@app.command()
def main(
    database_host: Annotated[str | None, typer.Option()] = None,      # convention-bound to database.host
    log_level: Annotated[str | None, typer.Option(), ConfigBind("logging.level")] = None,  # diverges: explicit bind
) -> None:
    settings = load(Settings, sources=[
        EnvSource(prefix="APP"),
        TyperSource(),            # highest precedence; contributes only explicitly-set options
    ])
```

### 10.3 Explicit-set detection

- **Click/Typer:** use `Context.get_parameter_source()` to distinguish a user-supplied value
  from a framework default.
- **argparse:** prefer sentinel defaults — arguments declared with `default=argparse.SUPPRESS`
  are simply absent from the namespace when unspecified, which is unambiguous. Comparing
  against `parser.get_default()` is the degraded fallback (it cannot tell a user-supplied
  value that equals the default).

`ClickSource`/`TyperSource` capture the active command `Context` **eagerly at
construction**: the explicitly-set parameters, their values, and their binding markers
are read into an immutable snapshot, and no `Context` reference survives `__init__`.
`fetch()` is a pure replay of that snapshot, so a CLI source held in a `ResolutionSpec`
behaves deterministically under `ConfigHandle.reload()` — files and env re-read; the CLI
layer replays the invocation, which has not changed. The `get_current_context()` grab in
the constructor is the library's one documented use of ambient state, confined to the
line where the user visibly wrote the constructor call inside a running command.
(ADR 0032.) Since typer 0.26.0 vendored Click privately, `TyperSource` reads Typer's own
context stack first and falls back to click's for typer < 0.26 (ADR 0054); the two sources
still share one capture path, because the two `Context` types remain structurally identical
for everything the snapshot reads.

### 10.4 Opt-in generator

For applications that want a single declaration site (add a field → get a flag),
`options_from(schema)` emits options from the schema. Because `confiq` controls the
generated options, it sets their defaults to the unset sentinel automatically, so the
"no duplicated default" property comes for free on this path. Both paths obey the same
name↔path convention — the consumer path runs it backward (parameter → path), the generator
runs it forward (path → parameter); they never disagree. Generated options are emitted as a
`click.Option` subclass carrying the dotted path directly on the option object (imperative
`params=[...]` construction has no function annotation to hang `ConfigBind` on); the
snapshot step prefers that attached path over annotations over convention, on both paths.
(ADR 0032.)

### 10.5 Framework support is asymmetric

| | Consume (read what the user set) | Generate (emit options from schema) |
|---|---|---|
| Click | easy — `Context` + `get_parameter_source()` | easy — imperative (`params=[...]`) |
| Typer | easy — its own `Context`, structurally Click's | awkward — signature-driven; params can't be injected |
| argparse | awkward — sentinel needed, no annotations | easy — imperative (`add_argument`) |

Each framework is hard on exactly one side; Click is easy on both. The generator therefore
lives most naturally at the Click layer. This asymmetry is documented rather than hidden behind
a promise of symmetric behavior.

**Typer generation has no drop-to-Click path (typer ≥ 0.26).** Vendoring made Typer's option
and command classes a separate lineage from the installed click's, and upstream withdrew
Click-level interop outright, so `options_from`'s `click.Option` objects cannot be handed to a
Typer app. Typer generation, if it is ever built, needs a Typer-aware command factory emitting
Typer's own parameters — not a bridge. Consumption is unaffected: `TyperSource` reads Typer's
context stack directly (ADR 0054).

### 10.6 Bootstrapping ambient config in the app callback

When the CLI is a source, ambient config (§8.3, §8.4) is established **once** in the Typer/Click
app callback, which runs before any command in the tree (including nested sub-apps), so no
command repeats the load:

```python
from .config import config_handle, config   # handle for bootstrap; config (proxy) for use

@app.callback()
def _bootstrap(database_host: Annotated[str | None, typer.Option()] = None):   # global config flags
    config_handle.bind(cli=TyperSource())   # resolve the proxy's base once, post-parse

@app.command()
def serve():
    run(config)                              # ambient value, already bound
```

Config-overriding flags live on the callback (group-level), not on individual subcommands: the
callback parses before a subcommand's own options exist, and a flag that tweaks *configuration*
is naturally global. Per-command flags that are not config stay on their command. (If a config
flag must live on a single subcommand, a `@with_config`-style decorator on that command performs
the bind at command-invocation time instead.)

---

## 11. Testing

### 11.1 Why the value path is trivial to test

A first-class goal, not a consequence. Because configuration is a plain value with no global
identity, a test constructs the value it wants instead of mutating and restoring shared state.

### 11.2 Primitives and fixtures

The core provides the primitives the testing story rests on: `MemorySource` (in-process
data), `context.override(data)` (a `ContextVar`-based scoped **data overlay**, async-safe,
read only by the `LazyConfig` proxy — `load()` never consults it, staying a pure function
of its arguments), and `spec_with(spec, overrides)` (a pure helper returning a new
`ResolutionSpec` with a `MemorySource(overrides)` appended at highest precedence — the
"splice one key" operation as explicit data flow). A `pytest-confiq` plugin — modeled on
Rust Figment's `Jail` — delivers the fixtures:

- a `config` fixture that builds from a `MemorySource` base, overridable per test and per
  parametrization;
- an autouse isolation fixture that scrubs `os.environ` and chdirs to a tmp path,
  Jail-style, so no environment or file source finds anything unless a test adds data
  explicitly — what `monkeypatch` otherwise forces you to do by hand. Isolation works on
  the *inputs* (the environment itself), never by intercepting `load()`;
- layering helpers (sugar over `spec_with`) so a test can say "the production sources, but
  with this one value overridden" without rebuilding the stack;
- async support via `context.override()`, giving per-task config isolation in async tests
  of proxy-reading code.

Two requirements fall back onto the core so the plugin stays thin: `MemorySource` and
`override()` must be ergonomic, and `spec_with` must make splicing or overriding a single
key in an existing source list one call. (ADR 0028, amending ADR 0016.)

### 11.3 Testing code that uses `lazy_config`

`lazy_config` (§8.4) reintroduces a process-global value — the situation that makes
`pytest-django` necessary — so code that reads the ambient `config` needs lifecycle handling in
tests. Two design choices make this nearly free rather than a second isolation system:

- **The proxy is override-aware.** Because each access consults the active `context.override()`
  ContextVar before its bound base, the *existing* `config` fixture and autouse reset (§11.2)
  flow straight through the proxy. A test sets `context.override({...})`; code-under-test doing
  `from myapp.config import config; config.x` sees the overridden value; the autouse reset
  clears it afterward. No proxy-specific set/reset machinery is required beyond the binder
  (below).
- **Unbound by default between tests.** The app callback that calls `config_handle.bind(...)`
  does not run under pytest, so the proxy is left *unbound*; an accidental read of ambient
  `config` in a test that did not establish one raises a clear "not bound" error rather than
  leaking a stale value or a production default. `pytest-confiq`'s autouse fixture calls the
  `LazyConfig` handle's `reset()` between tests to guarantee this; tests that want ambient config
  establish it via the `config` fixture / `context.override()` (or, when they need a concrete
  bound base, `config_handle.bind(...)` with a `MemorySource` standing in for the CLI layer).

The honest asterisk: testing `lazy_config`-based code is still *less* trivial than the
value/accessor path — you establish ambient config through a fixture and rely on autouse
isolation, rather than simply passing a value in. That is the inherent cost of ambient access,
with a real upside: you can test code that reads the global *without* refactoring it to accept a
config parameter (the reason `pytest-django` exists). Non-proxy users are unaffected — their
testing is §11.1–§11.2 with no proxy surface.

(Had the proxy been cache-only instead of override-aware, `pytest-confiq` would have needed its
own `set`/`reset` fixtures and a second autouse reset distinct from the override path; the
override-aware design in §8.4 is what avoids that fork.)

---

## 12. Extension and packaging

### 12.1–12.3 Extension surfaces

- **Built-in cloud sources behind extras** (`confiq[aws]`, …) ship in-tree so they share one
  `Source` contract and release in lockstep with it.
- **A `confiq.sources` entry-point group** lets third parties publish sources discovered
  without a pull request. Consumption semantics: the group is a *discoverability naming
  convention* — tooling and humans can enumerate installed source packages — and the core
  does nothing with it at runtime. Sources are classes the user imports and instantiates
  into the source list; there is no registry, no auto-loading, and confiq does not
  register its own built-ins in the group.
- **pluggy hookimpls** cover stateless transforms and adapter resolution, including
  `confiq_get_schema_adapter`.
- **Plugins are part of the resolution spec** (§7.1), not a handle responsibility: the same
  `plugins` apply whether you `load()` once or hold a `ConfigHandle`, and they persist across a
  handle's reloads because the handle persists its spec. (If per-handle plugin *isolation* ever
  proves necessary, it returns as a spec built per handle — never as a handle-owned manager.)

### 12.4 Dependency discipline

The governing rule (Koanf-style): **the core depends on nothing optional.** Core runtime
dependencies are `pydantic` (≥2), `pluggy`, and `typing-extensions` (for `Self`/`Protocol`
back-compat on the 3.10 floor). Everything else sits behind an extra:
CLI frameworks (`[click]`, `[typer]`; `[cli]` for both), dotenv (`[dotenv]`), non-stdlib loaders (`[yaml]`, `[toml]`), remote
filesystems (`[remote]`, fsspec), cloud SDKs (`[aws]`/`[gcp]`/`[vault]`), and the
**live-reload layer** — `ConfigHandle`, its notification machinery, and `blinker` — behind
`[reload]`. A user who only reads environment variables installs nothing but the core, and the
load-once majority never pays for reload. (This corrects `design_c`'s treatment of
`typer`/`python-dotenv` as mandatory; local file reading uses the stdlib, so fsspec is needed
only for remote URIs.)

---

## 13. Error handling

```
ConfiqError                     # base
├── SourceError                 # a source failed to fetch (malformed input, I/O)
│   └── SourceNotFoundError     # a required source's backing input is absent (§5.5, ADR 0040)
├── SchemaError                 # no adapter for the schema type, or schema misconfigured
│   ├── SecretMaskingError            # secret=True on a kind that cannot mask (§3, ADR 0039)
│   ├── AmbiguousBindingError         # a CLI param name matches >1 config leaf (§10.2, ADR 0027)
│   ├── UnknownBindTargetError        # a ConfigBind / alias target is not a schema field (ADR 0027, 0048)
│   └── IntermediateBindTargetError   # a ConfigBind / alias target is a node, not a leaf (ADR 0049)
├── MissingConfigError          # a required field is absent from all sources
└── ConfigValidationError       # validation/coercion failed
```

A missing *optional dependency* is intentionally not in this tree: it surfaces as a stdlib
`ImportError` naming the extra (§5.7), because it is an install-time programmer error, not a
runtime config failure.

Both `MissingConfigError` and `ConfigValidationError` hold `contexts: tuple[ErrorContext,
...]` — one `ErrorContext(field_path, sources)` frozen dataclass per failure, because the
validation engine (§4.5) reports every failure in one raise and confiq preserves that
yield rather than reporting only the first. `field_path` values are dotted paths in the
§4.3 path-table key space. Classification: if every underlying error is a missing-field
error, raise `MissingConfigError`; otherwise raise one `ConfigValidationError` carrying
every context, missing and invalid alike. The human-readable message renders all
contexts; `err.field_path` and `err.sources` remain as forwarding properties to
`contexts[0]` for the dominant single-error case, so existing call sites require no
changes. `ErrorContext` is a standalone passable value: an error formatter or logger can
accept it directly without the full exception object, and it is the single evolution
point for future diagnostic extensions (provenance detail, secret-masking flags,
structured output). (ADR 0025, amended by ADR 0029.) Secret fields
(`ConfigField(secret=True)`) are masked in all error output wherever field metadata
exists.

Two obligations apply to every error the library raises:

- **A declared guarantee is honored or refused, never silently dropped.**
  `ConfigField(secret=True)` on a schema kind that cannot honor masking raises
  `SchemaError` at load, naming the field path, the schema kind, and the fix — use a
  pydantic model or dataclass for that structure, or remove the flag. (§3, ADR 0033.)
- **Every refusal names a remediation path.** A "no" without a "do this instead" is a
  bug against the UX principle (§2). The exemplar is `load()` rejecting an async
  source while pointing the caller to `load_async()` (§7.2); the same standard applies
  to the frozen-schema requirement (§8.2), the unbound proxy read (§8.4), the
  CLI-binding ambiguity error (§10.2), and the secrets refusal above.

---

## 14. Provisional decisions and open questions

### 14.1 Provisional signature decisions

These signature-level points were not separately deliberated; the conservative call is
recorded here and is easy to override. (The earlier `plugins`-on-handle and `loop`-parameter
questions are now resolved — plugins live in the `ResolutionSpec` (§7.1) and the `loop`
parameter is gone (§9.3) — so they are no longer open.)

1. **`ConfigHandle.current` is a property** (not a method). **RESOLVED: kept as a property** —
   reads more naturally for an immutable snapshot and avoids `handle.current()`.
2. **`load()`'s convenience form takes `schema` and `sources` positionally** (positional-or-
   keyword), with `profile` and `plugins` keyword-only. **RESOLVED (ADR 0046):** kept
   positional-or-keyword — the signature §7.2 already writes and every example uses; the
   keyword-only-`sources` alternative was declined as needlessly restrictive. `load_async`
   mirrors it. (The skeleton's positional-only `/` was a bug that forbade the
   `load(Settings, sources=[...])` form the examples rely on.)
3. **`on_reload(fn)` passes `(old, new)` and returns a disconnect callable. — RESOLVED: kept.**
   `old` earns its place — a diffing subscriber ("act only on what changed") needs it, and
   passing it is free since the handle holds it during the swap. The disconnect return suits
   weak-referenced blinker subscribers better than returning `fn`. (ADR 0051 records the
   surrounding reload reconciliations.)

### 14.2 Open scope questions

These resolve through discussion as implementation reaches them (a culling pass was
declined — ADR 0034). Items #1 and #2 are now **resolved** and kept here as a record;
#3 and #4 remain open, each listed with the criterion that decides it.

1. **`MergeMode.FILL`: keep or remove. — RESOLVED: removed (ADR 0036).** FILL was
   position-redundant (a FILL source anywhere equals the same source at the bottom of the
   list with `OVERRIDE`); its only non-redundant value was enforced intent — a fallback
   that cannot be ruined by reordering. That guard rail did not justify a permanent second
   merge mode plus its provenance bookkeeping, and the reorder footgun it guarded is already
   diagnosable via provenance (§6.4). The entire `mode` concept was removed with it (§5.1,
   §6.3); re-adding later is additive and non-breaking.
2. **Schemaless mode: keep or remove. — RESOLVED: kept (ADR 0038).** An empty `BaseModel`
   with `extra="allow"` is a different product (it still requires a pydantic model), and
   ADR 0037 already leans on schemaless as a reliable untyped debugging view; the untyped
   merged-config capability is inherent to the config problem. The `SchemalessAdapter` is
   trivial and the `T | SchemalessConfig` union stays hidden behind the `load()` overloads.
3. **Async source support: a problem-boundary question.** (Reframed by ADR 0035 — the
   prior cost framing is retired; maintenance burden is not an admissible factor.)
   Decided per capability:
   - **Async fetch** (`AsyncSource`, `load_async`, `resolve_async`). **RESOLVED: ships
     (ADR 0047).** Async-native fetch is a mainstream shape a config source takes and is
     within the problem's reasonable range; the no-async workaround corrupts provenance
     (await-then-`MemorySource` records the origin as "memory"), a defect against §1; and
     the color-agnostic pipeline (§9.4) was built for exactly this, so the entry points are
     drift-proof shells over `_resolve_from_fetched`. Fetch uses **unbounded
     `asyncio.gather`** (order-preserving; concurrency bounding is the source's/client's
     responsibility, not a spec knob) with sync sources run inline and **no `to_thread`
     bridge** in either direction (it would drop ContextVars, the ADR 0013 hazard). Async
     *built-in* sources are still not shipped — a built-in wrapping a sync-first SDK would be
     false structure; the extension point receives a genuinely-async source (e.g. a remote
     `FileSource` over fsspec `AsyncFileSystem`) honestly when one is built.
   - **Async reload** (`reload_async`). **RESOLVED: ships (ADR 0050).** It is *essential*
     complexity of the live-reload sub-problem in async services — a blocking re-fetch parks the
     event loop under traffic — and `load_async` (the fetch half) already exists, so it is a thin
     shell over the same swap/notify skeleton as sync `reload()`, differing only at the recompute
     (`await load_async`) and an async-subscriber gather. With this and the fetch half, §14.2 #3
     is fully resolved.
4. **Resolution observability as first-class surface.** Provenance is already tracked
   (§6.4) and surfaced in errors; an `explain()`-style dump (merged snapshot +
   per-leaf source attribution, secrets masked) would attack the "breaks invisibly"
   problem directly on the success path, not just on failure. **The structural half is
   resolved (ADR 0043):** the resolver retains the raw `ResolvedSnapshot` at its
   color-agnostic seam, so `resolve()`'s return is unchanged but a future `explain()` is a
   projection of an already-available value, not a pipeline retrofit. The *surface* itself
   remains a candidate feature needing its own ADR (where it lives — API, CLI, or both;
   masking rules; output shape).

---

## 15. Non-goals

Deliberate refusals, recorded so they do not creep back in:

- **No value interpolation or expression DSL.** Computed values are a source's job, not the
  value's.
- **No magic environment discovery.** Precedence and profile selection are always explicit.
- **No library-owned global singleton.** Ambient access is built by the application.
- **`confiq` does not own the CLI command.** It consumes the user's command by default; the
  generator is additive and never required.
- **No mandatory optional dependencies.** The core installs no CLI framework, dotenv parser,
  remote-filesystem layer, or cloud SDK.
- **No sync→async bridging.** Sync entry points reject async sources rather than smuggling an
  event loop into a worker thread.
- **No background machinery for reload.** Reload runs subscribers inline on the thread that
  called `reload()` / the loop that awaited `reload_async()`; there is no daemon thread and no
  stored event loop. Live reload is also not in the core — it lives behind the `[reload]` extra.
- **No breadth for its own sake.** Every public concept taxes every user who must read
  about it to rule it out. A capability serving users outside the §1 triangle must earn
  its concept cost explicitly — an orientation, not a rule (§2, ADR 0034).
