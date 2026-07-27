# 11. CLI-to-config binding via ConfigBind annotation on command parameters

Date: 2026-06-02

## Status

Superseded by [ADR 0027](0027-cli-name-path-convention.md)

Specifically superseded: the opt-in participation model (only `ConfigBind`-marked
parameters enter the merge — design_d §10.2 and ADR 0027 make convention binding the
opt-out default) and `TyperSource` as a module-level alias of `ClickSource` (it is its
own class sharing the Click-context mechanism). The explicit-set detection mechanics
(`get_parameter_source()` / sentinel comparison) and the removal of `CliSource` /
`ConfigField.cli` carry forward unchanged.

## Context

The old `CliSource` parsed `sys.argv` manually, mapping `--dotted.key=value` tokens into a nested dict. This had two coupling problems:

1. **Schema awareness of CLI**: `ConfigField` carried a `cli: str | None` field so the schema could declare which CLI flag name corresponded to which field. This mixed CLI concerns into what should be a pure data description.
2. **Manual parsing duplicating framework logic**: Projects using Click, Typer, or argparse had already defined their CLI parameters with types, defaults, and validation. `CliSource` re-parsed `sys.argv` independently, meaning framework-level coercions and validations were bypassed, and the framework's already-parsed values were ignored.

A subtler problem with any naive framework-integrated approach is **default precedence**: if a CLI framework fills every parameter with either the explicit user value or the declared default, a source that reads all parameters would silently let defaults override higher-priority config file values.

## Decision

Introduce `ConfigBind("dotted.path")` — a frozen dataclass used as an `Annotated` marker on CLI function parameters (not on config schema fields). Framework-specific sources (`ClickSource` for Click/Typer, `ArgparseSource` for argparse) inspect the command function's type hints at `fetch()` time, collecting only parameters that:

- carry a `ConfigBind` marker, and
- were **explicitly set** on the command line (not defaulted).

For Click/Typer, "explicitly set" is determined by `ctx.get_parameter_source(param_name)` — values with `ParameterSource.DEFAULT` or `ParameterSource.DEFAULT_MAP` are skipped. For argparse, the parsed value is compared against `parser.get_default(param_name)` and skipped when equal.

`TyperSource` is a module-level alias for `ClickSource` since Typer is built on Click and its `Context` is a Click `Context`.

`CliSource`, `ConfigField.cli`, and the `cli` entry-point in `pyproject.toml` are removed.

## Consequences

**Positive:**
- Config schema (`ConfigField`) is fully ignorant of CLI. The `cli` field removal shrinks the schema surface and eliminates a category of coupling.
- Framework-parsed values are used directly — no re-parsing of `sys.argv`, no type coercion duplication, no divergence from what the framework already validated.
- The default-precedence problem is explicitly solved: only parameters the user actually typed on the command line enter the config merge chain.
- `ClickSource` / `TyperSource` / `ArgparseSource` are independently testable without spawning a subprocess or constructing `sys.argv`.
- `ConfigBind` is framework-agnostic; the binding declaration lives on the CLI side alongside the framework-specific option markers.

**Negative:**
- `CliSource` is removed. Any code using the old `sys.argv`-parsing approach must migrate to one of the framework-specific adapters, or construct a `MemorySource` manually if framework integration is not desired.
- `ArgparseSource`'s default-detection uses value equality (`actual == default`), which fails for mutable or non-comparable defaults. This is an edge case in typical CLI usage but is a known limitation.
- `ClickSource` requires `click` to be installed (`confiq[click]` extra). Importing `ClickSource` without click raises `ImportError` at construction time, not import time.
