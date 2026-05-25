import threading
from contextlib import ExitStack

import pytest

from confiq._locks import ReentrancyGuard


def test_single_entry_succeeds():
    guard = ReentrancyGuard()
    with guard:
        pass  # should not raise


def test_reentry_raises_runtime_error():
    guard = ReentrancyGuard()
    with ExitStack() as stack:
        stack.enter_context(guard)
        stack.enter_context(pytest.raises(RuntimeError, match="deadlock avoided"))
        stack.enter_context(guard)


def test_guard_releases_after_exit():
    guard = ReentrancyGuard()
    with guard:
        pass
    # Second entry on the same thread should succeed after the first exits
    with guard:
        pass


def test_different_threads_are_independent():
    guard = ReentrancyGuard()
    errors: list[Exception] = []

    def enter_guard():
        try:
            with guard:
                pass
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=enter_guard) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected errors in threads: {errors}"


def test_guard_releases_even_on_exception():
    guard = ReentrancyGuard()
    try:
        with guard:
            raise ValueError("boom")
    except ValueError:
        pass
    # Should be able to enter again
    with guard:
        pass
