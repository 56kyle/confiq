"""Module containing the shared secret-masking enforcement helper for the confiq adapter layer."""

from __future__ import annotations

from typing import Any
from typing import cast

from confiq._field import ConfigField
from confiq.adapter._schema_adapter import SchemaAdapter
from confiq.exceptions import SecretMaskingError


def enforce_secret_masking(adapter: SchemaAdapter[Any]) -> None:
    """Refuses when an adapter that cannot mask secrets carries ConfigField(secret=True) (ADR 0039).

    Scans the adapter's path table once; if any path declares a secret field and the
    adapter cannot honor masking, raises SecretMaskingError naming every offending path
    and the schema kind.
    """
    if adapter.masks_secrets:
        return
    offending = tuple(
        path
        for path, extras in adapter.field_metadata().items()
        for extra in cast("list[object]", extras)
        if isinstance(extra, ConfigField) and extra.secret
    )
    if offending:
        raise SecretMaskingError(offending, adapter.kind)
