from __future__ import annotations

import threading

import pytest

from confiq._locks import ReentrancyGuard


def test_acquires_and_releases() -> None:
    guard = ReentrancyGuard()
    with guard:
        pass
    with guard:
        pass


def test_reentrant_same_thread_raises() -> None:
    guard = ReentrancyGuard()
    with pytest.raises(RuntimeError), guard, guard:
        pass


def test_different_threads_do_not_conflict() -> None:
    guard = ReentrancyGuard()
    errors: list[Exception] = []

    def worker() -> None:
        try:
            with guard:
                pass
        except Exception as exc:
            errors.append(exc)

    with guard:
        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=1.0)

    assert not errors


def test_lock_released_on_exception() -> None:
    guard = ReentrancyGuard()
    try:
        with guard:
            raise ValueError("boom")
    except ValueError:
        pass
    with guard:
        pass


def test_owner_cleared_after_exit() -> None:
    guard = ReentrancyGuard()
    with guard:
        pass
    assert guard._owner_ident is None
