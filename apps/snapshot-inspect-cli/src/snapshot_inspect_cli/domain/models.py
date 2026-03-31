"""Domain layer: typed snapshot nodes and inspection summaries."""

from __future__ import annotations

from dataclasses import dataclass

ACTIONABLE_ROLES = frozenset(
    {
        "button",
        "checkbox",
        "combobox",
        "link",
        "menuitem",
        "option",
        "radio",
        "searchbox",
        "switch",
        "tab",
        "textbox",
    }
)


@dataclass(frozen=True, slots=True)
class SnapshotNode:
    """One parsed node from the snapshot accessibility tree."""

    role: str
    depth: int
    ref: str | None
    name: str | None
    inline_text: str | None
    url: str | None
    attributes: tuple[str, ...]
    raw_line: str


@dataclass(frozen=True, slots=True)
class SnapshotDocument:
    """Flat representation of one snapshot document."""

    nodes: tuple[SnapshotNode, ...]


@dataclass(frozen=True, slots=True)
class RoleCount:
    """Count of nodes for one role."""

    role: str
    count: int
