from __future__ import annotations

import threading
from typing import Any

from confiq.context import get_override
from confiq.context import override


def test_no_override_returns_none() -> None:
    assert get_override() is None


def test_override_active_inside_context() -> None:
    with override(name="temp"):
        assert get_override() == {"name": "temp"}


def test_override_reverts_after_context_exits() -> None:
    with override(name="temp"):
        pass
    assert get_override() is None


def test_override_reverts_on_exception() -> None:
    try:
        with override(name="temp"):
            raise ValueError("boom")
    except ValueError:
        pass
    assert get_override() is None


def test_contextvar_isolation_between_threads() -> None:
    inner_value: list[Any] = []

    def worker() -> None:
        with override(name="thread-local"):
            inner_value.append(get_override())

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert inner_value == [{"name": "thread-local"}]
    assert get_override() is None


def test_nested_override_inner_does_not_bleed_out() -> None:
    with override(host="outer"):
        outer_value = get_override()
        with override(host="inner"):
            assert get_override() == {"host": "inner"}
        assert get_override() == outer_value


def test_multiple_patches() -> None:
    with override(host="h", port=5432):
        result = get_override()
        assert result == {"host": "h", "port": 5432}
