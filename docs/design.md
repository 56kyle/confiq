# `confiq` — A Thread-Safe, Pluggable Configuration Manager for Python

> Audience: a technically sophisticated Python author who wants depth, opinions, and runnable-looking skeletons.

## TL;DR

- **Build it as "loguru for config + fsspec for sources + pluggy for hooks."** (See `docs/decisions/0002-pluggy-as-plugin-framework.md` and `0003-dual-extension-surfaces.md`.) Expose a single pre-configured `config` object (loguru's `from loguru import logger` ergonomics), keep a pluggable source registry driven by `known_implementations` + `entry_points` (verbatim fsspec pattern) for _instantiable_ sources, and use **pluggy** — the framework that powers pytest, tox, and devpi — for _stateless hooks_: lifecycle events (`before_load`, `after_merge`, `before_publish`, `on_reload`), file-format dispatch, and schema-adapter selection. Make `pydantic` and `pluggy` the only hard dependencies; put YAML/TOML/click/typer/watchdog/AWS/GCP/Azure/Vault/Consul/etcd behind extras that fail-fast with an actionable message when missing — the same `{"class": "...", "err": "..."}` shape fsspec's `known_implementations` uses.
- **Pick the immutable-snapshot + atomic-reference-swap mutability model**, not an RWLock. (See `docs/decisions/0001-lock-free-reads-via-immutable-snapshots.md`.) Reads (`config.get(...)`) become entirely lock-free: a single attribute load of a frozen `ConfigSnapshot[T]`. Writes (`bind`, `add_source`, `reload`, `patch`) take a short non-reentrant `threading.Lock`, build the new snapshot under the lock, and publish via a single `STORE_ATTR`. Subscribers run on a daemon thread _outside_ the lock, dispatched through pluggy's `on_reload` hook, and a loguru-style reentrancy guard (modeled on loguru's `_protected_lock` from `loguru/_handler.py`) makes deadlocks loud rather than hung.
- **Use pydantic v2 as the schema spine and `contextvars` for async-safe overrides.** `Config[T]` is `Generic[T]` so `config.get()` returns a typed `Settings` instance with full IDE autocomplete; precedence is the same `CLI > env > file > defaults` chain pydantic-settings uses, exposed as a re-orderable list. Per-task overrides go through `contextvars.ContextVar` (not `threading.local`) so they survive `await` and behave correctly under asyncio per PEP 567.

## Key Findings

1. **Loguru's secret is one object + many handlers, and its critical defensive idiom is a reentrancy-fail-fast lock**, not a clever RWLock. The handler module raises `"Could not acquire internal lock because it was already in use (deadlock avoided). This likely happened because the logger was re-used inside a sink, a signal handler or a '__del__' method."` (verbatim from `github.com/Delgan/loguru/blob/master/loguru/_handler.py`). The documented multiprocessing deadlock report — Issue #231, _"Bug - Deadlock when using multithreaded & multiprocessing Environment"_ opened by @shachakz on Mar 30, 2020 against loguru 0.4.1 — is the cautionary tale our design must avoid.

2. **fsspec's registry pattern is the right one for source instances.** `_registry: dict[str, type] = {}` is wrapped in `types.MappingProxyType(_registry)` for the public view; `known_implementations` maps protocol → `{"class": "pkg.mod.Class", "err": "Install ..."}`. Third parties register classes via `entry_points={"fsspec.specs": ["myfs=myfs.MyFS"]}`. We adopt this verbatim under the `confiq.sources` entry-point group — but only for sources, because sources are _configured instances_. For stateless multi-participant hooks (lifecycle, format dispatch, adapter selection), pluggy is the better tool.

3. **Pluggy is the de-facto Python plugin framework.** It powers pytest, tox, and devpi; it has zero transitive dependencies; its semantics (hookspec/hookimpl, first-result, all-results, `tryfirst`/`trylast`, `hookwrapper`) cover every hook pattern this package needs. It also handles entry-point discovery, plugin blocking, and introspection (`pm.list_name_plugin()`) out of the box. Using it for hooks is strictly better than rolling our own callback list — and it gives `confiq` a familiar surface for any developer who has written a pytest plugin.

4. **pydantic-settings' precedence model is the closest existing prior art**, and we should not re-invent it: per the pydantic-settings docs (`docs.pydantic.dev/2.0/usage/pydantic_settings/`), `settings_customise_sources` _"takes four callables as arguments and returns any number of callables as a tuple. ... The order of the returned callables decides the priority of inputs; first item is the highest priority."_ We generalize this to an ordered, re-sortable list of `ConfigSource` instances. Issue #351 (_"`AliasChoices` order overrides `settings_customise_sources` priority"_) is a useful warning that precedence interactions with field aliases can surprise users — we sidestep this by keeping merge purely structural.

5. **OmegaConf is explicitly "not thread-safe"** per maintainer @omry in `omry/omegaconf` Discussion #1116. That is decisive: do not borrow its lazy-interpolation model. Dynaconf's `environments=True` is a known footgun (Discussion #956). Neither should be emulated.

6. **For async, `contextvars` is mandatory, not optional.** The stdlib docs warn outright: _"Context managers that have state should use Context Variables instead of threading.local() to prevent their state from bleeding to other code unexpectedly, when used in concurrent code."_ (`docs.python.org/3/library/contextvars.html`). PEP 567 guarantees `ContextVar` is inherited by `asyncio.Task` at creation. Per-task config overrides therefore use `ContextVar`, period.

7. **A real RW lock is overkill for the read path.** Éric Larivière's README for `elarivie/pyReaderWriterLock` (`github.com/elarivie/pyReaderWriterLock/blob/master/README.md`) notes that _"Downgradable classes come with a theoretical ~20% negative effect on performance for acquiring and releasing locks."_ For a hot path that just reads a single attribute, even an uncontended RLock acquisition is wasted work. The atomic-reference-swap on a frozen snapshot gets you the same guarantees for free.

## Details

### 1. Design philosophy & guiding principles

The brief asks for "loguru for config." That framing is a hard constraint that drives every architectural choice. The North Stars:

1. **One blessed object, many handlers — like loguru.** loguru exposes a single pre-configured `logger`; all sinks are added/removed against it. The loguru source confirms this: `_logger.py` instantiates one `Core` at import time; the docs state _"There is only one logger, so there is no need to retrieve one before usage."_ We mirror this with one importable `config: Config` (`from confiq import config`).

2. **A pluggable registry of source classes — like fsspec.** fsspec maintains `known_implementations` mapping a `protocol` string to a `package.module.Class` _plus_ an `err` string explaining how to install the missing optional dependency. Discovery is by `entry_points` (group `fsspec.specs`); the registry itself is `types.MappingProxyType(_registry)` — publicly immutable, internally mutable. We copy this for config sources.

3. **A pluggy-based hook system for stateless extension points — like pytest.** Where fsspec's "register a class" pattern shines for sources (each is an _instance_ with state), it's awkward for things like "which loader handles `.yaml`?" or "transform the merged dict before validation." These are exactly pluggy's wheelhouse. `confiq` defines hookspecs for `load_file`, `get_schema_adapter`, `before_load`, `after_merge`, `before_publish`, and `on_reload`. Third parties register hookimpls via the `confiq` entry-point group and get pytest-grade plugin ergonomics for free.

4. **Type-first, pydantic-native.** Configuration without a schema is a footgun. We treat a user-supplied schema (`pydantic.BaseModel`, optionally `@dataclass` or `TypedDict`) as the source of truth. `Config` is generic in that schema; `Config[Settings]` gives full IDE autocomplete.

5. **Thread safety by default; deadlock avoidance as a design discipline.** loguru's `_handler.py` ships a `_protected_lock` that fast-fails with `RuntimeError("Could not acquire internal lock because it was already in use (deadlock avoided)")` if a thread re-enters the same lock. We adopt the same posture and choose immutable snapshot + atomic reference swap so the _hot path_ of `config.get()` is lock-free.

6. **Precedence is a contract.** `CLI > env > file > defaults` is the precedence used by pydantic-settings and twelve-factor tools. Deterministic, ordered list of sources merged by deep-update — same shape as pydantic-settings' `settings_customise_sources`, generalized.

7. **Zero-config defaults; full configurability when needed.** `from confiq import config; print(config.get("database.host"))` works with sensible auto-discovery, and is also drivable by an explicit fluent builder.

8. **Optional dependencies as features.** Base is stdlib-only except for `pydantic` and `pluggy`. YAML, TOML on 3.10−, click, typer, watchdog, boto3, hvac, etc. are behind extras. Missing extras fail with a clear `MissingDependencyError`, mirroring fsspec's `err` field.

**What we explicitly are not doing:**

- No YAML interpolation DSL (`${...}`) à la OmegaConf. OmegaConf is "not thread-safe" per maintainer @omry, and interpolation introduces stateful, order-dependent evaluation that fights an immutable-snapshot design.
- No implicit environment switching (Dynaconf `[development] / [production]`). Multi-env is achievable by composing multiple `FileSource` instances in a precedence chain.
- No `dict` subclassing. Public surface is `config.get("a.b.c")` and `config.snapshot()`, returning typed models or plain values — never a mutable proxy.

### 2. High-level architecture

```
confiq/
├── __init__.py              # exposes the singleton `config`, key types, hookimpl
├── _core.py                 # Config[T], ConfigManager
├── _snapshot.py             # ConfigSnapshot[T] (immutable view)
├── _merge.py                # deep_merge, _freeze
├── _registry.py             # source class registry (fsspec-style)
├── _hookspecs.py            # pluggy hook specifications
├── _plugins.py              # plugin manager + built-in hookimpls
├── _locks.py                # ReentrancyGuard
├── _watch.py                # optional: file-watching reload
├── sources/
│   ├── base.py              # ConfigSource protocol + AbstractConfigSource + priority constants
│   ├── _coerce.py           # _parse_env_value, _set_path — shared by env + argparse sources
│   ├── defaults.py          # DefaultsSource (from schema)
│   ├── dict_source.py       # DictSource — inline dict layer; canonical test primitive
│   ├── file.py              # FileSource (dispatches via pluggy load_file hook)
│   ├── env.py               # EnvSource (os.environ + .env)
│   ├── argparse_source.py   # ArgparseSource (no extra deps)
│   ├── click_source.py      # [click] extra
│   ├── typer_source.py      # [typer] extra
│   ├── aws_ssm.py / aws_secrets.py / aws_s3.py    # [aws] extra
│   ├── gcp_secrets.py       # [gcp] extra
│   ├── azure_keyvault.py    # [azure] extra
│   ├── vault.py             # [vault] extra
│   ├── consul.py            # [consul]
├── loaders/                 # pluggy hookimpls for each file format
│   ├── json_loader.py       # built-in
│   ├── yaml_loader.py       # [yaml]
│   ├── toml_loader.py       # [toml]
│   └── ini_loader.py        # built-in
├── schema/
│   ├── pydantic_adapter.py
│   ├── dataclass_adapter.py
│   └── typeddict_adapter.py
└── cli/
    └── flatten.py
```

**Data flow:**

```
 ┌──────────────────────────────────────────────────────────┐
 │ Ordered list of ConfigSource instances (priority asc)    │
 │ [DefaultsSource, FileSource, EnvSource, CLISource]       │
 └────────────────────────┬─────────────────────────────────┘
                          │  pm.hook.before_load(source=s)
                          │  s.load() → dict
                          ▼
                ┌──────────────────┐
                │   deep_merge()   │  ← last-wins, deep
                └────────┬─────────┘
                         │  pm.hook.confiq_after_merge(merged=d)
                         ▼
              ┌──────────────────────────┐
              │ Schema.model_validate()  │  (via pluggy adapter hook)
              └────────┬─────────────────┘
                         │  pm.hook.before_publish(old, new)
                         ▼
            ┌─────────────────────────────┐
            │ ConfigSnapshot[T] (frozen)  │  ← what readers get
            └────────┬────────────────────┘
                     ▼
         atomic store on Config._current
                     │
       ┌─────────────┴────────────┐
       ▼                          ▼
  config.get(...)         pm.hook.on_reload(old, new)
  (lock-free)             (daemon thread, outside lock)
```

The crucial property: **`config.get()` never takes a lock, and pluggy is never on the read path.** Pluggy is only invoked during the (rare) write path — reload, source registration, schema binding. Reads are still a single `LOAD_ATTR`.

### 3. Public API — from hello world to full power

**3.1 Five-second hello world**

```python
from confiq import config
# Auto-discovers ./config.{yaml,toml,json}, .env, then os.environ.
print(config.get("database.host", default="localhost"))
print(config.get("debug", cast=bool, default=False))
```

**3.2 With a pydantic schema (recommended)**

```python
from pydantic import BaseModel, Field
class Database(BaseModel):
    host: str = "localhost"
    port: int = Field(5432, ge=1, le=65535)
    password: str | None = None

class Settings(BaseModel):
    debug: bool = False
    database: Database = Database()
    allowed_hosts: list[str] = []
```

```python
from confiq import config
from settings import Settings

config.bind(Settings)
config.add_file("config.yaml")
config.add_env(prefix="MYAPP_")             # MYAPP_DATABASE__HOST → database.host
config.add_argparse()

s = config.get()                            # Settings instance, fully typed
print(s.database.host)                      # IDE autocomplete works
```

**3.3 Fluent builder, loguru-style**

```python
from confiq import config
config\
    .bind(Settings)\
    .add_defaults_from_schema()\
    .add_file("/etc/myapp/config.yaml", required=False)\
    .add_file("./config.yaml", required=False)\
    .add_env(prefix="MYAPP_")\
    .add_argparse()\
    .freeze()
```

**3.4 Click / Typer integration**

```python
# pip install confiq[click]
import click
from confiq import config

@click.command()
@click.option("--database-host")
@click.option("--debug/--no-debug", default=None)
def main(**kwargs):
    config.add_click(kwargs)
    run_app(config.get())
```

```python
# pip install confiq[typer]
import typer
from confiq import config
app = typer.Typer()

@app.command()
def serve(database_host: str = None, debug: bool = False):
    config.add_typer(locals())
    run_app(config.get())
```

**3.5 Live reload with subscribers (pluggy hook under the hood)**

```python
# pip install confiq[watch]
config.bind(Settings).add_file("config.yaml", watch=True)

@config.on_reload
def db_pool_resizer(old: Settings, new: Settings):
    if old.database != new.database:
        pool.reconfigure(new.database)
```

`@config.on_reload` is a thin convenience that registers a hookimpl for the `on_reload` hookspec. Anyone who wants the full pluggy power can register a class-based plugin via entry points instead.

**3.6 Cloud sources**

```python
config.add_aws_secrets_manager(secret_id="prod/myapp", region="us-west-2")
config.add_aws_ssm(path="/myapp/prod/", recursive=True)
config.add_vault(addr="https://vault.example.com", path="secret/data/myapp")
config.add_gcp_secret_manager(project_id="my-project")
```

**3.7 Async-safe per-task overrides (contextvars)**

```python
import asyncio
from confiq import config

async def handler(request):
    with config.override(database={"host": request.tenant_db_host}):
        await do_work()
```

`override` uses `contextvars.ContextVar`. Per the stdlib docs (`docs.python.org/3/library/contextvars.html`): _"Context managers that have state should use Context Variables instead of threading.local() to prevent their state from bleeding to other code unexpectedly, when used in concurrent code."_

**3.8 A third-party plugin (pluggy-style)**

```python
# my_redacting_plugin.py
from confiq import hookimpl

class RedactSecrets:
    @hookimpl
    def confiq_after_merge(self, merged: dict) -> dict:
        return _walk_and_redact(merged)

    @hookimpl
    def confiq_on_reload(self, old_model, new_model) -> None:
        metrics.increment("config.reload")
```

```toml
# my_redacting_plugin/pyproject.toml
[project.entry-points.confiq]
redact-secrets = "my_redacting_plugin:RedactSecrets"
```

`pip install my-redacting-plugin` is the entire user-facing install step. The pluggy plugin manager auto-discovers it on `confiq` import.

**3.9 Layered and split-file configuration**

Sources at equal priority are merged in the order they are added (Python's `sort` is stable). To make one file override another on shared keys, assign it a higher numeric priority.

_Environment-based layering (base → env-specific → local):_

```python
import os
from confiq import config
from confiq.sources.base import PRIORITY_FILE

env = os.getenv("ENV", "development")

config\
    .bind(Settings)\
    .add_file("config/base.yaml")\
    .add_file(f"config/{env}.yaml",  required=False, priority=PRIORITY_FILE + 1)\
    .add_file("config/local.yaml",   required=False, priority=PRIORITY_FILE + 2)\
    .add_env(prefix="MYAPP_")\
    .freeze()
```

`config/production.yaml` values shadow `config/base.yaml` on any shared key; `config/local.yaml` shadows both.

_Domain split (app + database + cache, all additive at equal priority):_

```python
config\
    .bind(Settings)\
    .add_file("config/app.yaml")\
    .add_file("config/database.yaml")\
    .add_file("config/cache.yaml")\
    .add_env(prefix="MYAPP_")\
    .freeze()
```

All three files deep-merge into a single dict. A key that appears in both `app.yaml` and `database.yaml` resolves in favour of `database.yaml` (added last among equals).

_`DictSource` for testing and programmatic injection:_

```python
from confiq import Config
from confiq.sources.base import PRIORITY_FILE
from settings import Settings

def build_config(overrides: dict | None = None) -> Config:
    cfg = Config()
    cfg.bind(Settings)
    cfg.add_file("config/base.yaml")
    if overrides:
        cfg.add_dict(overrides, priority=PRIORITY_FILE + 1)
    return cfg

# In a test:
cfg = build_config({"database": {"host": "localhost", "port": 5433}})
assert cfg.get().database.host == "localhost"
```

`DictSource` wraps a plain `dict` as a config layer. Its priority is fully controllable, making it the canonical primitive for test fixtures and for bridging values from another config system (e.g., a resolved Hydra `DictConfig`).

### 4. Core abstractions — code skeletons

**4.1 The Source protocol (fsspec-style; for instances)**

```python
# confiq/sources/base.py
from __future__ import annotations
from typing import Protocol, Any, runtime_checkable, ClassVar
from abc import ABC, abstractmethod

JSONDict = dict[str, Any]

PRIORITY_DEFAULTS: int = 0
PRIORITY_FILE: int = 10
PRIORITY_CLOUD: int = 15
PRIORITY_ENV: int = 20
PRIORITY_CLI: int = 30


@runtime_checkable
class ConfigSource(Protocol):
    """Anything that can produce a dict of config values."""
    protocol: ClassVar[str]
    priority: int

    def load(self) -> JSONDict: ...
    def supports_watch(self) -> bool: ...
    def watch(self, on_change: Any) -> "Stopper | None": ...


class AbstractConfigSource(ABC):
    """Reference implementation, analogous to fsspec.AbstractFileSystem."""
    protocol: ClassVar[str] = "abstract"
    priority: int = PRIORITY_FILE

    def __init__(self, *, priority: int | None = None) -> None:
        if priority is not None:
            self.priority = priority

    @abstractmethod
    def load(self) -> JSONDict: raise NotImplementedError

    def supports_watch(self) -> bool: return False
    def watch(self, on_change: Any) -> None: return None
```

**4.2 Source class registry (verbatim fsspec pattern)**

```python
# confiq/_registry.py
import importlib, types, warnings
from importlib.metadata import entry_points
from typing import Any

_registry: dict[str, type] = {}
registry = types.MappingProxyType(_registry)  # public, read-only view

known_implementations: dict[str, dict[str, str]] = {
    "file":     {"class": "confiq.sources.file.FileSource"},
    "env":      {"class": "confiq.sources.env.EnvSource"},
    "argparse": {"class": "confiq.sources.argparse_source.ArgparseSource"},
    "dict":     {"class": "confiq.sources.dict_source.DictSource"},
    "click":    {"class": "confiq.sources.click_source.ClickSource",
                 "err":   "Install confiq[click] to use Click integration."},
    "typer":    {"class": "confiq.sources.typer_source.TyperSource",
                 "err":   "Install confiq[typer] to use Typer integration."},
    "aws-ssm":  {"class": "confiq.sources.aws_ssm.AwsSsmSource",
                 "err":   "Install confiq[aws] to use AWS SSM."},
    "aws-secrets": {"class": "confiq.sources.aws_secrets.AwsSecretsManagerSource",
                    "err":   "Install confiq[aws] to use AWS Secrets Manager."},
    "gcp-secrets": {"class": "confiq.sources.gcp_secrets.GcpSecretManagerSource",
                    "err":   "Install confiq[gcp]."},
    "azure-kv": {"class": "confiq.sources.azure_keyvault.AzureKeyVaultSource",
                 "err":   "Install confiq[azure]."},
    "vault":    {"class": "confiq.sources.vault.VaultSource",
                 "err":   "Install confiq[vault]  (uses hvac)."},
    "consul":   {"class": "confiq.sources.consul.ConsulSource",
                 "err":   "Install confiq[consul]."},
}


class MissingDependencyError(ImportError): ...


def register_implementation(name, cls, *, clobber=False, errtxt=None):
    if name in _registry and not clobber:
        if _registry[name] is not cls:
            raise ValueError(f"{name!r} already registered")
        return
    if isinstance(cls, str):
        known_implementations[name] = {"class": cls,
                                       **({"err": errtxt} if errtxt else {})}
    else:
        _registry[name] = cls


def get_source_class(protocol: str) -> type:
    if protocol in _registry:
        return _registry[protocol]
    if protocol in known_implementations:
        spec = known_implementations[protocol]
        try:
            mod_path, _, cls_name = spec["class"].rpartition(".")
            cls = getattr(importlib.import_module(mod_path), cls_name)
        except ImportError as e:
            raise MissingDependencyError(spec.get("err") or str(e)) from e
        _registry[protocol] = cls
        return cls
    raise KeyError(f"Unknown config source protocol: {protocol!r}")


def _discover_entry_points() -> None:
    """Auto-register third-party source classes (group `confiq.sources`)."""
    try:
        eps = entry_points(group="confiq.sources")
    except TypeError:
        eps = entry_points().get("confiq.sources", [])
    for ep in eps:
        try:
            register_implementation(ep.name, f"{ep.module}.{ep.attr}")
        except Exception as e:
            warnings.warn(f"Failed to register source {ep.name!r}: {e}")


_discover_entry_points()


def create_source(protocol: str, **opts: Any) -> Any:
    """Top-level factory, mirrors fsspec.filesystem(protocol, **opts)."""
    return get_source_class(protocol)(**opts)
```

**4.3 Pluggy hookspecs**

```python
# confiq/_hookspecs.py
from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING
import pluggy

hookspec = pluggy.HookspecMarker("confiq")
hookimpl = pluggy.HookimplMarker("confiq")

if TYPE_CHECKING:
    from .sources.base import ConfigSource
    from ._snapshot import ConfigSnapshot


class ConfiqSpecs:
    """The hook contract third parties (and built-ins) implement."""

    @hookspec(firstresult=True)
    def confiq_load_file(self, path: Path, suffix: str) -> dict | None:
        """Load a file; return its contents as a dict, or None for unhandled suffixes."""

    @hookspec(firstresult=True)
    def confiq_get_schema_adapter(self, schema: type) -> Any | None:
        """Return a SchemaAdapter for this schema type, or None if unrecognised."""

    @hookspec
    def confiq_before_load(self, source: "ConfigSource") -> None:
        """Called before each source's load() during a reload."""

    @hookspec(firstresult=True)
    def confiq_after_merge(self, merged: dict) -> dict | None:
        """Called once with the fully-merged dict before schema validation.

        Return a transformed dict to replace the merged value, or None to pass.
        The highest-priority registered impl wins (firstresult). Register with
        tryfirst=True to take priority over other plugins. See ADR 0003."""

    @hookspec
    def confiq_before_publish(self,
                              old_snapshot: "ConfigSnapshot",
                              new_snapshot: "ConfigSnapshot") -> None:
        """Called under the write lock just before the atomic swap; raise to abort."""

    @hookspec
    def confiq_on_reload(self, old_model: Any, new_model: Any) -> None:
        """Called on the daemon notification thread after a successful publish."""
```

**4.4 Plugin manager and built-in hookimpls**

```python
# confiq/_plugins.py
from __future__ import annotations
from pathlib import Path
import pluggy
from ._hookspecs import ConfiqSpecs, hookimpl


def _make_plugin_manager() -> pluggy.PluginManager:
    pm = pluggy.PluginManager("confiq")
    pm.add_hookspecs(ConfiqSpecs)
    pm.register(_BuiltinLoaders(), name="confiq.builtin.loaders")
    pm.register(_BuiltinAdapters(), name="confiq.builtin.adapters")
    pm.load_setuptools_entrypoints("confiq")
    return pm


class _BuiltinLoaders:
    @hookimpl
    def confiq_load_file(self, path: Path, suffix: str) -> dict | None:
        if suffix == ".json":
            import json
            return json.loads(path.read_text(encoding="utf-8"))
        if suffix == ".ini":
            import configparser
            cp = configparser.ConfigParser()
            cp.read(path, encoding="utf-8")
            return {s: dict(cp.items(s)) for s in cp.sections()}
        return None


def _is_typeddict(tp: object) -> bool:
    return (
        isinstance(tp, type)
        and hasattr(tp, "__required_keys__")
        and hasattr(tp, "__optional_keys__")
    )


class _BuiltinAdapters:
    @hookimpl
    def confiq_get_schema_adapter(self, schema: type):
        from pydantic import BaseModel
        from dataclasses import is_dataclass
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            from .schema.pydantic_adapter import PydanticAdapter
            return PydanticAdapter(schema)
        if is_dataclass(schema):
            from .schema.dataclass_adapter import DataclassAdapter
            return DataclassAdapter(schema)
        if _is_typeddict(schema):
            from .schema.typeddict_adapter import TypedDictAdapter
            return TypedDictAdapter(schema)
        return None


def _register_optional_loaders(pm: pluggy.PluginManager) -> None:
    try:
        from .loaders import yaml_loader
        pm.register(yaml_loader, name="confiq.builtin.yaml")
    except ImportError:
        pass
    try:
        from .loaders import toml_loader
        pm.register(toml_loader, name="confiq.builtin.toml")
    except ImportError:
        pass
```

```python
# confiq/loaders/yaml_loader.py    (requires extra: confiq[yaml])
from pathlib import Path
from confiq import hookimpl
import yaml   # raises ImportError if [yaml] not installed → silently skipped


@hookimpl
def confiq_load_file(path: Path, suffix: str) -> dict | None:
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return None


# confiq/loaders/toml_loader.py    (requires extra: confiq[toml] or Python 3.11+)
from pathlib import Path
from confiq import hookimpl
try:
    import tomllib
except ImportError:
    import tomli as tomllib   # type: ignore


@hookimpl
def confiq_load_file(path: Path, suffix: str) -> dict | None:
    if suffix == ".toml":
        return tomllib.loads(path.read_text(encoding="utf-8"))
    return None
```

**4.5 `Config[T]` manager and snapshot**

```python
# confiq/_snapshot.py
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ConfigSnapshot(Generic[T]):
    model: T | None
    raw: MappingProxyType
    version: int
    sources: tuple[str, ...]

    def get(self, dotted: str, default: Any = ..., *, cast=None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if isinstance(node, (dict, MappingProxyType)) and part in node:
                node = node[part]
            else:
                if default is ...: raise KeyError(dotted)
                return default
        return cast(node) if cast is not None else node
```

```python
# confiq/_core.py
import threading, contextvars, copy
from types import MappingProxyType
from typing import Generic, TypeVar, Callable, Any
from contextlib import contextmanager
from ._snapshot import ConfigSnapshot
from ._merge import deep_merge, _freeze
from ._locks import ReentrancyGuard
from ._plugins import _make_plugin_manager, _register_optional_loaders

T = TypeVar("T")


class Config(Generic[T]):
    """The one Config to rule them all. Import as `from confiq import config`."""

    def __init__(self) -> None:
        self._sources: list[Any] = []
        self._schema: type[T] | None = None
        self._adapter = None
        self._lock = threading.Lock()
        self._reentry = ReentrancyGuard()
        self._current: ConfigSnapshot[T] = ConfigSnapshot(
            None, MappingProxyType({}), 0, ()
        )
        self._pm = _make_plugin_manager()
        _register_optional_loaders(self._pm)
        self._frozen = False
        # Per-instance ContextVar so multiple Config() objects (e.g. in tests)
        # don't share override state. See ADR 0001.
        self._override_var: contextvars.ContextVar[dict[str, Any] | None] = (
            contextvars.ContextVar(f"confiq_override_{id(self)}", default=None)
        )

    # ─── public read API (LOCK-FREE) ─────────────────────────────────────

    def get(self, dotted: str | None = None, default: Any = ..., *, cast=None) -> Any:
        snap = self._current
        override = self._override_var.get()
        if override is not None and dotted:
            try:
                node: Any = override
                for part in dotted.split("."):
                    node = node[part]
                return cast(node) if cast else node
            except (KeyError, TypeError):
                pass
        if dotted is None:
            return snap.model
        return snap.get(dotted, default, cast=cast)

    def snapshot(self) -> ConfigSnapshot[T]:
        return self._current

    # ─── fluent registration API ─────────────────────────────────────────

    def bind(self, schema: type[T]) -> "Config[T]":
        with self._lock, self._reentry:
            self._assert_unfrozen()
            self._schema = schema
            self._adapter = self._pm.hook.confiq_get_schema_adapter(schema=schema)
            if self._adapter is None:
                raise TypeError(f"No registered adapter handles {schema!r}")
            self._rebuild_locked()
        return self

    def add_source(self, src: Any) -> "Config[T]":
        with self._lock, self._reentry:
            self._assert_unfrozen()
            self._sources.append(src)
            self._sources.sort(key=lambda s: s.priority)
            self._rebuild_locked()
            self._maybe_attach_watch(src)
        return self

    def reprioritize_sources(self, key: Callable[[Any], Any]) -> "Config[T]":
        """Re-sort sources with a custom key and rebuild the snapshot."""
        with self._lock, self._reentry:
            self._assert_unfrozen()
            self._sources.sort(key=key)
            self._rebuild_locked()
        return self

    def add_file(self, path: Any, *, required: bool = True, watch: bool = False,
                 file_format: str | None = None,
                 priority: int | None = None) -> "Config[T]":
        from .sources.file import FileSource
        return self.add_source(FileSource(path, required=required, watch=watch,
                                          file_format=file_format, priority=priority,
                                          plugin_manager=self._pm))

    def add_dict(self, data: dict[str, Any], *,
                 priority: int | None = None) -> "Config[T]":
        from .sources.dict_source import DictSource
        return self.add_source(DictSource(data, priority=priority))

    def add_env(self, *, prefix: str = "", delimiter: str = "__",
                dotenv: Any = None, priority: int | None = None) -> "Config[T]":
        from .sources.env import EnvSource
        return self.add_source(EnvSource(prefix=prefix, delimiter=delimiter,
                                         dotenv=dotenv, priority=priority))

    def add_argparse(self, namespace: Any = None, *, argv: list[str] | None = None,
                     priority: int | None = None) -> "Config[T]":
        from .sources.argparse_source import ArgparseSource
        return self.add_source(ArgparseSource(namespace=namespace, argv=argv,
                                              priority=priority))

    # ─── plugin / subscriber API ─────────────────────────────────────────

    def register_plugin(self, plugin: Any, name: str | None = None) -> None:
        self._pm.register(plugin, name=name)

    def unregister_plugin(self, plugin_or_name: Any) -> None:
        self._pm.unregister(plugin_or_name)

    def on_reload(self, fn: Callable) -> Callable:
        """Decorator: register a free function as an on_reload hookimpl."""
        from ._hookspecs import hookimpl
        class _Adapter:
            @hookimpl
            def confiq_on_reload(self, old_model: Any, new_model: Any) -> None:
                fn(old_model, new_model)
        self._pm.register(_Adapter(), name=f"on_reload:{fn.__qualname__}")
        return fn

    def reload(self) -> ConfigSnapshot[T]:
        with self._lock, self._reentry:
            return self._rebuild_locked()

    @contextmanager
    def override(self, **patches: Any):
        """contextvars-based per-task override; safe for asyncio and threads."""
        prev = self._override_var.get()
        new = deep_merge(copy.deepcopy(prev) if prev else {}, patches)
        token = self._override_var.set(new)
        try:
            yield self
        finally:
            self._override_var.reset(token)

    def freeze(self) -> "Config[T]":
        """Permanently prevent further source registration or schema binding.

        One-way by design: users who need a mutable instance (e.g. in tests)
        should construct a fresh Config(). See ADR 0001.
        """
        self._frozen = True
        return self

    # ─── internals (lock is held) ────────────────────────────────────────

    def _rebuild_locked(self) -> ConfigSnapshot[T]:
        old = self._current
        merged: dict[str, Any] = {}
        sources_used: list[str] = []
        for src in self._sources:
            self._pm.hook.confiq_before_load(source=src)
            merged = deep_merge(merged, src.load())
            sources_used.append(src.protocol)

        transformed = self._pm.hook.confiq_after_merge(merged=merged)
        if transformed is not None:
            merged = transformed

        model = self._adapter.validate(merged) if self._adapter else None
        new_snap = ConfigSnapshot(
            model=model,
            raw=MappingProxyType(_freeze(merged)),
            version=old.version + 1,
            sources=tuple(sources_used),
        )

        self._pm.hook.confiq_before_publish(old_snapshot=old, new_snapshot=new_snap)
        self._current = new_snap
        self._enqueue_notify(old.model, new_snap.model)
        return new_snap

    def _enqueue_notify(self, old_model: Any, new_model: Any) -> None:
        def _run() -> None:
            try:
                self._pm.hook.confiq_on_reload(old_model=old_model, new_model=new_model)
            except Exception:
                import traceback; traceback.print_exc()
        threading.Thread(target=_run, daemon=True, name="confiq-notify").start()
```

**4.6 Reentrancy guard (modeled on loguru's `_protected_lock`)**

```python
# confiq/_locks.py
# ReentrancyGuard is modeled on loguru's _protected_lock (loguru/_handler.py).
# See ADR 0001 for the reasoning behind non-reentrant write locking.
import threading


class ReentrancyGuard:
    """Per-thread fast-fail: raise on re-entry rather than deadlock."""

    def __init__(self) -> None:
        self._local = threading.local()

    def __enter__(self) -> "ReentrancyGuard":
        if getattr(self._local, "in_use", False):
            raise RuntimeError(
                "confiq: re-entered the config write lock from the same thread "
                "(deadlock avoided). A hookimpl or subscriber tried to mutate "
                "config synchronously. Move that work off the notification thread."
            )
        self._local.in_use = True
        return self

    def __exit__(self, *exc: object) -> bool:
        self._local.in_use = False
        return False
```

**4.7 Merge engine**

```python
# confiq/_merge.py
from types import MappingProxyType
_MAP = (dict, MappingProxyType)


def deep_merge(base: dict, overlay: dict) -> dict:
    """Right-wins deep merge. Lists are REPLACED, not concatenated.
    Mirrors pydantic's `deep_update` semantics."""
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], _MAP) and isinstance(v, _MAP):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _freeze(d):
    """Deeply-frozen view: dicts → MappingProxyType, lists → tuples."""
    if isinstance(d, dict):
        return MappingProxyType({k: _freeze(v) for k, v in d.items()})
    if isinstance(d, list):
        return tuple(_freeze(x) for x in d)
    return d
```

**4.8 Schema adapters (pydantic / dataclass / TypedDict)**

```python
# confiq/schema/pydantic_adapter.py
from typing import Any


class PydanticAdapter:
    def __init__(self, model_cls: type) -> None:
        from pydantic import BaseModel
        if not issubclass(model_cls, BaseModel):
            raise TypeError(f"{model_cls!r} is not a pydantic BaseModel")
        self.model_cls = model_cls

    def validate(self, data: dict[str, Any]) -> Any:
        return self.model_cls.model_validate(data)

    def defaults(self) -> dict[str, Any]:
        try:
            return self.model_cls().model_dump()
        except Exception:
            return self.model_cls.model_construct().model_dump()


# confiq/schema/dataclass_adapter.py
import warnings
from dataclasses import fields, is_dataclass
from typing import Any


class DataclassAdapter:
    def __init__(self, dc_cls: type) -> None:
        if not is_dataclass(dc_cls):
            raise TypeError(f"{dc_cls!r} is not a dataclass")
        self.dc_cls = dc_cls

    def validate(self, data: dict[str, Any]) -> Any:
        accepted = {f.name for f in fields(self.dc_cls)}
        unknown = set(data) - accepted
        if unknown:
            warnings.warn(
                f"Config keys {sorted(unknown)!r} are not fields of "
                f"{self.dc_cls.__name__!r} and will be ignored.",
                stacklevel=2,
            )
        return self.dc_cls(**{k: v for k, v in data.items() if k in accepted})


# confiq/schema/typeddict_adapter.py
from typing import Any


class TypedDictAdapter:
    def __init__(self, td_cls: type) -> None:
        self.td_cls = td_cls

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        return data
```

**4.9 Built-in sources — File, Env, Argparse**

```python
# confiq/sources/file.py
from pathlib import Path
from typing import Any
from .base import AbstractConfigSource, PRIORITY_FILE


class FileSource(AbstractConfigSource):
    protocol = "file"
    priority = PRIORITY_FILE

    def __init__(self, path: Any, *, required: bool = True, watch: bool = False,
                 file_format: str | None = None, plugin_manager: Any = None,
                 priority: int | None = None) -> None:
        super().__init__(priority=priority)
        self.path = Path(path)
        self.required = required
        self.watch_enabled = watch
        self.file_format = file_format
        self._pm = plugin_manager

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            if self.required:
                raise FileNotFoundError(self.path)
            return {}
        suffix = (self.file_format or self.path.suffix).lower()
        if not suffix.startswith("."):
            suffix = "." + suffix
        result = self._pm.hook.confiq_load_file(path=self.path, suffix=suffix)
        if result is None:
            raise ValueError(
                f"No registered loader handles suffix {suffix!r}. "
                f"Install confiq[yaml] / confiq[toml] or register a custom loader plugin."
            )
        return result

    def supports_watch(self) -> bool:
        return self.watch_enabled

    def watch(self, on_change: Any) -> Any:
        from confiq._watch import watch_path
        return watch_path(self.path, on_change)
```

```python
# confiq/sources/_coerce.py
# Shared by EnvSource and ArgparseSource; both need the same scalar-inference
# and path-assignment logic, so it lives here rather than in either module.
from typing import Any


def parse_env_value(v: str) -> Any:
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lstrip("-").isdigit():
        return int(v)
    try:
        return float(v)
    except ValueError:
        pass
    return v


def set_nested_path(d: dict[str, Any], parts: list[str], val: Any) -> None:
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = val


# confiq/sources/env.py
import os
from typing import Any
from .base import AbstractConfigSource, PRIORITY_ENV
from ._coerce import parse_env_value, set_nested_path


class EnvSource(AbstractConfigSource):
    protocol = "env"
    priority = PRIORITY_ENV

    def __init__(self, *, prefix: str = "", delimiter: str = "__",
                 dotenv: Any = None, priority: int | None = None) -> None:
        super().__init__(priority=priority)
        self.prefix, self.delimiter, self.dotenv = prefix, delimiter, dotenv

    def load(self) -> dict[str, Any]:
        env = dict(os.environ)
        if self.dotenv:
            env = {**_parse_dotenv_file(self.dotenv), **env}
        out: dict[str, Any] = {}
        plen = len(self.prefix)
        for k, v in env.items():
            if self.prefix and not k.startswith(self.prefix):
                continue
            parts = k[plen:].lower().split(self.delimiter)
            set_nested_path(out, parts, parse_env_value(v))
        return out
```

```python
# confiq/sources/argparse_source.py
import sys
from typing import Any
from .base import AbstractConfigSource, PRIORITY_CLI
from ._coerce import parse_env_value, set_nested_path


class ArgparseSource(AbstractConfigSource):
    protocol = "argparse"
    priority = PRIORITY_CLI

    def __init__(self, namespace: Any = None, *, argv: list[str] | None = None,
                 priority: int | None = None) -> None:
        super().__init__(priority=priority)
        self._ns = namespace
        self._argv = sys.argv[1:] if (namespace is None and argv is None) else argv

    def load(self) -> dict[str, Any]:
        if self._ns is not None:
            return _explode_dots(vars(self._ns))
        return _parse_dotted(self._argv or [])


def _parse_dotted(argv: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if not a.startswith("--"):
            i += 1
            continue
        a = a[2:]
        if "=" in a:
            k, v = a.split("=", 1)
            i += 1
        else:
            k = a
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                v = argv[i + 1]
                i += 2
            else:
                v = True  # type: ignore[assignment]
                i += 1
        set_nested_path(out, k.split("."), parse_env_value(v) if isinstance(v, str) else v)
    return out
```

**4.10 `DictSource` — inline dict layer**

```python
# confiq/sources/dict_source.py
from typing import Any
from .base import AbstractConfigSource, PRIORITY_FILE


class DictSource(AbstractConfigSource):
    """Wraps a pre-built dict as a config layer; canonical test primitive."""
    protocol = "dict"
    priority = PRIORITY_FILE

    def __init__(self, data: dict[str, Any], *, priority: int | None = None) -> None:
        super().__init__(priority=priority)
        self._data = data

    def load(self) -> dict[str, Any]:
        return dict(self._data)
```

**4.11 Cloud source stubs (extras)**

```python
# confiq/sources/aws_secrets.py     # requires extra: confiq[aws]
import json
from typing import Any
from .base import AbstractConfigSource, PRIORITY_CLOUD


class AwsSecretsManagerSource(AbstractConfigSource):
    protocol = "aws-secrets"
    priority = PRIORITY_CLOUD

    def __init__(self, *, secret_id: str, region: str | None = None,
                 boto_session: Any = None) -> None:
        super().__init__()
        try:
            import boto3
        except ImportError as e:
            raise ImportError("Install confiq[aws].") from e
        sess = boto_session or boto3.session.Session(region_name=region)
        self._client = sess.client("secretsmanager")
        self.secret_id = secret_id

    def load(self) -> dict[str, Any]:
        resp = self._client.get_secret_value(SecretId=self.secret_id)
        s = resp.get("SecretString")
        return json.loads(s) if s else {}


# confiq/sources/vault.py            # requires extra: confiq[vault]
import os
from typing import Any
from .base import AbstractConfigSource, PRIORITY_CLOUD

_VAULT_DATA_PREFIX = "secret/data/"


class VaultSource(AbstractConfigSource):
    protocol = "vault"
    priority = PRIORITY_CLOUD

    def __init__(self, *, addr: str, token: str | None = None,
                 path: str = "secret/data/app", mount_point: str = "secret") -> None:
        super().__init__()
        try:
            import hvac
        except ImportError as e:
            raise ImportError("Install confiq[vault].") from e
        self._client = hvac.Client(url=addr, token=token or os.environ.get("VAULT_TOKEN"))
        self.path, self.mount_point = path, mount_point

    def load(self) -> dict[str, Any]:
        if not self._client.is_authenticated():
            raise RuntimeError("Vault client is not authenticated")
        resp = self._client.secrets.kv.v2.read_secret_version(
            path=self.path.removeprefix(_VAULT_DATA_PREFIX),
            mount_point=self.mount_point,
        )
        return resp["data"]["data"]
```

### 5. Thread-safety design — the part that matters

This is the single most important design decision. The choice: **immutable snapshots + atomic reference swap + reentrancy fast-fail**.

**5.1 Why not an RWLock?**

See `docs/decisions/0001-lock-free-reads-via-immutable-snapshots.md` for the full reasoning. In brief:

1. **`config.get()` is on the hot path.** Even an uncontended `gen_rlock().acquire()` adds overhead per call. For a path that only loads one attribute, that is wasted work.
2. **A single attribute read on CPython is bytecode-atomic.** `snap = self._current` compiles to `LOAD_ATTR`. The GIL guarantees this doesn't tear, and `@dataclass(frozen=True, slots=True)` ensures the snapshot is fully built before publication.
3. **Writes are rare.** A `threading.Lock` for the write path is the right trade.

**5.2 Locking strategy in one table**

| Operation                               | Locking                            | Why                                   |
| --------------------------------------- | ---------------------------------- | ------------------------------------- |
| `config.get(...)` / `config.snapshot()` | **none**                           | reads one attribute                   |
| `config.override(...)`                  | none (uses `ContextVar`)           | async-safe, no contention             |
| `config.bind(schema)`                   | `threading.Lock`                   | rare, must serialize w/ reload        |
| `config.add_source(...)`                | `threading.Lock`                   | same                                  |
| `config.reload()`                       | `threading.Lock`                   | same                                  |
| `on_reload` hookimpls                   | none (daemon thread, outside lock) | prevents reentrancy deadlocks         |
| `before_publish` hookimpls              | inside `threading.Lock`            | invariant checks must run before swap |
| `after_merge` hookimpls                 | inside `threading.Lock`            | runs as part of build                 |

**5.3 The atomic-swap pattern**

```python
with self._lock:
    new_snap = build_snapshot_from_all_sources()   # may take time
    self._current = new_snap                       # ← single bytecode op
# All concurrent readers saw either the OLD snap or the NEW snap. Never broken.
```

Same idea as load-acquire/store-release on a pointer, used by persistent data structures and kernel RCU. Works in Python because (a) the GIL serializes individual bytecode ops, and (b) `frozen=True, slots=True` snapshots are immutable after publication.

**5.4 Avoiding deadlocks with subscribers**

A naive design has subscribers run inline inside the write lock. That deadlocks the moment a subscriber tries to read or mutate config. Two real-world bug reports make this pattern-instructive:

- **Loguru Issue #231**, _"Bug - Deadlock when using multithreaded & multiprocessing Environment"_, opened by @shachakz on Mar 30, 2020 against loguru 0.4.1 — multiprocessing forks while a handler's `_lock` is held by another thread → child deadlocks.
- **pydantic-settings Issue #351**, _"`AliasChoices` order overrides `settings_customise_sources` priority"_ — a precedence-interaction bug that demonstrates how subtle ordering hooks can be.

Our design:

1. The write builds the new snapshot, **publishes** it via atomic store, _then_ spawns a daemon thread to dispatch the `on_reload` hook.
2. Hookimpls receive `(old_model, new_model)` — they don't have to call `config.get()`, removing one footgun.
3. If a hookimpl re-enters the write path, the reentrancy guard fires loudly — exactly what loguru's `_protected_lock` does. Verbatim from `github.com/Delgan/loguru/blob/master/loguru/_handler.py`: _"Could not acquire internal lock because it was already in use (deadlock avoided). This likely happened because the logger was re-used inside a sink, a signal handler or a '**del**' method."_ We borrow the message wording and the failure mode.
4. Pluggy itself propagates exceptions by default. We catch at the daemon-thread boundary so one bad subscriber doesn't crash the notifier.

**5.5 Async (asyncio) compatibility**

- **Concurrent reads from coroutines:** `config.get()` is sync and lock-free; coroutines can call it freely. No event-loop blocking.
- **Per-task overrides:** must use `contextvars`, not `threading.local`. The stdlib docs are explicit: _"Context managers that have state should use Context Variables instead of threading.local() to prevent their state from bleeding to other code unexpectedly, when used in concurrent code."_ (`docs.python.org/3/library/contextvars.html`). We use `ContextVar` for `config.override(...)`. Each `asyncio.Task` inherits its parent's context at creation (PEP 567).
- **Async reload triggers:** the write path is sync. From async, do `await loop.run_in_executor(None, config.reload)`. Reload is rare enough that the threadpool detour is fine. For fully-async needs, `aiorwlock` is the right tool.

**5.6 Why `threading.Lock` (not `RLock`) for the write lock?**

`RLock` would _allow_ the same thread to re-acquire — convenient, but it would _hide_ the bug we want to surface (a hookimpl synchronously mutating config). loguru pairs a non-reentrant lock with a `threading.local` reentrancy detector for exactly this reason; we follow suit.

### 6. Pydantic integration in depth

**6.1 Generic `Config[T]` for IDE autocomplete**

```python
from confiq import Config
from settings import Settings

config: Config[Settings] = Config().bind(Settings)
s = config.get()        # IDE knows this is Settings
s.database.host         # autocompletes
```

`Config` is `Generic[T]` with `T = TypeVar("T")`. `bind(schema: type[T]) -> Config[T]` carries `T` through the type checker. The module-level `config` is typed as `Config[Any]` until the user re-annotates.

**6.2 Customising precedence (pydantic-settings parity)**

```python
config.reprioritize_sources(key=custom_key)
```

This is the equivalent of pydantic-settings' `settings_customise_sources`. The pydantic-settings docs (`docs.pydantic.dev/2.0/usage/pydantic_settings/`) state: _"settings_customise_sources takes four callables as arguments and returns any number of callables as a tuple. ... The order of the returned callables decides the priority of inputs; first item is the highest priority."_ `reprioritize_sources` acquires the write lock and rebuilds the snapshot, keeping the operation safe under concurrent reads.

**6.3 Partial updates against a schema**

```python
new = config.snapshot().model.model_copy(update={"debug": True})
config.patch(new)        # validate-and-publish; takes the write lock once.
```

`patch` validates the new model, then builds and atomic-swaps a snapshot with `raw = MappingProxyType(new.model_dump())`.

**6.4 Using `pydantic-settings` as a source**

```python
from pydantic_settings import BaseSettings
class MySettings(BaseSettings): ...

config.add_source(PydanticSettingsSource(MySettings))
```

pydantic-settings is the right tool when you want its env/secrets/cli wiring (it ships `AWSSecretsManagerSettingsSource`, `AzureKeyVaultSettingsSource`, `GoogleSecretManagerSettingsSource`, `CliSettingsSource`, etc.); `confiq` adds the _layering, snapshotting, watching, and pluggable cloud sources_ around it.

### 7. Optional dependency structure (`pyproject.toml`)

```toml
[project]
name = "confiq"
requires-python = ">=3.10"
dependencies = [
    "pydantic>=2.5",       # validation core
    "pluggy>=1.5",         # plugin framework (pytest's, zero transitive deps)
]

[project.optional-dependencies]
# File-format extras
yaml   = ["pyyaml>=6.0"]
toml   = ["tomli>=2.0; python_version<'3.11'"]
dotenv = ["python-dotenv>=1.0"]

# CLI extras
click  = ["click>=8.1"]
typer  = ["typer>=0.12"]

# Live reload
watch  = ["watchdog>=4.0"]

# Cloud / KMS extras
aws    = ["boto3>=1.34"]
gcp    = ["google-cloud-secret-manager>=2.18"]
azure  = ["azure-identity>=1.15", "azure-keyvault-secrets>=4.7"]
vault  = ["hvac>=2.0"]
consul = ["py-consul>=1.7"]

# Convenience meta-extras
# (Per Hynek Schlawack's "Recursive Optional Dependencies in Python":
#  "Since pip 21.2 you can refer to your own project in your optional dependencies.")
common = ["confiq[yaml,toml,dotenv,watch]"]
all    = ["confiq[yaml,toml,dotenv,watch,click,typer,aws,gcp,azure,vault,consul]"]
dev    = ["pytest>=8", "pytest-asyncio>=0.23", "mypy>=1.10", "ruff>=0.5"]

# Source-class registry (instances). Mirrors fsspec.specs.
[project.entry-points."confiq.sources"]
file       = "confiq.sources.file:FileSource"
env        = "confiq.sources.env:EnvSource"
argparse   = "confiq.sources.argparse_source:ArgparseSource"

# Pluggy hook implementations (stateless plugins).
# Third parties register here too; the plugin manager auto-discovers them
# via `pm.load_setuptools_entrypoints("confiq")`.
[project.entry-points.confiq]
# (built-ins are registered directly in _plugins.py; this group is for
#  third-party plugins, e.g. confiq-redact, confiq-vault-rotator, ...)
```

Notes:

- **`pydantic` and `pluggy` are the only mandatory deps.** Defensible: pydantic is fast (Rust core), widely installed, and obviates ~80% of the validation/coercion code competing libraries reinvent. Pluggy is tiny (no transitive deps), maintained by the pytest team, and gives us pytest-grade plugin ergonomics for free.
- **TOML on 3.10:** Python 3.11 ships `tomllib`; on 3.10 the `toml` extra installs `tomli`. The pluggy `toml_loader` hookimpl handles both.
- **`all` is a recursive extra.** Per Hynek Schlawack's "Recursive Optional Dependencies in Python" (`hynek.me/articles/python-recursive-optional-dependencies/`): _"Since pip 21.2 you can refer to your own project in your optional dependencies."_
- **Two entry-point groups, two purposes.** `confiq.sources` registers _classes_ (fsspec-style); `confiq` registers _hookimpl plugins_ (pluggy-style). A third-party package can use either or both.

### 8. Plugin systems: two patterns, one mental model

`confiq` exposes two distinct extension surfaces. The distinction matters.

**8.1 Source classes (fsspec-style) — for instantiable things with state**

Use when your plugin is a _thing the user constructs and configures_: a database client, a Vault session, an HTTP poller. Each instance has its own state and lifecycle.

```python
# confiq-redis/source.py
from confiq.sources.base import AbstractConfigSource, PRIORITY_FILE

class RedisSource(AbstractConfigSource):
    protocol = "redis"
    priority = PRIORITY_FILE

    def __init__(self, *, url: str, key: str) -> None:
        super().__init__()
        import redis
        self._r = redis.from_url(url)
        self._key = key

    def load(self) -> dict:
        import json
        raw = self._r.get(self._key)
        return json.loads(raw) if raw else {}
```

```toml
# confiq-redis/pyproject.toml
[project.entry-points."confiq.sources"]
redis = "confiq_redis.source:RedisSource"
```

User-facing:

```python
from confiq import config, create_source
config.add_source(create_source("redis", url="redis://localhost:6379", key="myapp/config"))
```

**8.2 Hookimpls (pluggy-style) — for stateless multi-participant logic**

Use when your plugin _participates in a coordinated event_: "redact this dict," "validate this snapshot," "log every reload."

```python
# confiq-redact/plugin.py
from confiq import hookimpl

class RedactSecrets:
    @hookimpl
    def confiq_after_merge(self, merged: dict) -> dict:
        return _walk_and_redact(merged)
```

```toml
# confiq-redact/pyproject.toml
[project.entry-points.confiq]
redact-secrets = "confiq_redact.plugin:RedactSecrets"
```

`pm.load_setuptools_entrypoints("confiq")` is called once at `confiq` import time. No user code change required.

**8.3 The rule of thumb**

| You want to...                                                     | Use                                                      |
| ------------------------------------------------------------------ | -------------------------------------------------------- |
| Add a new source of config (Redis, custom KV store, REST endpoint) | source class + `confiq.sources` entry point              |
| Add a new file format (JSON5, HCL, properties)                     | hookimpl on `confiq_load_file`                           |
| Add a new schema type (attrs, msgspec, marshmallow)                | hookimpl on `confiq_get_schema_adapter`                  |
| Transform the merged dict before validation                        | hookimpl on `confiq_after_merge`                         |
| Validate or log every config change                                | hookimpl on `confiq_before_publish` / `confiq_on_reload` |

This is exactly the pytest mental model: there are _fixtures_ (instances you compose) and there are _hooks_ (events you participate in). They're different tools.

### 9. Comparison with existing libraries

| Concern                           | **confiq (this design)**                                 | Dynaconf                                                   | pydantic-settings                               | Hydra/OmegaConf                                                         | python-decouple |
| --------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------------------- | --------------- |
| **One global object**             | yes (loguru-style)                                       | yes (`from dynaconf import settings`)                      | no — you instantiate `Settings()`               | per-`@hydra.main`                                                       | yes (`config`)  |
| **Pluggable source registry**     | **yes (entry points, fsspec-style)**                     | partial (`core_loaders`, custom loaders)                   | yes (`settings_customise_sources`)              | composable but not registry-based                                       | no              |
| **First-class plugin framework**  | **yes (pluggy)**                                         | no                                                         | no                                              | no                                                                      | no              |
| **Cloud sources**                 | optional extras (AWS/GCP/Azure/Vault/Consul)             | Vault, Redis built-in                                      | AWS, GCP, Azure source classes built in         | none built-in                                                           | none            |
| **Pydantic-native**               | **yes** (generic `Config[T]`)                            | optional integration                                       | **yes** (it _is_ pydantic)                      | no (dataclasses/attrs)                                                  | no              |
| **Schema validation**             | pydantic / dataclass / TypedDict / extensible via pluggy | rule-based `Validator(...)`                                | pydantic                                        | dataclass/attrs runtime                                                 | manual `cast=`  |
| **Thread safety**                 | **explicit, immutable snapshot + atomic swap**           | unspecified                                                | unspecified (per-instance, no shared state)     | **"OmegaConf is not thread-safe" (maintainer @omry, Discussion #1116)** | unspecified     |
| **Live reload**                   | watchdog-based, opt-in                                   | yes                                                        | no                                              | no                                                                      | no              |
| **Subscribers / observers**       | **yes (via `on_reload` pluggy hook)**                    | no                                                         | no                                              | no                                                                      | no              |
| **Async (contextvars) overrides** | **yes**                                                  | no                                                         | no                                              | no                                                                      | no              |
| **CLI parsing**                   | argparse default; click/typer extras                     | dynaconf CLI tool (not arg parsing)                        | argparse-style `cli_parse_args` (built in v2)   | own override DSL (`+a=1`)                                               | no              |
| **Precedence**                    | CLI>env>file>defaults (configurable)                     | layered envs + files (env-driven)                          | init>env>dotenv>secrets>defaults (configurable) | composition + overrides                                                 | env>file        |
| **Singleton-with-handlers**       | **yes (loguru-style)**                                   | yes                                                        | no                                              | no                                                                      | yes             |
| **Footgun count**                 | low (immutable snapshots)                                | medium (`environments=True` is viral; see Discussion #956) | low                                             | medium (interpolations + non-thread-safe)                               | low             |

**Where this package fits:** pydantic-settings' typed ergonomics + loguru's "one importable thing" ergonomics + fsspec's pluggable cloud-source story + pluggy's pytest-grade extension model + explicit, documented thread safety. The existing libraries each miss at least one of those five. This package's reason to exist is the union.

### 10. Open questions & trade-offs

1. **`Config` as class or module-level singleton?** _Choice: instance of a class with one canonical pre-built instance exposed as `confiq.config`._ Mirrors loguru exactly, allows testing (construct your own `Config()`), avoids module-level mutable-state gymnastics. Cost: users may accidentally construct multiple instances — documented; `confiq.get_default_config()` is the always-right answer.

2. **Pluggy as a hard dep.** _Choice: yes._ See `docs/decisions/0002-pluggy-as-plugin-framework.md`.

3. **Pydantic as a hard dep.** _Choice: yes._ See `docs/decisions/0005-pydantic-as-required-dependency.md`.

4. **Two extension surfaces (source classes + pluggy hooks) — is that confusing?** _Choice: yes, two, and document the rule clearly._ See `docs/decisions/0003-dual-extension-surfaces.md`. The §8.3 table is the canonical quick-reference.

5. **Immutable snapshots vs. mutable Config + RWLock.** _Choice: snapshots._ See `docs/decisions/0001-lock-free-reads-via-immutable-snapshots.md`.

6. **List merging: replace or concatenate?** _Choice: replace._ See `docs/decisions/0004-deep-merge-list-replacement-semantics.md`.

7. **Live reload by default?** _Choice: off._ `watch=True` per file. "Config is immutable for the process lifetime" is the safer default. The `on_reload` hook and `config.reload()` are always available.

8. **Built-in HTTP long-poll watcher?** Not in v1. The `ConfigSource.watch(on_change)` hook is in the protocol; extras can implement it later.

9. **Why not OmegaConf interpolations (`${foo.bar}`)?** They turn config evaluation into a graph problem with cycles, defaults, and order-dependent resolvers. OmegaConf itself is not thread-safe per its maintainer. Users who want it can pre-process YAML with `omegaconf` and pass the result through `add_source(DictSource(omegaconf.to_container(...)))` — or write a `before_load`/`after_merge` pluggy hookimpl that runs interpolation.

10. **Argparse default-handler ambiguity.** `add_argparse()` with no explicit `Namespace` consumes `sys.argv` permissively (`--a.b.c=value`). Friendly for ad-hoc scripts but conflicts with apps that have a "real" argparse parser. Documented: pass your own `Namespace` for production apps.

11. **`on_reload` thread vs. event loop.** We dispatch the hook on a daemon thread. Async users will sometimes want hookimpls on the event loop. v1 documents `loop.call_soon_threadsafe(...)` inside the hookimpl as the bridge; v2 may grow a paired `confiq_on_reload_async` hookspec that schedules onto a known loop.

12. **Versioning the snapshot.** `ConfigSnapshot.version` is a monotonic int. We considered a content hash for cache keys — deferred to v2 to keep the v1 surface small.

## Recommendations

**Staged implementation plan.**

1. **Week 1–2 — core skeleton.** Build `_core.py`, `_snapshot.py`, `_merge.py`, `_registry.py`, `_hookspecs.py`, `_plugins.py`, `_locks.py`, the `ConfigSource` protocol, and three sources: `FileSource` (JSON-only first, dispatched through the pluggy hook), `EnvSource`, `ArgparseSource`. Wire `PydanticAdapter` as a built-in hookimpl. Ship as `v0.1` with the lock-free read path + atomic swap + pluggy plugin manager as the architectural commitments. **Threshold to revisit:** if internal benchmarks show `config.get()` is slower than 200 ns on CPython 3.12, redesign.
2. **Week 3 — formats and live reload.** Add `[yaml]`, `[toml]`, `[dotenv]`, `[watch]` extras. Each format ships as a pluggy hookimpl. Implement `_watch.py` on top of `watchdog`. Wire the daemon-thread `on_reload` dispatcher. **Threshold:** if a single hookimpl can block another, switch to per-impl queues.
3. **Week 4 — CLI integrations.** `ArgparseSource` is already in v0.1. Add `[click]` and `[typer]` extras as thin adapters over their introspection APIs.
4. **Week 5–6 — cloud sources.** `[aws]` (SSM, Secrets Manager, S3 file), then `[vault]`, then `[gcp]` and `[azure]` in parallel. Each follows the same pattern as the existing skeletons in §4.10.
5. **Week 7 — async polish.** `config.override(...)` via `contextvars`. Document `loop.run_in_executor` for reload. Decide whether to ship `confiq_on_reload_async`. **Threshold:** if users routinely call `await config.reload_async()` and it forces an `asyncio.Lock` into the core, accept the per-event-loop lock as v1.5.
6. **Week 8 — docs, comparison page, migration guides from Dynaconf and pydantic-settings, plus a "writing a confiq plugin" tutorial that mirrors pytest's plugin guide.** Ship v1.0.

**Decisions to lock in now (not negotiable later):**

- One global `config` object. Don't ship a "loggers per module" API; users who want isolation construct a fresh `Config()`. (loguru learned this the hard way; their docs are now explicit: _"Since Loguru is designed on the use of a single logger, it is fundamentally not possible to create different loggers for multiple modules"_.)
- `ConfigSource.load()` returns a plain `dict`. Don't let sources return models. Validation happens in one place — the schema adapter, itself selected via pluggy.
- The hot read path takes no locks and invokes no pluggy hooks. If you find yourself adding either, you've taken the wrong turn.
- Two extension surfaces (source classes via fsspec registry, hookimpls via pluggy). Don't collapse them — they solve different problems.
- `freeze()` is one-way, permanently. Users who need a mutable instance for tests construct a fresh `Config()`. No `thaw()` will be added.

**Decisions that are deferrable:**

- Whether to back `_registry` with `entry_points(group=...)` lazily-on-first-use vs. at import. Either works.
- Whether `argparse` integration auto-parses or requires a pre-built `Namespace`. Ship permissive; tighten later.
- Whether to expose `pm` directly on `Config` for power users. Probably yes in v1.1.

## Caveats

- **The atomic-swap argument assumes CPython with the GIL.** On a free-threaded build (PEP 703, optional in 3.13+, becoming default later), `STORE_ATTR` is _still_ atomic for a single object reference per the Python data model, but the broader argument (other bytecodes are atomic by virtue of the GIL) loosens. The design is _still correct_ — frozen snapshots + a single reference store — but the merge path may need an explicit lock around dict reads if a custom source mutates a shared dict concurrently. The recommendation: keep the simple model; add a free-threading audit in v1.1.
- **Pluggy's `firstresult=True` semantics are strict.** Once a hookimpl returns a non-None value, no further impls are called. This applies to `confiq_load_file` (one loader per suffix), `confiq_get_schema_adapter` (one adapter per type), and `confiq_after_merge` (one transformer wins). Plugin order matters; `tryfirst=True` / `trylast=True` on the hookimpl decorator is the explicit override mechanism. Document the convention clearly: "register your impl with `tryfirst=True` to take priority over the built-ins."
- **Pydantic v2's behavior around generic models with `bound=BaseModel` has known sharp edges**, e.g. pydantic Issue #7562: serializing a generic with `bound=BaseModel` may produce an empty dict because pydantic treats the unparametrized form as `Any` for serialization. Users should _parametrize_ the generic at the call site (`Config[Settings]`), not lean on the bound for runtime serialization.
- **Live reload with watchdog has platform variance.** On Linux it uses `inotify`; on macOS `FSEvents`; on Windows `ReadDirectoryChangesW`; the fallback is `PollingObserver`. Editor save-then-rename patterns (Vim) can fire spurious events. The recommendation is debouncing the reload — the package should ship with a 100 ms debounce window.
- **`pydantic-settings` precedence interacts with `AliasChoices` in ways that surprise users** (their Issue #351, _"`AliasChoices` order overrides `settings_customise_sources` priority"_). When we add a `PydanticSettingsSource` adapter, document this loudly: aliases inside the pydantic model are resolved before our precedence chain sees the values.
- **OmegaConf is not interoperable for shared-state.** If a user passes a `DictConfig` into `add_source`, eagerly call `OmegaConf.to_container(cfg, resolve=True)` and store the plain dict. Holding a `DictConfig` reference is unsafe given the maintainer's explicit _"OmegaConf is not thread-safe"_ statement (`omry/omegaconf` Discussion #1116).
- **`on_reload` hookimpl failures are swallowed (with a printed traceback).** This is intentional — config notifications must not bring down the application — but it does mean a silently-broken hookimpl is possible. Document this; consider a `strict_hooks=True` flag on `Config()` in v1.1 for users who want exceptions to propagate.
- **The "recursive extra" syntax (`all = ["confiq[yaml,toml,...]"]`) requires pip ≥ 21.2.** Older pip will fail mysteriously. Document the minimum pip in the README.
- **This document describes a v1 design, not a finished package.** The code is illustrative — runnable-looking, not yet runnable. Helpers like `_assert_unfrozen`, `_maybe_attach_watch`, `_explode_dots`, and `_parse_dotenv_file` are referenced but not shown in full; they are mechanical implementations of obvious behavior. Expect 1800–2400 SLOC for v1, not counting cloud-source extras.
