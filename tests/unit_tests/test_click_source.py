"""Unit tests pinning context-stack acquisition for the CLI binding sources (`confiq.source._click`).

Typer >= 0.26 vendors Click at `typer._click` with its own thread-local context stack, so context
acquisition is an ordered list of context-stack module names rather than a hardcoded `click.globals`
lookup (ADR 0054). The end-to-end proof of that lives in the integration suite but only bites in an
environment whose installed typer actually vendors Click; these tests pin the acquisition mechanism
itself with real modules and a real Click invocation, independent of which typer is installed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import ClassVar

import click
import pytest
from click.testing import CliRunner

from confiq.source._click import NO_ACTIVE_CONTEXT_MESSAGE_TEMPLATE
from confiq.source._click import ClickSource
from confiq.source._click import _context_from
from confiq.source._click import _current_command_context
from confiq.source._typer import TyperSource


if TYPE_CHECKING:
    from confiq.source._click import _CommandContextLike


_REAL_CLICK_MODULE = "click.globals"
_VENDORED_TYPER_CLICK_MODULE = "typer._click.globals"
_MISSING_MODULE = "confiq_no_such_vendored_click.globals"
_MODULE_WITHOUT_CURRENT_CONTEXT = "json"
_FALLBACK_MODULES = (_MISSING_MODULE, _REAL_CLICK_MODULE)
_ARBITRARY_FRAMEWORK = "Nonexistent"
_COMMAND_NAME = "cmd"
_OPTION_FLAG = "--db-port"
_OPTION_NAME = "db_port"
_OPTION_VALUE = "8080"


class _FallbackModuleSource(ClickSource):
    """A source whose first context-stack module is unavailable, mirroring typer<0.26's fallback."""

    _CONTEXT_STACK_MODULES: ClassVar[tuple[str, ...]] = _FALLBACK_MODULES


def test__context_from_with_missing_module_returns_none() -> None:
    assert _context_from(_MISSING_MODULE) is None


def test__context_from_with_module_lacking_get_current_context_returns_none() -> None:
    assert _context_from(_MODULE_WITHOUT_CURRENT_CONTEXT) is None


def test__context_from_with_no_active_invocation_returns_none() -> None:
    assert _context_from(_REAL_CLICK_MODULE) is None


def test__context_from_with_live_invocation_returns_the_active_context() -> None:
    captured: dict[str, _CommandContextLike | None] = {}

    @click.command(_COMMAND_NAME)
    @click.option(_OPTION_FLAG)
    def cmd(db_port: str) -> None:
        captured["context"] = _context_from(_REAL_CLICK_MODULE)

    result = CliRunner().invoke(cmd, [_OPTION_FLAG, _OPTION_VALUE])

    assert result.exit_code == 0, result.output
    context = captured["context"]
    assert context is not None
    assert context.params[_OPTION_NAME] == _OPTION_VALUE


def test__current_command_context_with_unavailable_first_module_falls_through() -> None:
    captured: dict[str, _CommandContextLike] = {}

    @click.command(_COMMAND_NAME)
    @click.option(_OPTION_FLAG)
    def cmd(db_port: str) -> None:
        captured["context"] = _current_command_context(ClickSource._FRAMEWORK, _FALLBACK_MODULES)

    result = CliRunner().invoke(cmd, [_OPTION_FLAG, _OPTION_VALUE])

    assert result.exit_code == 0, result.output
    assert captured["context"].params[_OPTION_NAME] == _OPTION_VALUE


def test__current_command_context_with_all_modules_exhausted_raises_branded_runtime_error() -> None:
    expected = NO_ACTIVE_CONTEXT_MESSAGE_TEMPLATE.format(framework=_ARBITRARY_FRAMEWORK)

    with pytest.raises(RuntimeError, match=re.escape(expected)):
        _current_command_context(_ARBITRARY_FRAMEWORK, _FALLBACK_MODULES)


def test_click_source_with_unavailable_first_module_still_captures_bindings() -> None:
    captured: dict[str, ClickSource] = {}

    @click.command(_COMMAND_NAME)
    @click.option(_OPTION_FLAG)
    def cmd(db_port: str) -> None:
        captured["source"] = _FallbackModuleSource()

    result = CliRunner().invoke(cmd, [_OPTION_FLAG, _OPTION_VALUE])

    assert result.exit_code == 0, result.output
    bindings = captured["source"].raw_bindings()
    assert [(binding.name, binding.value) for binding in bindings] == [(_OPTION_NAME, _OPTION_VALUE)]


def test_typer_source_prefers_the_vendored_context_stack_over_real_click() -> None:
    """The literal order IS the fix (ADR 0054): under typer>=0.26 only the vendored stack is live.

    Asserted literally rather than behaviourally on purpose — the private module path and its
    precedence are the contract, so a reorder or a "cleanup" of the private coupling must fail loudly.
    """
    assert TyperSource._CONTEXT_STACK_MODULES == (_VENDORED_TYPER_CLICK_MODULE, _REAL_CLICK_MODULE)
