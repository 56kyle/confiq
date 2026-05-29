from __future__ import annotations

import typing
from typing import Any

from confiq.schema._field import ConfigField


def field_meta(model: type, field_name: str) -> ConfigField | None:
    try:
        hints: dict[str, Any] = typing.get_type_hints(model, include_extras=True)
    except (TypeError, NameError, AttributeError):
        return None

    annotated_type = hints.get(field_name)
    if annotated_type is None:
        return None

    if typing.get_origin(annotated_type) is not typing.Annotated:
        return None

    for meta in typing.get_args(annotated_type)[1:]:
        if isinstance(meta, ConfigField):
            return meta

    return None
