"""CLI module execution tests."""

from __future__ import annotations

import subprocess
import sys


def test_price_search_cli_module_executes_help_output() -> None:
    """`python -m price_search.handler.cli --help` should print CLI usage."""
    completed = subprocess.run(
        [sys.executable, "-m", "price_search.handler.cli", "sample", "--help"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert "price-search" in completed.stdout


def test_searxng_search_cli_module_executes_help_output() -> None:
    """`python -m searxng_search_cli.handler.cli --help` should print CLI usage."""
    completed = subprocess.run(
        [sys.executable, "-m", "searxng_search_cli.handler.cli", "sample", "--help"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert "searxng-search" in completed.stdout
