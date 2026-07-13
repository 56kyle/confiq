"""CLI ergonomics: parameter path routing and Click option generation (design_d §10)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from confiq._imports import import_optional
from confiq.adapter._path_table import build_path_table
from confiq.adapter._path_table import leaf_paths


@dataclass(frozen=True)
class ConfigBind:
    """Maps a CLI parameter to a dotted config path, or opts it out (design_d §10.2, ADR 0027).

    Usage::

        log_level: Annotated[str | None, typer.Option(), ConfigBind("logging.level")] = None

    When the parameter name and config path match by convention (e.g. ``db_host``
    ↔ ``database.host``), no ConfigBind is needed.

    ``ConfigBind(None)`` is a meaningful opt-out: a CLI parameter whose name coincidentally
    matches a schema path is treated as a plain flag, not config, and never participates in
    the merge.
    """

    path: str | None


def options_from(schema: type[Any]) -> list[Any]:
    """Emit one click.Option per schema leaf path (design_d §10.4, ADR 0027).

    Each option is a ConfiqOption carrying its confiq_path, defaults to the unset sentinel
    (None) so defaults live only in the schema, and takes the flag the name↔path convention
    produces forward: dotted path → underscore-joined parameter → --kebab-case flag. Requires
    click (confiq[cli]).
    """
    option_type = _confiq_option_type()
    table = build_path_table(schema)
    return [option_type(_flag_for(path), confiq_path=path, default=None) for path in sorted(leaf_paths(table))]


def _flag_for(path: str) -> str:
    """Run the name↔path convention forward: dotted path → --kebab-case flag (ADR 0027)."""
    return "--" + path.replace(".", "_").replace("_", "-")


@lru_cache(maxsize=1)
def _confiq_option_type() -> type[Any]:
    """Build the ConfiqOption class, deferring its optional click base to call time (ADR 0032)."""
    click = import_optional("click", extra="cli")

    class ConfiqOption(click.Option):  # pyright: ignore[reportUntypedBaseClass, reportAny]  # optional-dep base is Any
        """A click.Option carrying the schema leaf path it was generated for (ADR 0027, 0049)."""

        def __init__(self, *param_decls: str, confiq_path: str, **kwargs: object) -> None:
            self.confiq_path: str = confiq_path
            super().__init__(list(param_decls), **kwargs)  # pyright: ignore[reportUnknownMemberType]  # Any base

    return ConfiqOption
