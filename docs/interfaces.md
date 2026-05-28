# confiq — Interface Space

A menu of choices across eight independent axes. Each variant is a concrete, self-contained sketch — not a tutorial. The goal is to lay the full space out side-by-side so the final public API can be chosen with the trade-offs visible.

---

## Axis 1 — Entry point

How the user gets hold of the config object.

---

**1-A · Global singleton**

```python
from confiq import config
from myapp.settings import Settings

config.bind(Settings).add_env(prefix="MYAPP_").add_file("config.toml").freeze()

host = config.get().database.host
level = config.get("log_level", default="INFO")
```

Loguru ergonomics — one import, works anywhere; makes testing without monkeypatching harder.

---

**1-B · `load()` function**

```python
from confiq import load
from confiq.sources import FileSource, EnvSource
from myapp.settings import Settings

config = load(
    Settings,
    sources=[FileSource("config.toml"), EnvSource(prefix="MYAPP_")],
)

print(config.database.host)
print(config.log_level)
```

Explicitly functional — config is a value you construct and pass around; no ambient global state.

---

**1-C · Constructor**

```python
from confiq import Config
from confiq.sources import FileSource, EnvSource
from myapp.settings import Settings

config = Config(Settings, FileSource("config.toml"), EnvSource(prefix="MYAPP_"))

print(config.database.host)
print(config.debug)
```

Familiar OOP shape; sources are constructor arguments so the object is valid at construction time.

---

**1-D · Decorator on the schema class**

```python
from confiq import confiq
from confiq.sources import FileSource, EnvSource

@confiq(sources=[FileSource("config.toml"), EnvSource(prefix="MYAPP_")])
class Settings:
    database_host: str = "localhost"
    log_level: str = "INFO"
    debug: bool = False

print(Settings.database.host)
print(Settings.log_level)
```

Schema definition and source wiring live in one place; schema class doubles as the config object.

---

## Axis 2 — Schema definition

How the shape of config is declared.

---

**2-A · Plain `pydantic.BaseModel`**

```python
from pydantic import BaseModel
from confiq import load
from confiq.sources import EnvSource

class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432
    password: str = ""

class Settings(BaseModel):
    debug: bool = False
    log_level: str = "INFO"
    database: Database = Database()

config = load(Settings, sources=[EnvSource(prefix="MYAPP_")])
print(config.database.host)
```

Zero friction for existing pydantic users; confiq has no metadata hook point on fields.

---

**2-B · confiq `Settings` base**

```python
from typing import Annotated
from confiq import load
from confiq.schema import Settings, ConfigField
from confiq.sources import EnvSource

class Database(Settings):
    host: Annotated[str, ConfigField(env="DB_HOST")] = "localhost"
    port: Annotated[int, ConfigField(env="DB_PORT")] = 5432
    password: Annotated[str, ConfigField(env="DB_PASSWORD", secret=True)] = ""

class AppSettings(Settings):
    debug: bool = False
    log_level: str = "INFO"
    database: Database = Database()

config = load(AppSettings, sources=[EnvSource()])
```

Slight coupling to confiq; unlocks per-field metadata without fighting type checkers.

---

**2-C · `@dataclass`**

```python
from dataclasses import dataclass, field
from confiq import load
from confiq.sources import EnvSource

@dataclass
class Database:
    host: str = "localhost"
    port: int = 5432
    password: str = ""

@dataclass
class Settings:
    debug: bool = False
    log_level: str = "INFO"
    database: Database = field(default_factory=Database)

config = load(Settings, sources=[EnvSource(prefix="MYAPP_")])
print(config.database.host)
```

No coercion or validation; confiq does basic type casting only.

---

**2-D · No schema (schemaless)**

```python
from confiq import load
from confiq.sources import FileSource, EnvSource

config = load(sources=[FileSource("config.toml"), EnvSource(prefix="MYAPP_")])

host = config.get("database.host", default="localhost")
port = config.get("database.port", cast=int, default=5432)
debug = config.get("debug", cast=bool, default=False)
```

Zero setup for simple scripts; no type safety at access time.

---

## Axis 3 — Per-field metadata

Env names, CLI flags, secrets, custom parsers.

---

**3-A · None — convention only**

```python
from pydantic import BaseModel
from confiq import load
from confiq.sources import EnvSource

class Database(BaseModel):
    host: str = "localhost"     # reads MYAPP_DATABASE__HOST
    port: int = 5432            # reads MYAPP_DATABASE__PORT
    password: str = ""          # reads MYAPP_DATABASE__PASSWORD

class Settings(BaseModel):
    log_level: str = "INFO"     # reads MYAPP_LOG_LEVEL
    debug: bool = False         # reads MYAPP_DEBUG
    database: Database = Database()

config = load(Settings, sources=[EnvSource(prefix="MYAPP_")])
```

Minimal boilerplate; loses the ability to diverge from the naming convention per field.

---

**3-B · `Annotated` + `ConfigField` (Typer-style)**

```python
from typing import Annotated
from confiq.schema import Settings, ConfigField
from confiq import load
from confiq.sources import EnvSource, CliSource

class Database(Settings):
    host: Annotated[str, ConfigField(env="DB_HOST", cli="--db-host")] = "localhost"
    port: Annotated[int, ConfigField(env="DB_PORT", cli="--db-port")] = 5432
    password: Annotated[str, ConfigField(env="DB_PASSWORD", secret=True)] = ""

class AppSettings(Settings):
    log_level: Annotated[str, ConfigField(env="LOG_LEVEL", cli="--log-level")] = "INFO"
    debug: Annotated[bool, ConfigField(cli="--debug")] = False
    database: Database = Database()

config = load(AppSettings, sources=[EnvSource(), CliSource()])
```

Explicit, readable, type-checker-safe; verbose for large schemas.

---

**3-C · pydantic-settings `Field`**

```python
from pydantic import BaseModel, Field
from confiq import load
from confiq.sources import EnvSource

class Database(BaseModel):
    host: str = Field("localhost", validation_alias="DB_HOST")
    port: int = Field(5432, validation_alias="DB_PORT")
    password: str = Field("", validation_alias="DB_PASSWORD")

class Settings(BaseModel):
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    debug: bool = Field(False, validation_alias="APP_DEBUG")
    database: Database = Field(default_factory=Database)

config = load(Settings, sources=[EnvSource()])
```

Zero new types — users already know pydantic `Field`; loses CLI and secret metadata.

---

**3-D · Separate mapping dict**

```python
from pydantic import BaseModel
from confiq import load
from confiq.schema import FieldMeta
from confiq.sources import EnvSource

class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432
    password: str = ""

class Settings(BaseModel):
    log_level: str = "INFO"
    debug: bool = False
    database: Database = Database()

field_map = {
    "database.host": FieldMeta(env="DB_HOST", secret=False),
    "database.password": FieldMeta(env="DB_PASSWORD", secret=True),
    "log_level": FieldMeta(env="LOG_LEVEL"),
}

config = load(Settings, sources=[EnvSource()], field_map=field_map)
```

Keeps the schema clean of confiq-isms; mapping lives apart from the type definition.

---

## Axis 4 — Source specification

How the list of config sources is expressed.

---

**4-A · Explicit list to `load()`**

```python
from confiq import load
from confiq.sources import FileSource, EnvSource, CliSource
from myapp.settings import Settings

config = load(
    Settings,
    sources=[
        FileSource("config.toml", required=False),
        EnvSource(prefix="MYAPP_"),
        CliSource(),
    ],
)
print(config.database.host)
```

Precedence is explicit and visible at the call site; slightly more verbose.

---

**4-B · Fluent method chaining**

```python
from confiq import config
from myapp.settings import Settings

config\
    .bind(Settings)\
    .add_file("config.toml", required=False)\
    .add_env(prefix="MYAPP_")\
    .add_argparse()\
    .freeze()

print(config.get().database.host)
print(config.get().log_level)
```

Readable build sequence; mutates state incrementally, making the object valid partway through construction.

---

**4-C · Auto-discovery**

```python
from confiq import load
from myapp.settings import Settings

# Finds config.{toml,yaml,json} in CWD; reads MYAPP_* from os.environ.
config = load(Settings, prefix="MYAPP_")

print(config.database.host)
print(config.debug)
```

Zero configuration for the common case; discovery rules must be documented clearly to avoid surprises.

---

**4-D · Variadic positional**

```python
from confiq import Config
from confiq.sources import FileSource, EnvSource, CliSource
from myapp.settings import Settings

config = Config(
    Settings,
    FileSource("config.toml", required=False),
    EnvSource(prefix="MYAPP_"),
    CliSource(),
)

print(config.database.host)
print(config.log_level)
```

Sources are part of the constructor signature — no mutation after construction; slightly unusual Python idiom.

---

## Axis 5 — Read interface

How values are accessed from the loaded config.

---

**5-A · Attribute access only**

```python
from confiq import load
from confiq.sources import FileSource, EnvSource
from myapp.settings import Settings

config = load(Settings, sources=[FileSource("config.toml"), EnvSource(prefix="MYAPP_")])

host: str = config.database.host       # str — type checker knows
port: int = config.database.port       # int — type checker knows
level: str = config.log_level
flag: bool = config.debug
```

Fully type-safe; requires a schema; dynamic key access is impossible.

---

**5-B · Dotted string keys**

```python
from confiq import load
from confiq.sources import FileSource, EnvSource

config = load(sources=[FileSource("config.toml"), EnvSource(prefix="MYAPP_")])

host = config.get("database.host", default="localhost", cast=str)
port = config.get("database.port", default=5432, cast=int)
level = config.get("log_level", default="INFO")
debug = config.get("debug", default=False, cast=bool)
```

Flexible and schemaless-friendly; returns `Any`, so type checkers can't help.

---

**5-C · Subscript**

```python
from confiq import load
from confiq.sources import FileSource, EnvSource

config = load(sources=[FileSource("config.toml"), EnvSource(prefix="MYAPP_")])

host = config["database"]["host"]
port = config["database"]["port"]
level = config["log_level"]
debug = config["debug"]
```

Familiar dict-like ergonomics; same type-safety loss as dotted strings.

---

**5-D · Hybrid — attribute primary, `get()` as escape hatch**

```python
from confiq import load
from confiq.sources import FileSource, EnvSource
from myapp.settings import Settings

config = load(Settings, sources=[FileSource("config.toml"), EnvSource(prefix="MYAPP_")])

host: str = config.database.host          # typed — IDE autocompletes
level: str = config.log_level             # typed

dynamic_key = "database.password"
secret = config.get(dynamic_key)          # escape hatch — returns Any
```

Best of both; two mental models to document and keep consistent.

---

## Axis 6 — Override / test isolation

How config is overridden in tests or per-request.

---

**6-A · Context manager on singleton**

```python
from confiq import config
from myapp.settings import Settings

config.bind(Settings).add_env(prefix="MYAPP_").freeze()

def test_uses_test_database():
    with config.override(database={"host": "test-db", "port": 5433}):
        result = run_query()
    assert result is not None
```

No test setup/teardown boilerplate; tied to the singleton, so works poorly with parallel test runners.

---

**6-B · `MemorySource` / `DictSource` in a fresh `load()`**

```python
from confiq import load
from confiq.sources import MemorySource
from myapp.settings import Settings

def test_uses_test_database():
    config = load(
        Settings,
        sources=[MemorySource({"database": {"host": "test-db", "port": 5433}})],
    )
    result = run_query(config)
    assert result is not None
```

Completely hermetic per test; requires passing config explicitly rather than using a global.

---

**6-C · Fresh instance**

```python
from confiq import Config
from myapp.settings import Settings

def test_uses_test_database():
    cfg = (
        Config()
        .bind(Settings)
        .add_dict({"database": {"host": "test-db", "port": 5433}})
    )
    result = run_query(cfg.get())
    assert result is not None
```

Same hermetic guarantee as 6-B; uses the mutable builder idiom so tests mirror production setup code.

---

**6-D · `confiq.testing.patch()`**

```python
import pytest
from confiq import config
from confiq.testing import patch
from myapp.settings import Settings

config.bind(Settings).add_env(prefix="MYAPP_").freeze()

def test_uses_test_database():
    with patch(config, database__host="test-db", database__port=5433):
        result = run_query()
    assert result is not None
```

Highest-level ergonomics for the singleton case; `database__host` double-underscore syntax needs learning.

---

## Axis 7 — Reload / live config

How config changes at runtime.

---

**7-A · Explicit `reload()` + subscriber decorator**

```python
from confiq import config
from myapp.settings import Settings

config.bind(Settings).add_file("config.yaml", watch=False).add_env(prefix="MYAPP_").freeze()

@config.on_reload
def on_change(old: Settings, new: Settings) -> None:
    if old.database != new.database:
        pool.reconfigure(new.database)

config.reload()
```

Reload is explicit and auditable; subscribers run on a background thread.

---

**7-B · `ConfigHandle[T]`**

```python
from confiq import ConfigHandle
from confiq.sources import FileSource, EnvSource
from myapp.settings import Settings

handle = ConfigHandle.create(
    Settings,
    sources=[FileSource("config.yaml"), EnvSource(prefix="MYAPP_")],
)

cfg: Settings = handle.current()
print(cfg.database.host)

handle.reload()
cfg = handle.current()
print(cfg.log_level)
```

Reload surface is separate from the config value — clear ownership; slightly more boilerplate.

---

**7-C · File watching (auto-reload)**

```python
from confiq import config
from myapp.settings import Settings

config.bind(Settings).add_file("config.yaml", watch=True).add_env(prefix="MYAPP_").freeze()

@config.on_reload
def on_change(old: Settings, new: Settings) -> None:
    if old.log_level != new.log_level:
        logger.info("Log level changed to {}", new.log_level)
```

Zero manual reload calls; depends on `watchdog` extra; debounce behavior must be configured.

---

**7-D · Immutable / no reload**

```python
from confiq import load
from confiq.sources import FileSource, EnvSource
from myapp.settings import Settings

config = load(
    Settings,
    sources=[FileSource("config.toml"), EnvSource(prefix="MYAPP_")],
)

# config is frozen; no .reload() surface exists.
print(config.database.host)
print(config.debug)
```

Simplest mental model — config is a value; process restart is the reload mechanism.

---

## Axis 8 — CLI integration

How command-line arguments feed into config.

---

**8-A · Auto-generated from schema**

```python
from typing import Annotated
from confiq.schema import Settings, ConfigField
from confiq import load
from confiq.sources import EnvSource, CliSource

class AppSettings(Settings):
    log_level: Annotated[str, ConfigField(cli="--log-level", description="Logging level")] = "INFO"
    debug: Annotated[bool, ConfigField(cli="--debug")] = False
    database_host: Annotated[str, ConfigField(cli="--db-host")] = "localhost"

# CliSource() introspects the schema and generates flags automatically.
config = load(AppSettings, sources=[EnvSource(prefix="MYAPP_"), CliSource()])
print(config.log_level)
```

No argparse boilerplate; generated `--help` may not match a hand-crafted one.

---

**8-B · Manual argparse namespace**

```python
import argparse
from confiq import load
from confiq.sources import EnvSource, ArgparseSource
from myapp.settings import Settings

parser = argparse.ArgumentParser(description="My app")
parser.add_argument("--log-level", default=None)
parser.add_argument("--db-host", dest="database__host", default=None)
parser.add_argument("--debug", action="store_true", default=None)

ns = parser.parse_args()
config = load(Settings, sources=[EnvSource(prefix="MYAPP_"), ArgparseSource(ns)])
print(config.database.host)
```

Full control over `--help` and argument names; config wiring is explicit but manual.

---

**8-C · Typer decorator**

```python
import typer
from confiq.cli.typer import confiq_typer
from confiq.sources import EnvSource, FileSource
from myapp.settings import Settings

app = typer.Typer()

@app.command()
@confiq_typer(Settings, sources=[FileSource("config.toml"), EnvSource(prefix="MYAPP_")])
def serve(config: Settings) -> None:
    print(f"Starting on {config.database.host}:{config.database.port}")
    print(f"Log level: {config.log_level}")

if __name__ == "__main__":
    app()
```

Idiomatic for Typer apps; tight coupling between the CLI framework and the config system.

---

**8-D · Click pass-through**

```python
import click
from confiq import load
from confiq.sources import EnvSource, ClickSource
from myapp.settings import Settings

@click.command()
@click.option("--log-level", default=None)
@click.option("--db-host", default=None)
@click.option("--debug/--no-debug", default=None)
@click.pass_context
def main(ctx: click.Context, **kwargs: object) -> None:
    config = load(Settings, sources=[EnvSource(prefix="MYAPP_"), ClickSource(ctx)])
    print(config.database.host)
    print(config.log_level)
```

Works with existing Click commands without changing their signatures; relies on Click option naming matching config key naming.

---

## Composed examples

Four end-to-end examples, each combining choices across axes coherently.

---

**Example 1 — pydantic-settings replacement**

Axes: 1-B (`load()`), 2-B (confiq `Settings`), 3-B (`Annotated` + `ConfigField`), 4-A (explicit list), 5-A (attribute access), 7-D (immutable).

```python
from typing import Annotated
from confiq import load
from confiq.schema import Settings, ConfigField
from confiq.sources import FileSource, EnvSource

class Database(Settings):
    host: Annotated[str, ConfigField(env="DB_HOST")] = "localhost"
    port: Annotated[int, ConfigField(env="DB_PORT")] = 5432
    password: Annotated[str, ConfigField(env="DB_PASSWORD", secret=True)]

class AppSettings(Settings):
    debug: bool = False
    log_level: str = "INFO"
    database: Database

config = load(
    AppSettings,
    sources=[
        FileSource("config.toml", required=False),
        EnvSource(),
    ],
)

# config is frozen; attribute access is fully typed.
print(config.database.host)
print(config.database.port)
print(config.log_level)
```

---

**Example 2 — loguru-for-config**

Axes: 1-A (global singleton), 2-A (plain `BaseModel`), 3-A (no per-field metadata), 4-B (fluent chaining), 5-B (dotted `get()`), 7-C (file watch + `@on_reload`).

```python
from pydantic import BaseModel
from confiq import config

class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432

class Settings(BaseModel):
    debug: bool = False
    log_level: str = "INFO"
    database: Database = Database()

config\
    .bind(Settings)\
    .add_file("config.yaml", watch=True)\
    .add_env(prefix="MYAPP_")\
    .add_argparse()\
    .freeze()

@config.on_reload
def on_db_change(old: Settings, new: Settings) -> None:
    if old.database != new.database:
        pool.reconfigure(new.database)

host = config.get("database.host", default="localhost")
level = config.get("log_level", default="INFO")
```

---

**Example 3 — twelve-factor**

Axes: 1-B (`load()`), 2-D (schemaless), 4-A (explicit, env-only source), 5-B (dotted `get()`), 7-D (immutable).

```python
from confiq import load
from confiq.sources import EnvSource

# No schema. Reads environment only — classic twelve-factor.
config = load(sources=[EnvSource(prefix="MYAPP_")])

host = config.get("database__host", default="localhost")
port = config.get("database__port", default=5432, cast=int)
password = config.get("database__password", default="")
log_level = config.get("log_level", default="INFO")
debug = config.get("debug", default=False, cast=bool)
```

---

**Example 4 — plugin-extended**

Axes: 1-C (constructor), 2-B (confiq `Settings`), 4-D (variadic), 5-A (attribute access), 7-A (reload + subscriber via pluggy `hookimpl`).

```python
from typing import Annotated
from confiq import Config, hookimpl
from confiq.schema import Settings, ConfigField
from confiq.sources import EnvSource, FileSource
from confiq.sources.vault import VaultSource

class Database(Settings):
    host: Annotated[str, ConfigField(env="DB_HOST")] = "localhost"
    port: Annotated[int, ConfigField(env="DB_PORT")] = 5432
    password: Annotated[str, ConfigField(env="DB_PASSWORD", secret=True)]

class AppSettings(Settings):
    log_level: str = "INFO"
    debug: bool = False
    database: Database

class AuditPlugin:
    @hookimpl
    def confiq_on_reload(self, old: AppSettings, new: AppSettings) -> None:
        audit_log.record(old_version=old, new_version=new)

config = Config(
    AppSettings,
    FileSource("config.toml", required=False),
    EnvSource(prefix="MYAPP_"),
    VaultSource(addr="https://vault.example.com", path="secret/data/myapp"),
)
config.register_plugin(AuditPlugin())

print(config.database.host)
print(config.log_level)
```
