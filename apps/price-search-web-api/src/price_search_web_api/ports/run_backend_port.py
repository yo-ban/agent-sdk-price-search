"""Port for launcher-backed run management in the Web API infrastructure layer."""

from __future__ import annotations

from typing import Protocol

from price_search_web_api.contracts.create_run_request import CreateRunRequest
from price_search_web_api.contracts.run_snapshot import RunSnapshot


class RunBackendPort(Protocol):
    """Abstraction for creating, reading, and mutating launcher-backed runs."""

    def start_run(self, request: CreateRunRequest) -> RunSnapshot:
        """Start a new run and return its initial snapshot."""
        ...

    def get_run(self, run_id: str) -> RunSnapshot | None:
        """Return the current snapshot for a single run."""
        ...

    def list_runs(self) -> tuple[RunSnapshot, ...]:
        """Return the available run snapshots."""
        ...

    def cancel_run(self, run_id: str) -> RunSnapshot | None:
        """Request cancellation for an in-flight run and return the latest snapshot."""
        ...

    def delete_run(self, run_id: str) -> bool:
        """Soft-delete one completed run from the visible history."""
        ...
