"""Unit tests pinning the Stage 8 reentrancy guard (`confiq._locks.ReentrancyGuard`).

The guard is the fast-fail detector wrapped around the reload body: a subscriber that
re-enters reload() must raise rather than deadlock, and the lock must release on every
exit path so a handle stays reloadable after an error (design_d §9.2).
"""

from __future__ import annotations

import pytest

from confiq._locks import ReentrancyGuard


def test_guard_acquires_and_releases_allowing_reentry_after_normal_exit() -> None:
    guard = ReentrancyGuard()

    with guard as entered:
        assert entered is guard

    with guard:
        pass


def test_nested_entry_raises_runtime_error() -> None:
    guard = ReentrancyGuard()

    with pytest.raises(RuntimeError, match="re-entered"), guard, guard:
        pass


def test_lock_released_after_exception_inside_block_allows_reentry() -> None:
    guard = ReentrancyGuard()

    with pytest.raises(ValueError, match="boom"), guard:
        raise ValueError("boom")

    with guard:
        pass
