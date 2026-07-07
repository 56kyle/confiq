"""Unit tests pinning the Stage 2 secret-masking refusal (`confiq.adapter._secret_masking`, ADR 0039)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Annotated

import pytest
import typing_extensions
from pydantic import BaseModel

from confiq._field import ConfigField
from confiq.adapter._dataclass import DataclassAdapter
from confiq.adapter._pydantic import PydanticAdapter
from confiq.adapter._secret_masking import enforce_secret_masking
from confiq.adapter._typeddict import TypedDictAdapter
from confiq.exceptions import SchemaError
from confiq.exceptions import SecretMaskingError


if TYPE_CHECKING:
    from confiq.adapter._schema_adapter import SchemaAdapter


class UnmaskableWithSecret(typing_extensions.TypedDict):
    token: Annotated[str, ConfigField(secret=True)]


class UnmaskableWithTwoSecrets(typing_extensions.TypedDict):
    token: Annotated[str, ConfigField(secret=True)]
    password: Annotated[str, ConfigField(secret=True)]


class UnmaskableWithoutSecret(typing_extensions.TypedDict):
    token: str


class PydanticWithSecret(BaseModel):
    token: Annotated[str, ConfigField(secret=True)]


@dataclass
class DataclassWithSecret:
    token: Annotated[str, ConfigField(secret=True)]


def test_enforce_secret_masking_with_unmaskable_secret_field_raises() -> None:
    adapter = TypedDictAdapter(UnmaskableWithSecret)

    with pytest.raises(SecretMaskingError) as exc_info:
        enforce_secret_masking(adapter)

    assert exc_info.value.field_paths == ("token",)
    assert exc_info.value.schema_kind == "TypedDict"
    assert isinstance(exc_info.value, SchemaError)


def test_enforce_secret_masking_with_multiple_secret_fields_reports_all_paths() -> None:
    adapter = TypedDictAdapter(UnmaskableWithTwoSecrets)

    with pytest.raises(SecretMaskingError) as exc_info:
        enforce_secret_masking(adapter)

    assert set(exc_info.value.field_paths) == {"token", "password"}


@pytest.mark.parametrize(
    "adapter",
    [
        pytest.param(PydanticAdapter(PydanticWithSecret), id="pydantic"),
        pytest.param(DataclassAdapter(DataclassWithSecret), id="stdlib dataclass"),
    ],
)
def test_enforce_secret_masking_with_maskable_adapter_does_not_raise(adapter: SchemaAdapter[object]) -> None:
    enforce_secret_masking(adapter)


def test_enforce_secret_masking_with_unmaskable_adapter_and_no_secret_fields_does_not_raise() -> None:
    enforce_secret_masking(TypedDictAdapter(UnmaskableWithoutSecret))
