"""Handler tests for the isolated launcher CLI."""

from __future__ import annotations

import sys
from pathlib import Path

from price_search_launcher.contracts.isolated_price_search_request import (
    IsolatedPriceSearchRequest,
)
from price_search_launcher.handler import launcher


class FakeLaunchUseCase:
    """Capture the launcher request and return a deterministic exit code."""

    def __init__(self, exit_code: int) -> None:
        """Store one deterministic exit code."""
        self.exit_code = exit_code
        self.received_request: IsolatedPriceSearchRequest | None = None

    def execute(self, request: IsolatedPriceSearchRequest) -> int:
        """Record the request and return the configured exit code."""
        self.received_request = request
        return self.exit_code


def test_run_cli_forwards_price_search_args_into_isolated_request(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Launcher should wrap the product name and forwarded args into one request."""
    fake_use_case = FakeLaunchUseCase(exit_code=23)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        launcher,
        "build_use_case",
        lambda: fake_use_case,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "price-search-run",
            "全自動コーヒーメーカー ABC-1234",
            "--",
            "--json",
            "--max-offers",
            "2",
        ],
    )

    exit_code = launcher.run_cli()

    assert exit_code == fake_use_case.exit_code
    assert fake_use_case.received_request == IsolatedPriceSearchRequest(
        cli_args=("全自動コーヒーメーカー ABC-1234", "--json", "--max-offers", "2"),
        launch_directory=tmp_path,
    )
