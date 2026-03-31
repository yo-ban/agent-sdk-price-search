"""Use case for listing available run snapshots."""

from __future__ import annotations

from price_search_web_api.contracts.run_snapshot import RunSnapshot
from price_search_web_api.ports.run_query_port import RunQueryPort


class ListRunsUseCase:
    """Application service for reading run history."""

    def __init__(self, run_query: RunQueryPort) -> None:
        """Store the run query dependency."""
        self._run_query = run_query

    def execute(self) -> tuple[RunSnapshot, ...]:
        """List the available runs."""
        return self._run_query.list_runs()

