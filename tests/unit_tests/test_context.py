from __future__ import annotations

import threading
from typing import Any

from confiq.context import get_override
from confiq.context import override


def test_get_override_with_no_active_context() -> None:
    assert get_override() is None


def test_get_override_with_active_context() -> None:
    with override(name="temp"):
        assert get_override() == {"name": "temp"}


def test_get_override_after_context_exits() -> None:
    with override(name="temp"):
        pass
    assert get_override() is None


def test_get_override_with_exception_in_context() -> None:
    try:
        with override(name="temp"):
            raise ValueError("boom")
    except ValueError:
        pass
    assert get_override() is None


def test_get_override_with_thread_isolation() -> None:
    inner_value: list[Any] = []

    def worker() -> None:
        with override(name="thread-local"):
            inner_value.append(get_override())

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert inner_value == [{"name": "thread-local"}]
    assert get_override() is None


def test_get_override_with_nested_override() -> None:
    with override(host="outer"):
        outer_value = get_override()
        with override(host="inner"):
            assert get_override() == {"host": "inner"}
        assert get_override() == outer_value


def test_override_with_multiple_kwargs() -> None:
    with override(host="h", port=5432):
        result = get_override()
        assert result == {"host": "h", "port": 5432}
