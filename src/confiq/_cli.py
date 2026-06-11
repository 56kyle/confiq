"""CLI ergonomics: parameter path routing and Click option generation (design_d §10)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConfigBind:
    """Maps a CLI parameter to a dotted config path (design_d §10.2).

    Usage::

        log_level: Annotated[str | None, typer.Option(), ConfigBind("logging.level")] = None

    When the parameter name and config path match by convention (e.g. ``db_host``
    ↔ ``database.host``), no ConfigBind is needed.
    """

    path: str


def options_from(schema: type[Any]) -> list[Any]:
    """Emit Click Option objects from *schema*'s fields (design_d §10.4).

    Generates one Click option per schema field. Options default to the unset
    sentinel (None) so defaults live only in the schema and are never declared
    twice. Field names are converted to CLI flag names using the same
    name↔path convention as the consumer path (path → parameter).

    Returns a list of ``click.Option`` objects suitable for passing to a
    ``click.Command(params=[...])``.

    Requires click (confiq[cli]).
    """
    ...
