"""Module containing schema-kind detection predicates used by the confiq adapter layer."""

from __future__ import annotations

import dataclasses
import typing
from typing import TypeGuard

import typing_extensions
from pydantic import BaseModel
from pydantic.dataclasses import is_pydantic_dataclass


def is_base_model(schema: object) -> TypeGuard[type[BaseModel]]:
    """Reports whether schema is a pydantic BaseModel subclass."""
    return isinstance(schema, type) and issubclass(schema, BaseModel)


def is_pydantic_dataclass_type(schema: object) -> bool:
    """Reports whether schema is a pydantic dataclass class."""
    return isinstance(schema, type) and is_pydantic_dataclass(schema)


def is_pydantic_schema(schema: object) -> bool:
    """Reports whether schema is a pydantic BaseModel subclass or a pydantic dataclass."""
    return is_base_model(schema) or is_pydantic_dataclass_type(schema)


def is_stdlib_dataclass(schema: object) -> bool:
    """Reports whether schema is a stdlib dataclass and not a pydantic dataclass."""
    return dataclasses.is_dataclass(schema) and not is_pydantic_dataclass_type(schema)


def is_typed_dict(schema: object) -> bool:
    """Reports whether schema is a TypedDict class (typing or typing_extensions on the 3.10 floor)."""
    return typing.is_typeddict(schema) or typing_extensions.is_typeddict(schema)


def is_supported_nested_kind(schema: object) -> bool:
    """Reports whether schema is a schema kind the path table recurses into (ADR 0026)."""
    return is_pydantic_schema(schema) or is_stdlib_dataclass(schema) or is_typed_dict(schema)
