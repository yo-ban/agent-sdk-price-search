"""Domain layer: parse Playwright snapshot YAML-like text into typed nodes."""

from __future__ import annotations

import re

from snapshot_inspect_cli.domain.models import SnapshotDocument, SnapshotNode

_NODE_LINE_PATTERN = re.compile(r"^(?P<indent>\s*)-\s+(?P<body>.+?)\s*$")
_URL_LINE_PATTERN = re.compile(r"^(?P<indent>\s*)-\s+/url:\s+(?P<url>.+?)\s*$")
_ROLE_PATTERN = re.compile(r"^(?P<role>[A-Za-z][A-Za-z0-9_-]*)(?P<rest>.*)$")
_NAME_PATTERN = re.compile(r'"(?P<name>[^"]+)"')
_ATTRIBUTE_PATTERN = re.compile(r"\[(?P<attribute>[^\]]+)\]")
_REF_PATTERN = re.compile(r"\[ref=(?P<ref>[^\]]+)\]")


def parse_snapshot_text(text: str) -> SnapshotDocument:
    """Parse snapshot text into a flat document of nodes."""
    nodes: list[SnapshotNode] = []
    active_nodes_by_indent: dict[int, int] = {}

    for raw_line in text.splitlines():
        url_match = _URL_LINE_PATTERN.match(raw_line)
        if url_match is not None:
            _attach_url_to_parent(
                nodes=nodes,
                active_nodes_by_indent=active_nodes_by_indent,
                indent=len(url_match.group("indent")),
                url=url_match.group("url").strip(),
            )
            continue

        node_match = _NODE_LINE_PATTERN.match(raw_line)
        if node_match is None:
            continue

        parsed_node = _parse_node_line(
            body=node_match.group("body"),
            depth=len(node_match.group("indent")) // 2,
            raw_line=raw_line.rstrip(),
        )
        if parsed_node is None:
            continue

        nodes.append(parsed_node)
        indent = len(node_match.group("indent"))
        active_nodes_by_indent[indent] = len(nodes) - 1
        for stale_indent in tuple(active_nodes_by_indent):
            if stale_indent > indent:
                del active_nodes_by_indent[stale_indent]

    return SnapshotDocument(nodes=tuple(nodes))


def _attach_url_to_parent(
    *,
    nodes: list[SnapshotNode],
    active_nodes_by_indent: dict[int, int],
    indent: int,
    url: str,
) -> None:
    """Attach one `/url:` property to the nearest parent node."""
    parent_index: int | None = None
    for candidate_indent in sorted(active_nodes_by_indent, reverse=True):
        if candidate_indent < indent:
            parent_index = active_nodes_by_indent[candidate_indent]
            break
    if parent_index is None:
        return
    parent = nodes[parent_index]
    nodes[parent_index] = SnapshotNode(
        role=parent.role,
        depth=parent.depth,
        ref=parent.ref,
        name=parent.name,
        inline_text=parent.inline_text,
        url=url,
        attributes=parent.attributes,
        raw_line=parent.raw_line,
    )


def _parse_node_line(*, body: str, depth: int, raw_line: str) -> SnapshotNode | None:
    """Parse one node-like list item into a typed snapshot node."""
    normalized_body = body.rstrip()
    inline_text: str | None = None
    if normalized_body.endswith(":"):
        normalized_body = normalized_body[:-1].rstrip()
    elif ": " in normalized_body:
        prefix, suffix = normalized_body.split(": ", 1)
        normalized_body = prefix.strip()
        inline_text = suffix.strip() or None

    role_match = _ROLE_PATTERN.match(normalized_body)
    if role_match is None:
        return None

    rest = role_match.group("rest")
    name_match = _NAME_PATTERN.search(rest)
    ref_match = _REF_PATTERN.search(rest)
    attributes = tuple(
        attribute
        for attribute in _ATTRIBUTE_PATTERN.findall(rest)
        if attribute and not attribute.startswith("ref=")
    )
    return SnapshotNode(
        role=role_match.group("role"),
        depth=depth,
        ref=ref_match.group("ref") if ref_match is not None else None,
        name=name_match.group("name") if name_match is not None else None,
        inline_text=inline_text,
        url=None,
        attributes=attributes,
        raw_line=raw_line,
    )
