"""Use case for fetching a single run snapshot."""

from __future__ import annotations

from price_search_web_api.contracts.run_snapshot import RunSnapshot
from price_search_web_api.ports.run_query_port import RunQueryPort


class GetRunUseCase:
    """Application service for reading a single run."""

    def __init__(self, run_query: RunQueryPort) -> None:
        """Store the run query dependency."""
        self._run_query = run_query

    def execute(self, run_id: str) -> RunSnapshot | None:
        """Fetch a snapshot for one run."""
        return self._run_query.get_run(run_id)

