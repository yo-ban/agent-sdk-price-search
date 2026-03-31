"""Output DTOs for snapshot inspection use cases."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SnapshotElementResponse:
    """One snapshot element formatted for CLI output."""

    role: str
    ref: str | None
    label: str
    url: str | None
    depth: int


@dataclass(frozen=True, slots=True)
class SnapshotSummaryResponse:
    """Summary of one snapshot file."""

    snapshot_path: str
    total_nodes: int
    control_counts: tuple[tuple[str, int], ...]
    suggested_controls: tuple[SnapshotElementResponse, ...]


@dataclass(frozen=True, slots=True)
class SnapshotElementsResponse:
    """Collection of snapshot elements returned by one query."""

    snapshot_path: str
    elements: tuple[SnapshotElementResponse, ...]
