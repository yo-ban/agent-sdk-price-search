"""Port for reading launcher-backed run snapshots."""

from __future__ import annotations

from typing import Protocol

from price_search_web_api.contracts.run_snapshot import RunSnapshot


class RunQueryPort(Protocol):
    """Abstraction for reading stored run snapshots."""

    def get_run(self, run_id: str) -> RunSnapshot | None:
        """Return the current snapshot for a single run."""
        ...

    def list_runs(self) -> tuple[RunSnapshot, ...]:
        """Return the available run snapshots."""
        ...
