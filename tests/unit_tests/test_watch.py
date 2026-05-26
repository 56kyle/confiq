"""Tests for _watch.py and FileSource watch integration."""
from __future__ import annotations

import json
import time

import pytest

from confiq._registry import MissingDependencyError


watchdog = pytest.importorskip("watchdog", reason="confiq[watch] not installed")


class TestWatchPath:
    def test_calls_on_change_after_file_modified(self, tmp_path):
        from confiq._watch import watch_path

        f = tmp_path / "cfg.json"
        f.write_text('{"x": 1}')
        called: list[int] = []

        stop = watch_path(f, lambda: called.append(1))
        try:
            time.sleep(0.05)
            f.write_text('{"x": 2}')
            time.sleep(0.4)  # debounce + observer latency
            assert len(called) >= 1
        finally:
            stop()

    def test_stopper_cleans_up_without_error(self, tmp_path):
        from confiq._watch import watch_path

        f = tmp_path / "cfg.json"
        f.write_text("{}")
        stop = watch_path(f, lambda: None)
        stop()  # must not raise

    def test_debounce_coalesces_rapid_writes(self, tmp_path):
        from confiq._watch import watch_path

        f = tmp_path / "cfg.json"
        f.write_text('{"v": 0}')
        called: list[int] = []

        stop = watch_path(f, lambda: called.append(1))
        try:
            time.sleep(0.05)
            # Write 5 times faster than the debounce window
            for i in range(5):
                f.write_text(f'{{"v": {i}}}')
                time.sleep(0.02)
            time.sleep(0.4)
            # All rapid writes should collapse into ≤ 2 callbacks
            assert 1 <= len(called) <= 2
        finally:
            stop()

    def test_missing_watchdog_raises_missing_dependency(self, tmp_path, monkeypatch):
        import sys
        import types

        # Simulate watchdog not installed
        monkeypatch.setitem(sys.modules, "watchdog", None)
        monkeypatch.setitem(sys.modules, "watchdog.events", None)
        monkeypatch.setitem(sys.modules, "watchdog.observers", None)

        # Force re-import by removing cached module
        watch_mod = sys.modules.pop("confiq._watch", None)
        try:
            from confiq._watch import watch_path

            f = tmp_path / "cfg.json"
            f.write_text("{}")
            with pytest.raises(MissingDependencyError, match="confiq\\[watch\\]"):
                watch_path(f, lambda: None)
        finally:
            # Restore
            if watch_mod is not None:
                sys.modules["confiq._watch"] = watch_mod


class TestFileSourceWatch:
    def test_add_file_with_watch_triggers_reload(self, tmp_path):
        from confiq._core import Config

        f = tmp_path / "config.json"
        f.write_text(json.dumps({"name": "initial"}))

        cfg = Config()
        cfg.add_file(f, watch=True)

        time.sleep(0.05)
        assert cfg.get("name") == "initial"

        f.write_text(json.dumps({"name": "updated"}))
        time.sleep(0.4)
        assert cfg.get("name") == "updated"
