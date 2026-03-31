"""Command-line handler for the Playwright snapshot inspection tool."""

from __future__ import annotations

import argparse
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


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for snapshot inspection subcommands."""
    parser = argparse.ArgumentParser(
        prog="snapshot-inspect",
        description="Playwright snapshot YAML を要約・検索します。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser(
        "summary",
        help="snapshot 全体の要約を表示する。",
    )
    summary_parser.add_argument("snapshot_path", type=Path, help="対象 snapshot file")

    find_parser = subparsers.add_parser(
        "find",
        help="text と role で snapshot 要素を検索する。",
    )
    find_parser.add_argument("snapshot_path", type=Path, help="対象 snapshot file")
    find_parser.add_argument(
        "--text",
        action="append",
        required=True,
        help="name/text/url に対する検索語。複数指定した場合はいずれか一致。",
    )
    find_parser.add_argument("--role", default=None, help="role での絞り込み")
    find_parser.add_argument("--limit", type=int, default=8, help="返す件数の上限")

    controls_parser = subparsers.add_parser(
        "controls",
        help="click/fill 候補になりやすい操作要素を列挙する。",
    )
    controls_parser.add_argument("snapshot_path", type=Path, help="対象 snapshot file")
    controls_parser.add_argument("--role", default=None, help="role での絞り込み")
    controls_parser.add_argument("--limit", type=int, default=12, help="返す件数の上限")

    return parser


def run_cli() -> int:
    """Dispatch one snapshot inspection subcommand and print the result."""
    args = build_parser().parse_args()
    if args.command == "summary":
        response = SummarizeSnapshotUseCase().execute(
            SnapshotFileRequest(snapshot_path=args.snapshot_path)
        )
        print(f"Snapshot: {response.snapshot_path}")
        print(f"Nodes: {response.total_nodes}")
        if response.control_counts:
            print("Controls:")
            for role, count in response.control_counts:
                print(f"- {role}: {count}")
        else:
            print("Controls: none")
        if response.suggested_controls:
            print("Suggested controls:")
            _print_elements(response.suggested_controls)
        return 0

    if args.command == "find":
        response = FindSnapshotElementsUseCase().execute(
            FindSnapshotRequest(
                snapshot_path=args.snapshot_path,
                texts=tuple(args.text),
                role=args.role,
                limit=args.limit,
            )
        )
        print(f"Snapshot: {response.snapshot_path}")
        _print_elements(response.elements)
        return 0

    response = ListSnapshotControlsUseCase().execute(
        ListControlsRequest(
            snapshot_path=args.snapshot_path,
            role=args.role,
            limit=args.limit,
        )
    )
    print(f"Snapshot: {response.snapshot_path}")
    _print_elements(response.elements)
    return 0


def main() -> None:
    """Run the synchronous snapshot inspection CLI entry point."""
    raise SystemExit(run_cli())


def _print_elements(elements) -> None:
    """Print one numbered element list for human and LLM consumption."""
    if not elements:
        print("(no matches)")
        return
    for index, element in enumerate(elements, start=1):
        print(f"{index}. {element.label}")
        if element.url:
            print(f"   url={element.url}")


if __name__ == "__main__":
    main()
