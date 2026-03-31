"""Observable-behavior tests for the snapshot inspection CLI use cases."""

from __future__ import annotations

from pathlib import Path

from snapshot_inspect_cli.application.inspect_snapshot import (
    FindSnapshotElementsUseCase,
    ListSnapshotControlsUseCase,
    SummarizeSnapshotUseCase,
)
from snapshot_inspect_cli.contracts.request import (
    FindSnapshotRequest,
    ListControlsRequest,
    SnapshotFileRequest,
)

_SNAPSHOT_TEXT = """
- generic [ref=e2]:
  - heading "Shop" [level=1] [ref=e3]
  - textbox "Search products" [ref=e4]
  - button "Add to cart" [ref=e5]
  - link "Product details" [ref=e6]:
    - /url: https://example.com/product
  - checkbox "In stock only" [checked] [ref=e7]
  - paragraph [ref=e8]: Ships tomorrow
""".strip()


def test_summarize_snapshot_reports_actionable_role_counts(tmp_path: Path) -> None:
    """Summary should count actionable roles and expose suggested controls."""
    snapshot_path = _write_snapshot(tmp_path / "summary.yaml")
    expected_roles = ("button", "checkbox", "link", "textbox")

    response = SummarizeSnapshotUseCase().execute(
        SnapshotFileRequest(snapshot_path=snapshot_path)
    )

    returned_roles = tuple(role for role, _count in response.control_counts)
    assert returned_roles == expected_roles
    assert response.total_nodes == len(_SNAPSHOT_TEXT.splitlines()) - 1
    assert all(element.role in expected_roles for element in response.suggested_controls)


def test_find_snapshot_returns_nodes_matching_any_requested_text(tmp_path: Path) -> None:
    """Find should match any requested text against names and attached URLs."""
    snapshot_path = _write_snapshot(tmp_path / "find.yaml")

    response = FindSnapshotElementsUseCase().execute(
        FindSnapshotRequest(
            snapshot_path=snapshot_path,
            texts=("cart", "example.com"),
            role=None,
            limit=5,
        )
    )

    assert tuple(element.ref for element in response.elements) == ("e5", "e6")
    assert response.elements[1].url == "https://example.com/product"


def test_find_snapshot_honors_role_filter(tmp_path: Path) -> None:
    """Find should narrow matches to the requested role."""
    snapshot_path = _write_snapshot(tmp_path / "role-filter.yaml")
    requested_role = "button"

    response = FindSnapshotElementsUseCase().execute(
        FindSnapshotRequest(
            snapshot_path=snapshot_path,
            texts=("product",),
            role=requested_role,
            limit=5,
        )
    )

    assert response.elements == ()


def test_list_controls_returns_only_requested_actionable_role(tmp_path: Path) -> None:
    """Controls should return actionable nodes and allow role narrowing."""
    snapshot_path = _write_snapshot(tmp_path / "controls.yaml")
    requested_role = "checkbox"

    response = ListSnapshotControlsUseCase().execute(
        ListControlsRequest(
            snapshot_path=snapshot_path,
            role=requested_role,
            limit=5,
        )
    )

    assert tuple(element.role for element in response.elements) == (requested_role,)


def _write_snapshot(path: Path) -> Path:
    """Create one snapshot fixture file for the current test."""
    path.write_text(_SNAPSHOT_TEXT, encoding="utf-8")
    return path
