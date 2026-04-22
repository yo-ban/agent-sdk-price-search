"""Filesystem adapter: launcher 用の隔離 workspace を準備する。"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

from price_search_launcher.contracts.prepared_workspace import PreparedWorkspace

_RUNTIME_ASSET_MAPPINGS = (
    (Path("workspace_assets/bin/claude-code-wrapper"), Path("bin/claude-code-wrapper")),
    (Path("workspace_assets/bin/playwright-cli"), Path("bin/playwright-cli")),
    (Path("workspace_assets/bin/web-search"), Path("bin/web-search")),
    (Path("workspace_assets/bin/snapshot-inspect"), Path("bin/snapshot-inspect")),
    (Path("workspace_assets/playwright/cli.config.json"), Path("playwright/cli.config.json")),
    (
        Path("workspace_assets/playwright/filter_playwright_cli_output.py"),
        Path("playwright/filter_playwright_cli_output.py"),
    ),
    (Path("config/price_search.toml"), Path("config/price_search.toml")),
)
_OPTIONAL_ASSET_MAPPINGS = (
    (Path("config/price_search.local.toml"), Path("config/price_search.local.toml")),
)


class IsolatedWorkspaceProvisioner:
    """repo から必要最小限の runtime asset だけを workspace へ展開する。"""

    def __init__(self, *, repository_root: Path, python_executable: str) -> None:
        """asset source と wrapper 用 Python 実行ファイルを保持する。"""
        self._repository_root = repository_root

    def prepare_workspace(self, *, launch_directory: Path) -> PreparedWorkspace:
        """launch directory とは分離された temp workspace を準備する。"""
        workspace_root = Path(tempfile.mkdtemp(prefix="price-search-workspace-")).resolve()
        self._copy_runtime_assets(workspace_root=workspace_root)
        self._create_output_links(
            workspace_root=workspace_root,
            launch_directory=launch_directory.resolve(),
        )
        return PreparedWorkspace(
            workspace_root=workspace_root,
            config_file=workspace_root / "config" / "price_search.toml",
            local_config_file=_optional_workspace_file(
                workspace_root / "config" / "price_search.local.toml"
            ),
        )

    def cleanup_workspace(self, *, workspace_root: Path) -> None:
        """temp workspace を再帰削除する。"""
        shutil.rmtree(workspace_root, ignore_errors=True)

    def _copy_runtime_assets(self, *, workspace_root: Path) -> None:
        """runtime asset allowlist を workspace へ複写する。"""
        for source_relative_path, destination_relative_path in _RUNTIME_ASSET_MAPPINGS:
            source_path = self._repository_root / source_relative_path
            destination_path = workspace_root / destination_relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            _make_executable_if_needed(path=destination_path)

        for source_relative_path, destination_relative_path in _OPTIONAL_ASSET_MAPPINGS:
            source_path = self._repository_root / source_relative_path
            if not source_path.exists():
                continue
            destination_path = workspace_root / destination_relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)

    def _create_output_links(
        self,
        *,
        workspace_root: Path,
        launch_directory: Path,
    ) -> None:
        """永続成果物だけを launch directory 側へ逃がす。"""
        output_directories = {
            "logs": launch_directory / "logs",
            "out": launch_directory / "out",
        }
        for link_name, target_directory in output_directories.items():
            target_directory.mkdir(parents=True, exist_ok=True)
            link_path = workspace_root / link_name
            os.symlink(target_directory, link_path, target_is_directory=True)
        (workspace_root / ".playwright-cli").mkdir(parents=True, exist_ok=True)


def discover_repository_root() -> Path:
    """この checkout の repository root を検出する。"""
    current_path = Path(__file__).resolve()
    for candidate in current_path.parents:
        if not (candidate / "pyproject.toml").exists():
            continue
        if _has_workspace_asset_markers(repository_root=candidate):
            return candidate
    raise RuntimeError("Could not locate the price-search repository root.")


def _has_workspace_asset_markers(*, repository_root: Path) -> bool:
    """launcher が temp workspace へ複写する asset 一式の存在を確認する。"""
    return all(
        (repository_root / source_relative_path).exists()
        for source_relative_path, _destination_relative_path in _RUNTIME_ASSET_MAPPINGS
    )


def _make_executable_if_needed(*, path: Path) -> None:
    """実行可能 script だけ owner execute bit を付与する。"""
    if path.suffix or path.name not in {
        "claude-code-wrapper",
        "playwright-cli",
        "web-search",
        "snapshot-inspect",
    }:
        return
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR)


def _optional_workspace_file(path: Path) -> Path | None:
    """存在する workspace file だけを返す。"""
    if path.exists():
        return path
    return None
