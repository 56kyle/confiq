# confiq: Comparative Analysis and Design Ideas

> Compares confiq (Design C) against spf13/viper + spf13/cobra (Go) and argparse / click / typer
> (Python CLI) to identify gaps, strengths, and design directions.

---

## Part 1: confiq vs viper — Configuration Management

Both are multi-source config libraries. Viper is the dominant Go solution; confiq is the target
Python design.

### 1.1 Core Philosophy

| Dimension | viper | confiq (Design C) |
|-----------|-------|-------------------|
| Mental model | Single global instance with mutable state | `load()` returns an immutable value; no global state |
| Primary API | `viper.GetString("key")` — string key access on a shared object | Attribute access on a frozen pydantic `BaseModel` |
| Schema coupling | Loose; unmarshal into a struct post-load | Tight; schema drives resolution, validation, and field metadata |
| Global singleton | Yes — `viper` package is the default global instance | No — user-owned module variable is the documented pattern |
| Type on read path | `GetString()`, `GetInt()` etc. — manual cast at call site | Attribute access returns `T` as declared; IDE completion works |

**Key difference:** viper's global-instance model means two callers can see different configs if one
calls `Set()` — shared mutable state is the root of viper's known thread-safety problems. confiq's
immutable snapshot model eliminates this class of bug by design.

---

### 1.2 Source Support

| Source | viper | confiq |
|--------|-------|--------|
| Files (YAML/JSON/TOML/INI) | ✓ native; HCL and Java properties also supported | ✓ via `FileSource` + loader plugins (JSON/INI built-in; YAML/TOML as extras) |
| Environment variables | ✓ `AutomaticEnv()`, `BindEnv()`, case-insensitive | ✓ `EnvSource(prefix=, delimiter=)`, double-underscore nesting |
| CLI flags | ✓ via `BindPFlag()` bound to cobra's pflag | ✓ `CliSource` accepts pre-parsed dict from any CLI framework |
| In-memory / defaults | ✓ `SetDefault()` per key | ✓ `MemorySource(dict)` |
| Remote K/V (etcd, Consul, Firestore) | ✓ first-class, built-in | ✓ `ConsulSource` built-in; etcd not yet included |
| Cloud secrets (AWS/GCP/Azure/Vault) | ✗ not built-in; community packages | ✓ `AwsSecretsManagerSource`, `GcpSecretManagerSource`, `AzureKeyVaultSource`, `VaultSource` built-in with optional extras |
| Dotenv files | ✗ not native | ✓ via `EnvSource` with `python-dotenv` extra |
| Custom sources | ✗ no extension point; fork or wrap | ✓ `Source` protocol + `confiq.sources` entry-point group |

**confiq advantage:** Cloud secrets (Vault, AWS, GCP, Azure) are first-class. Viper has no opinion
on secrets management.

**viper advantage:** HCL and Java properties file parsing; etcd support out of the box.

---

### 1.3 Schema / Typing

| Dimension | viper | confiq |
|-----------|-------|--------|
| Schema requirement | Optional — call `Get*()` forever without a struct | Optional — schemaless mode returns `SchemalessConfig`; schema mode returns `T` |
| Schema type | Any Go struct with `mapstructure` tags | Any pydantic `BaseModel` (no confiq base class required) |
| Type on read | Manual: `v.GetString("db.host")` always returns `string` | Direct: `config.database.host` is `str`; no cast needed |
| Per-field metadata | Struct tags + separate `BindEnv()` calls | `Annotated[T, ConfigField(...)]` — env name, cli hint, source restriction, parser, secret, deprecated — all in one place |
| Validation | `Unmarshal()` via mapstructure; basic type coercion only | pydantic `model_validate()` — full Pydantic v2 validators, constraints, nested models |
| Nested structs from env | Broken — known issue since 2016 | ✓ `MYAPP_DATABASE__HOST` → `settings.database.host` via double-underscore convention |
| Unknown key warnings | ✗ silently ignored | ✓ `strict=True` (default) emits `UserWarning` for unrecognized keys |

---

### 1.4 Precedence Model

| Dimension | viper | confiq |
|-----------|-------|--------|
| Mechanism | Hard-coded 6-level hierarchy: `Set > flags > env > file > remote > defaults` | Ordered `sources` list; position is the specification |
| Customizability | Fixed; cannot reorder without monkey-patching | Fully explicit — reverse the list for first-higher semantics |
| Implicit discovery | `SetConfigName("config")` searches multiple directories | None — every source is explicitly listed |
| Multiple files | One config file only (plus override file) | Multiple `FileSource` entries, each at its own position |
| Transparency | Opaque; debug via `viper.AllSettings()` | `ResolvedSnapshot.provenance` tracks which source set each key |

---

### 1.5 Merging Semantics

| Dimension | viper | confiq |
|-----------|-------|--------|
| Strategy | Shallow merge for scalars; YAML structures merged | Deep merge, left-to-right; later sources win on collision |
| List handling | Inconsistent across versions (concatenation vs replacement) | Lists are replaced, not concatenated (ADR 0004) |
| Provenance | None | `provenance: dict[str, str]` — maps every dotted key path to the source name |

---

### 1.6 Live Reload

| Dimension | viper | confiq |
|-----------|-------|--------|
| Mechanism | `WatchConfig()` + `OnConfigChange(fn)` | `ConfigHandle[T]` + `handle.on_reload(fn)` |
| Thread safety | Not thread-safe — concurrent reads/writes require external mutex | `current()` is lock-free; `reload()` uses `threading.Lock`; `ReentrancyGuard` prevents deadlock |
| Reloaded value type | Mutable viper state; same global instance | New frozen `T`; old and new both available in subscriber |
| Subscriber signature | `fn(fsnotify.Event)` | `fn(old: T, new: T)` — typed diff |
| Reentrancy | Silently deadlocks | `ReentrancyGuard` raises `RuntimeError` with remedy message |
| Async reload | ✗ | ✓ `reload_async()` with asyncio-compatible lock |

---

### 1.7 Plugin System

| Dimension | viper | confiq |
|-----------|-------|--------|
| Native plugin system | ✗ no hookspec or extension mechanism | ✓ pluggy hookspecs: `confiq_pre_load`, `confiq_post_load`, `confiq_on_reload`, `confiq_on_error`, `confiq_load_file`, `confiq_get_schema_adapter` |
| Entry point discovery | ✗ | ✓ `pm.load_setuptools_entrypoints("confiq")` |
| Custom file format support | Fork or pre-process | `confiq_load_file` hookspec — register a loader for any suffix |
| Custom schema types | Fork | `confiq_get_schema_adapter` hookspec — attrs, msgspec, etc. |
| Internal subsystems as plugins | ✗ hard-coded loaders | ✓ YAML/TOML loaders are themselves hookimpls |

---

### 1.8 Testing

| Dimension | viper | confiq |
|-----------|-------|--------|
| Isolation | Hard — global state bleeds between tests; must `Reset()` | Hermetic — each `load()` call is independent |
| In-memory fixture | No dedicated API; write a temp file | `MemorySource({"key": "val"})` — no I/O |
| Monkeypatching needed | Often — `os.Setenv` and `viper.Reset()` in each test | Never on the primary testing path |
| Parallel test support | Risky — global state causes races | Safe — `load()` has no shared mutable state |
| Per-call plugin injection | ✗ | ✓ `load(Settings, sources=[...], plugins=[MyPlugin()])` scopes a plugin to one call |

---

### 1.9 Error Handling

| Dimension | viper | confiq |
|-----------|-------|--------|
| Error timing | Deferred — `GetString("missing")` returns zero value silently | Eager — all errors surface at `load()`; attribute access cannot raise |
| Missing required field | Returns zero value silently | `MissingConfigError` with field path and source names consulted |
| Parse failure | `ReadInConfig()` returns error; limited context | `SourceParseError` wraps original `yaml.YAMLError` etc. |
| Validation failure | Basic type coercion; no constraint checking | `ConfigValidationError` with `field_path`, `source_names`, `pydantic_errors` |
| Source restriction violation | Not a concept | `ConflictingSourceError` — always raised for `secret=True` fields |
| Error wrapping | Non-standard; no `errors.Is()` / `errors.As()` | `__cause__` set; standard Python exception chaining |

---

## Part 2: confiq's CliSource vs cobra — CLI Integration

These are not direct competitors (cobra is a full CLI framework; `CliSource` is one source in the
loading pipeline), but the comparison illuminates where confiq's CLI story sits.

| Dimension | cobra | confiq CliSource |
|-----------|-------|-----------------|
| Role | Full CLI framework — commands, subcommands, help, shell completion | One source in the config pipeline — accepts pre-parsed values from a CLI framework |
| Flag declaration | Manual: `cmd.Flags().StringP("host", "h", "", "database host")` | Not confiq's concern — declared by the CLI framework above |
| Subcommands | First-class — unlimited depth, persistent flags, lifecycle hooks | Not a concept — confiq doesn't model command routing |
| Shell completion | Auto-generated for bash, zsh, fish, PowerShell | ✗ |
| Help generation | Auto-generated from flag descriptions | ✗ — belongs to the CLI framework above confiq |
| Flag binding to config | Via `BindPFlag()` into viper — indirect, boilerplate-heavy | `CliSource(parsed_dict)` — direct, no binding wiring needed |
| Source restriction on CLI values | Not a concept | `ConfigField(sources=("env",), secret=True)` refuses CLI input |
| Integration with other sources | `BindPFlag` + `AutomaticEnv` + `SetConfigFile` — four wiring steps | `CliSource` is just another entry in `sources=[...]` |

**cobra strength:** Complete, battle-tested CLI framework with subcommands, interactive prompts, shell
completion, and man page generation.

**confiq strength:** First-class multi-source merging. The user declares the schema once; sources
are listed explicitly; no separate binding calls needed.

---

## Part 3: confiq's CliSource vs argparse / click / typer — Python CLI

### 3.1 Config Value Passing

| Dimension | argparse | click | typer | confiq CliSource |
|-----------|----------|-------|-------|-----------------|
| Flag syntax | `--name value` | `--name value` | `--name value` | Accepts pre-parsed dict; syntax is the CLI framework's concern |
| Environment variable support | Manual `os.environ` | `envvar=` per option; `auto_envvar_prefix` | `envvar=` per option | Separate `EnvSource` — orthogonal |
| Config file support | None natively | None natively | None natively | Separate `FileSource` — orthogonal |
| Nested key support | ✗ flat `Namespace` | ✗ flat dict | ✗ flat function args | ✓ nested dict maps to nested schema fields |
| Multi-source precedence | Manual | Manual | Manual | Resolver handles it; `sources` list position is the spec |
| Schema-driven flag generation | ✗ | ✗ | ✓ type hints | `ConfigField.cli` documents intended flag name for tooling |

### 3.2 Typing

| Dimension | argparse | click | typer | confiq |
|-----------|----------|-------|-------|--------|
| Type declaration | `type=int` callable | `type=click.INT` ParamType | Python type hints | Pydantic field types in schema |
| Inference from annotations | ✗ | ✗ | ✓ | ✓ resolver reads `get_type_hints()` |
| Custom validation | Post-parse manual code | `callback=` + `click.BadParameter` | `callback=` parameter | Pydantic validators + `ConfigField.parser` |
| Nested model types | ✗ | ✗ | Partial (pydantic-typer) | ✓ first-class via nested `BaseModel` fields |
| Secret / masked fields | ✗ | `click.Password` type | ✗ | `ConfigField(secret=True)` — masked in repr, redacted in hooks |
| Deprecated fields | ✗ | ✗ | ✗ | `ConfigField(deprecated="Use X instead")` — warning on load |

### 3.3 Subcommands

| Dimension | argparse | click | typer | confiq |
|-----------|----------|-------|-------|--------|
| Native support | `add_subparsers()` — awkward beyond one level | `@click.group()` — idiomatic, unlimited depth | `app.add_typer()` — clean, unlimited depth | ✗ not a CLI framework |
| Plugin discovery | No native mechanism | Entry points + dynamic `list_commands()` | Inherits Click's mechanism | ✗ out of scope |
| Shell completion | ✗ | ✓ | ✓ | ✗ |

### 3.4 Testing

| Dimension | argparse | click | typer | confiq |
|-----------|----------|-------|-------|--------|
| Test runner | None — manually construct argv | `click.testing.CliRunner` | `typer.testing.CliRunner` | `MemorySource` + `load()` — CLI layer not needed in tests |
| Env var isolation | Mock `os.environ` manually | `env=` dict to `runner.invoke()` | `env=` dict to `runner.invoke()` | `MemorySource` replaces env var setup entirely |
| Config isolation | ✗ | ✗ | ✗ | Hermetic by construction |
| Testing without CLI | Direct `parse_args()` call | Direct callback call | Direct function call | ✓ `load(Settings, sources=[MemorySource(...)])` |

### 3.5 Plugin / Extension

| Dimension | argparse | click | typer | confiq |
|-----------|----------|-------|-------|--------|
| Native plugin system | ✗ | Entry points + dynamic group loading | Inherits Click | pluggy hookspecs + entry points |
| Custom source types | N/A | N/A | N/A | `Source` protocol + `confiq.sources` entry-point group |
| Custom schema adapters | ✗ | ✗ | ✗ | `confiq_get_schema_adapter` hookspec |
| Audit / observability hooks | ✗ | ✗ | ✗ | `confiq_post_load`, `confiq_on_error` |

---

## Part 4: Summary Matrix

### Config Management (confiq vs viper)

| Axis | viper | confiq |
|------|-------|--------|
| Global state | Yes — shared mutable viper instance | No — `load()` returns a value |
| Immutability | No — `Set()` mutates globally | Yes — frozen pydantic model |
| Thread safety | Not thread-safe | Lock-free reads; non-reentrant write lock |
| Schema validation | mapstructure + manual | Pydantic v2 with full constraint support |
| Nested env vars | Broken (known issue) | ✓ via double-underscore delimiter |
| Cloud secrets | ✗ | ✓ AWS/GCP/Azure/Vault built-in |
| Plugin system | ✗ | ✓ pluggy hookspecs + entry points |
| Provenance tracking | ✗ | ✓ per-key source attribution |
| Test isolation | Requires `Reset()` + env cleanup | Hermetic by construction |
| Error boundary | At key access (silent zero value) | At `load()` — attribute access cannot raise |

### CLI Source Integration (Python CLI frameworks vs confiq CliSource)

| Axis | argparse | click | typer | confiq CliSource |
|------|----------|-------|-------|-----------------|
| Multi-source loading | ✗ | ✗ | ✗ | ✓ first-class |
| Schema-driven flags | ✗ | ✗ | ✓ type hints | `ConfigField.cli` documents intent; CLI framework generates flags |
| Nested key support | ✗ | ✗ | ✗ | ✓ nested dict |
| Env + file + CLI merging | ✗ | Manual | Manual | ✓ automatic |
| Source restriction on secrets | ✗ | ✗ | ✗ | ✓ `ConfigField(sources=("env",), secret=True)` |
| Subcommands | Awkward | ✓ | ✓ | ✗ not in scope |
| Shell completion | ✗ | ✓ | ✓ | ✗ not in scope |
| Testing without CLI | ✗ | Partial (CliRunner) | Partial (CliRunner) | ✓ MemorySource |
| Plugin discovery | ✗ | ✓ | Partial | ✓ entry points |

---

## Part 5: The Config/CLI Junction — Design Direction

### The cobra+viper separation of concerns

In the cobra+viper world the junction is explicit:

1. cobra owns flag declaration and argv parsing — produces a typed `flag.FlagSet`
2. viper owns config reading — has no opinion on how argv was parsed
3. `BindPFlag("database.host", flag)` is the bridge — names the binding explicitly

The key insight: **the CLI layer and the config layer agree on a key name; the bridge is explicit.**

### confiq's equivalent

confiq does not parse argv. The CLI framework (typer, click, argparse, or any other) owns flag
declaration and argv parsing. confiq receives pre-parsed values via `CliSource`.

```python
# confiq does not own argv parsing.
# The CLI framework parses; CliSource bridges to confiq.

# Integration with typer:
@app.command()
def main(db_host: str = "localhost", debug: bool = False):
    config = load(Settings, sources=[
        FileSource("config.yaml"),
        EnvSource("MYAPP_"),
        CliSource({"database": {"host": db_host}, "debug": debug}),
    ])

# Integration with click:
@click.command()
@click.option("--db-host", default="localhost")
@click.option("--debug", is_flag=True)
def main(db_host, debug):
    config = load(Settings, sources=[
        FileSource("config.yaml"),
        EnvSource("MYAPP_"),
        CliSource({"database": {"host": db_host}, "debug": debug}),
    ])

# Integration with argparse:
args = parser.parse_args()
config = load(Settings, sources=[
    FileSource("config.yaml"),
    EnvSource("MYAPP_"),
    CliSource({"database": {"host": args.db_host}, "debug": args.debug}),
])
```

### Why `CliSource` rather than `MemorySource(d, name="cli")`

`MemorySource` accepts `name="cli"` — the workaround exists today. But:

- **Discoverability:** users look for `CliSource` when wiring CLI integration, not `MemorySource`
- **Semantic clarity:** `MemorySource` reads as "test fixture / in-process defaults"; `CliSource`
  reads as "values from the CLI layer"
- **Source restriction correctness:** `ConfigField(sources=("env",), secret=True)` matches on
  `source.name == "cli"` — using `MemorySource` without `name="cli"` silently bypasses the
  restriction

### What `ConfigField.cli` means

`ConfigField(cli="--db-host")` no longer informs a confiq-owned parser (there is none). Instead it
serves as **documentation and a hook for future tooling**.

A post-v1 `confiq-typer` (or `confiq-click`) integration package could read `ConfigField.cli`
annotations from the schema and auto-generate typer parameters, routing results through `CliSource`.
This is the full cobra+viper analogy:

- cobra: manually declared flags → `BindPFlag` bridges to viper
- `confiq-typer`: `ConfigField.cli` annotations → auto-generated typer options → `CliSource` bridges
  to confiq

For v1: `ConfigField.cli` is preserved but has no runtime effect on `CliSource`.

---

## Part 6: Notable Gaps in confiq Relative to These Tools

1. **No command routing.** Subcommands belong to the CLI framework above confiq. The integration
   story (how to wire confiq into typer/click) needs documentation.

2. **No shell completion.** cobra and click/typer auto-generate completion scripts. Since confiq
   doesn't model commands, this is out of scope — but a `confiq-typer` package that generates
   completions from a pydantic schema would be valuable post-v1.

3. **No HCL or Java properties support.** Viper supports these. confiq's loader plugin system
   could accommodate them, but no built-in loaders exist yet.

4. **No etcd support.** Viper's remote config includes etcd. confiq has Consul but not etcd.

5. **No `confiq_override` pytest fixture yet.** Documented as a post-v1 `pytest-confiq` package.

6. **No interactive prompts.** click's `click.prompt()` and `click.confirm()` have no confiq
   equivalent. Correct — confiq is config loading, not interactive UX.

7. **Async `on_reload` callbacks deferred to v1.1.** Viper's `OnConfigChange` accepts any callback;
   confiq v1 restricts to sync. Workaround: `loop.call_soon_threadsafe(...)` inside a sync
   subscriber.