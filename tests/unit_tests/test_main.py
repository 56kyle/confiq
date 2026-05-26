"""Test cases for the __main__ module."""

import pytest
from typer.testing import CliRunner

from confiq import __main__


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


def test_main_succeeds(runner: CliRunner) -> None:
    """Invoking --help exits 0 and shows usage text."""
    result = runner.invoke(__main__.app, ["--help"])
    assert result.exit_code == 0
    assert "show" in result.output or "confiq" in result.output
