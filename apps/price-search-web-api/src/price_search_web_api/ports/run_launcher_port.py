"""Port for starting launcher-backed runs."""

from __future__ import annotations

from typing import Protocol

from price_search_web_api.contracts.create_run_request import CreateRunRequest
from price_search_web_api.contracts.run_snapshot import RunSnapshot


class RunLauncherPort(Protocol):
    """Abstraction for creating a new run."""

    def start_run(self, request: CreateRunRequest) -> RunSnapshot:
        """Start a new run and return its initial snapshot."""
        ...
