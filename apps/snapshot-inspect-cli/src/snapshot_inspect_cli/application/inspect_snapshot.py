"""Application layer: summarize and search parsed snapshot documents."""

from __future__ import annotations

from collections import Counter

from snapshot_inspect_cli.contracts.request import (
    FindSnapshotRequest,
    ListControlsRequest,
    SnapshotFileRequest,
)
from snapshot_inspect_cli.contracts.response import (
    SnapshotElementResponse,
    SnapshotElementsResponse,
    SnapshotSummaryResponse,
)
from snapshot_inspect_cli.domain.models import ACTIONABLE_ROLES, SnapshotDocument, SnapshotNode
from snapshot_inspect_cli.domain.snapshot_parser import parse_snapshot_text


class SummarizeSnapshotUseCase:
    """Summarize one snapshot file into compact control-focused output."""

    def execute(self, request: SnapshotFileRequest) -> SnapshotSummaryResponse:
        """Return a summary with role counts and likely next controls."""
        document = _load_document(request.snapshot_path)
        control_counts = _count_controls(document)
        suggested_controls = tuple(
            _to_element_response(node) for node in _select_suggested_controls(document, limit=8)
        )
        return SnapshotSummaryResponse(
            snapshot_path=str(request.snapshot_path),
            total_nodes=len(document.nodes),
            control_counts=control_counts,
            suggested_controls=suggested_controls,
        )


class FindSnapshotElementsUseCase:
    """Search one snapshot file for nodes matching text and optional role."""

    def execute(self, request: FindSnapshotRequest) -> SnapshotElementsResponse:
        """Return matching nodes in snapshot order."""
        document = _load_document(request.snapshot_path)
        matches = tuple(
            _to_element_response(node)
            for node in _find_nodes(
                document=document,
                queries=request.texts,
                role=request.role,
                limit=request.limit,
            )
        )
        return SnapshotElementsResponse(
            snapshot_path=str(request.snapshot_path),
            elements=matches,
        )


class ListSnapshotControlsUseCase:
    """List actionable controls from one snapshot file."""

    def execute(self, request: ListControlsRequest) -> SnapshotElementsResponse:
        """Return actionable controls, optionally narrowed to one role."""
        document = _load_document(request.snapshot_path)
        controls = tuple(
            _to_element_response(node)
            for node in _list_controls(
                document=document,
                role=request.role,
                limit=request.limit,
            )
        )
        return SnapshotElementsResponse(
            snapshot_path=str(request.snapshot_path),
            elements=controls,
        )


def _load_document(snapshot_path) -> SnapshotDocument:
    """Read one snapshot file and parse it into a domain document."""
    return parse_snapshot_text(snapshot_path.read_text(encoding="utf-8"))


def _count_controls(document: SnapshotDocument) -> tuple[tuple[str, int], ...]:
    """Count actionable controls by role."""
    role_counter = Counter(
        node.role for node in document.nodes if node.role in ACTIONABLE_ROLES
    )
    return tuple(
        (role, role_counter[role])
        for role in sorted(role_counter)
    )


def _select_suggested_controls(
    document: SnapshotDocument,
    *,
    limit: int,
) -> tuple[SnapshotNode, ...]:
    """Choose the first actionable controls, or named nodes when none exist."""
    actionable_nodes = tuple(node for node in document.nodes if node.role in ACTIONABLE_ROLES)
    if actionable_nodes:
        return actionable_nodes[:limit]
    named_nodes = tuple(node for node in document.nodes if node.name or node.inline_text)
    return named_nodes[:limit]


def _find_nodes(
    *,
    document: SnapshotDocument,
    queries: tuple[str, ...],
    role: str | None,
    limit: int,
) -> tuple[SnapshotNode, ...]:
    """Return nodes whose label or URL contains any requested query."""
    normalized_queries = tuple(query.strip().lower() for query in queries if query.strip())
    normalized_role = role.strip().lower() if role is not None else None
    matches: list[SnapshotNode] = []
    for node in document.nodes:
        if normalized_role is not None and node.role.lower() != normalized_role:
            continue
        haystack = " ".join(
            part.lower()
            for part in (node.name, node.inline_text, node.url, node.raw_line)
            if part
        )
        if any(query in haystack for query in normalized_queries):
            matches.append(node)
        if len(matches) >= limit:
            break
    return tuple(matches)


def _list_controls(
    *,
    document: SnapshotDocument,
    role: str | None,
    limit: int,
) -> tuple[SnapshotNode, ...]:
    """Return actionable controls in snapshot order."""
    normalized_role = role.strip().lower() if role is not None else None
    controls: list[SnapshotNode] = []
    for node in document.nodes:
        if node.role not in ACTIONABLE_ROLES:
            continue
        if normalized_role is not None and node.role.lower() != normalized_role:
            continue
        controls.append(node)
        if len(controls) >= limit:
            break
    return tuple(controls)


def _to_element_response(node: SnapshotNode) -> SnapshotElementResponse:
    """Convert one domain node into a CLI-facing element summary."""
    label_parts = [node.role]
    if node.ref is not None:
        label_parts.append(f"ref={node.ref}")
    if node.name:
        label_parts.append(f'name="{node.name}"')
    elif node.inline_text:
        label_parts.append(f'text="{node.inline_text}"')
    elif node.attributes:
        label_parts.append(f"attrs=[{', '.join(node.attributes)}]")
    return SnapshotElementResponse(
        role=node.role,
        ref=node.ref,
        label=" ".join(label_parts),
        url=node.url,
        depth=node.depth,
    )
