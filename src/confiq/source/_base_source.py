"""Module defining a convenience base class for synchronous configuration sources."""

from __future__ import annotations


class BaseSource:
    """Convenience base class for synchronous sources (design_d §5.1).

    Supplies a profile=None default so concrete sources need only implement name
    and fetch.
    """

    profile: str | None = None
