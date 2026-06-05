"""Module containing custom types used throughout the confiq package."""
from typing import TypeVar

from typing_extensions import Literal
from typing_extensions import TypeAlias


T = TypeVar("T")

ListFillBehavior: TypeAlias = Literal["override", "fill"]
