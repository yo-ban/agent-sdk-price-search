"""Port for mutating launcher-backed runs."""

from __future__ import annotations

from typing import Protocol

from price_search_web_api.contracts.run_snapshot import RunSnapshot


class RunControlPort(Protocol):
    """Abstraction for canceling or hiding stored runs."""

    def cancel_run(self, run_id: str) -> RunSnapshot | None:
        """Request cancellation for an in-flight run and return the latest snapshot."""
        ...

    def delete_run(self, run_id: str) -> bool:
        """Soft-delete one completed run from the visible history."""
        ...
