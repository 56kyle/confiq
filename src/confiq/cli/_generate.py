"""Module defining options_from for generating CLI options from a schema."""
from __future__ import annotations

from typing import Any


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
