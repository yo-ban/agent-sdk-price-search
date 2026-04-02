"""Support script: filter playwright-cli stdout for normal LLM-facing runs."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from PIL import Image as PillowImage
from PIL import UnidentifiedImageError

_DEBUG_ONLY_HEADERS = frozenset(
    {
        "### Events",
        "### Ran Playwright code",
    }
)
_PAGE_DEBUG_ONLY_PREFIXES = ("- Console:",)
_SNAPSHOT_LINK_PATTERN = re.compile(r"(\[Snapshot\]\()([^)]+)(\))")
_SCREENSHOT_LINK_PATTERN = re.compile(r"(\[Screenshot[^]]*\]\()([^)]+)(\))")


def filter_playwright_cli_output(*, raw_output: str) -> str:
    """Drop debug-only sections from playwright-cli stdout."""
    filtered_lines: list[str] = []
    current_header: str | None = None
    skip_current_section = False

    for line in raw_output.splitlines(keepends=True):
        stripped_line = line.rstrip("\n")
        if stripped_line.startswith("### "):
            current_header = stripped_line
            skip_current_section = current_header in _DEBUG_ONLY_HEADERS
            if skip_current_section:
                continue
            filtered_lines.append(line)
            continue

        if skip_current_section:
            continue

        if current_header == "### Page" and stripped_line.startswith(
            _PAGE_DEBUG_ONLY_PREFIXES
        ):
            continue

        if current_header == "### Snapshot":
            line = _rewrite_snapshot_link(line)
        elif current_header == "### Result":
            line = _rewrite_screenshot_link(line)

        filtered_lines.append(line)

    return "".join(filtered_lines)


def main(argv: list[str] | None = None) -> int:
    """Read captured stdout and print the filtered representation."""
    parser = argparse.ArgumentParser(
        description="Filter debug-only sections from playwright-cli stdout."
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        help="Path to captured playwright-cli stdout. Reads stdin when omitted.",
    )
    args = parser.parse_args(argv)

    raw_output = _read_raw_output(output_file=args.output_file)
    sys.stdout.write(filter_playwright_cli_output(raw_output=raw_output))
    return 0


def _read_raw_output(*, output_file: str | None) -> str:
    """Load raw stdout from stdin or a file."""
    if output_file is None:
        return sys.stdin.read()
    return Path(output_file).read_text(encoding="utf-8")


def _rewrite_snapshot_link(line: str) -> str:
    """Rewrite snapshot links to absolute host paths when the file can be resolved."""
    match = _SNAPSHOT_LINK_PATTERN.search(line)
    if match is None:
        return line

    resolved_path = _resolve_snapshot_path(match.group(2))
    if resolved_path is None:
        return line

    return line[: match.start(2)] + str(resolved_path) + line[match.end(2) :]


def _rewrite_screenshot_link(line: str) -> str:
    """Rewrite screenshot links and append image dimensions when available."""
    match = _SCREENSHOT_LINK_PATTERN.search(line)
    if match is None:
        return line

    resolved_path = _normalize_artifact_path(match.group(2))

    rewritten_line = (
        line[: match.start(2)] + str(resolved_path) + line[match.end(2) :]
    )
    image_size = _read_image_size(resolved_path)
    if image_size is None:
        return rewritten_line

    width, height = image_size
    stripped_line = rewritten_line.rstrip("\n")
    line_ending = "\n" if rewritten_line.endswith("\n") else ""
    return f"{stripped_line} ({width}x{height}){line_ending}"


def _resolve_snapshot_path(raw_path: str) -> Path | None:
    """Resolve one snapshot path relative to the current workspace."""
    resolved_path = _resolve_artifact_path(raw_path)
    if resolved_path is None:
        return None

    if resolved_path.suffix.lower() not in {".yml", ".yaml"}:
        return None
    return resolved_path


def _resolve_artifact_path(raw_path: str) -> Path | None:
    """Resolve one artifact path relative to the current workspace."""
    artifact_path = _normalize_artifact_path(raw_path)
    if artifact_path.exists():
        return artifact_path

    workspace_root = Path(
        os.environ.get("PRICE_SEARCH_WORKSPACE_ROOT") or Path.cwd()
    ).resolve()
    hidden_dir_candidate = (workspace_root / ".playwright-cli" / artifact_path.name).resolve()
    if hidden_dir_candidate.exists():
        return hidden_dir_candidate
    return None


def _normalize_artifact_path(raw_path: str) -> Path:
    """Normalize one artifact path to an absolute host path."""
    artifact_path = Path(raw_path)
    if artifact_path.is_absolute():
        return artifact_path.resolve()

    workspace_root = Path(
        os.environ.get("PRICE_SEARCH_WORKSPACE_ROOT") or Path.cwd()
    ).resolve()
    return (workspace_root / artifact_path).resolve()


def _read_image_size(image_path: Path) -> tuple[int, int] | None:
    """Read one image's dimensions when the target is a supported image file."""
    try:
        with PillowImage.open(image_path) as image:
            return image.size
    except (FileNotFoundError, UnidentifiedImageError, OSError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
