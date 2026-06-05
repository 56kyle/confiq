"""Module containing custom types used throughout the confiq package."""

from typing import Literal
from typing import TypeAlias
from typing import TypeVar


T = TypeVar("T")

ListFillBehavior: TypeAlias = Literal["override", "fill"]
