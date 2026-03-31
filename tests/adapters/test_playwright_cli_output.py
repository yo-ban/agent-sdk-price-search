"""Tests for playwright-cli output shaping."""

from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

_FILTER_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "workspace_assets"
    / "playwright"
    / "filter_playwright_cli_output.py"
)


def test_filter_playwright_cli_output_removes_debug_only_sections() -> None:
    """通常モードでは code と events を出さず、Page 内の console 行も落とす。"""
    raw_output = dedent(
        """
        ### Result
        "49,846"
        ### Ran Playwright code
        ```js
        await page.evaluate('document.title');
        ```
        ### Page
        - Page URL: https://example.com/
        - Page Title: Example Domain
        - Console: 1 errors, 8 warnings
        ### Events
        - New console entries: .playwright-cli/console.log#L1-L8
        """
    ).lstrip()

    filtered_output = _run_filter_script(raw_output=raw_output)

    assert filtered_output == dedent(
        """
        ### Result
        "49,846"
        ### Page
        - Page URL: https://example.com/
        - Page Title: Example Domain
        """
    ).lstrip()


def test_filter_playwright_cli_output_keeps_browser_and_snapshot_sections() -> None:
    """通常モードでも行動に必要な browser と snapshot 情報は残す。"""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        snapshot_path = temp_path / ".playwright-cli" / "page.yml"
        snapshot_path.parent.mkdir(parents=True)
        snapshot_path.write_text("snapshot", encoding="utf-8")
        raw_output = dedent(
            """
            ### Browser `default` opened with pid 715.
            - default:
              - browser-type: chrome
              - user-data-dir: <in-memory>
              - headed: true
            ---
            ### Ran Playwright code
            ```js
            await page.goto('https://example.com');
            ```
            ### Page
            - Page URL: https://example.com/
            - Page Title: Example Domain
            ### Snapshot
            - [Snapshot](.playwright-cli/page.yml)
            """
        ).lstrip()

        filtered_output = _run_filter_script(raw_output=raw_output, cwd=temp_path)

        assert filtered_output == dedent(
            f"""
            ### Browser `default` opened with pid 715.
            - default:
              - browser-type: chrome
              - user-data-dir: <in-memory>
              - headed: true
            ---
            ### Page
            - Page URL: https://example.com/
            - Page Title: Example Domain
            ### Snapshot
            - [Snapshot]({snapshot_path.resolve()})
            """
        ).lstrip()


def test_filter_playwright_cli_output_resolves_bare_snapshot_filename_from_hidden_dir() -> None:
    """Bare snapshot filenames should also resolve through .playwright-cli when present."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        snapshot_path = temp_path / ".playwright-cli" / "amazon_page.yaml"
        snapshot_path.parent.mkdir(parents=True)
        snapshot_path.write_text("snapshot", encoding="utf-8")
        raw_output = dedent(
            """
            ### Page
            - Page URL: https://example.com/
            - Page Title: Example Domain
            ### Snapshot
            - [Snapshot](amazon_page.yaml)
            """
        ).lstrip()

        filtered_output = _run_filter_script(raw_output=raw_output, cwd=temp_path)

        assert filtered_output == dedent(
            f"""
            ### Page
            - Page URL: https://example.com/
            - Page Title: Example Domain
            ### Snapshot
            - [Snapshot]({snapshot_path.resolve()})
            """
        ).lstrip()


def _run_filter_script(*, raw_output: str, cwd: Path | None = None) -> str:
    """Execute the filter script through Python and return stdout."""
    completed_process = subprocess.run(
        ["python3", str(_FILTER_SCRIPT)],
        check=True,
        input=raw_output,
        text=True,
        capture_output=True,
        cwd=cwd,
    )
    return completed_process.stdout
