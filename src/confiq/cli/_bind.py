"""Module defining ConfigBind for mapping CLI parameters to config paths."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigBind:
    """Maps a CLI parameter to a dotted config path (design_d §10.2).

    Usage::

        log_level: Annotated[str | None, typer.Option(), ConfigBind("logging.level")] = None

    When the parameter name and config path match by convention (e.g. ``db_host``
    ↔ ``database.host``), no ConfigBind is needed.
    """

    path: str
