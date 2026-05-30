from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel

from confiq.schema._field import ConfigField
from confiq.schema._meta import field_meta


class MyModel(BaseModel, frozen=True):
    plain: str = "default"
    annotated: Annotated[str, ConfigField(env="MY_VAR")] = "default"
    other_meta: Annotated[str, "just a string"] = "default"


def test_returns_none_for_plain_field() -> None:
    assert field_meta(MyModel, "plain") is None


def test_returns_none_for_missing_field() -> None:
    assert field_meta(MyModel, "nonexistent") is None


def test_returns_config_field_for_annotated_field() -> None:
    result = field_meta(MyModel, "annotated")
    assert isinstance(result, ConfigField)
    assert result.env == "MY_VAR"


def test_returns_none_for_annotated_without_config_field() -> None:
    assert field_meta(MyModel, "other_meta") is None
