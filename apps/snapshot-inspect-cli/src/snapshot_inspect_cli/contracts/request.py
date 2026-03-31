"""Input DTOs for snapshot inspection use cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SnapshotFileRequest:
    """Request to inspect one snapshot file."""

    snapshot_path: Path


@dataclass(frozen=True, slots=True)
class FindSnapshotRequest:
    """Request to search matching nodes from one snapshot file."""

    snapshot_path: Path
    texts: tuple[str, ...]
    role: str | None
    limit: int


@dataclass(frozen=True, slots=True)
class ListControlsRequest:
    """Request to list actionable controls from one snapshot file."""

    snapshot_path: Path
    role: str | None
    limit: int
