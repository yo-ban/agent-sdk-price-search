"""Adapter tests for isolated workspace provisioning."""

from __future__ import annotations

import os
from pathlib import Path

from price_search_launcher.adapters.filesystem.isolated_workspace import (
    IsolatedWorkspaceProvisioner,
    discover_repository_root,
)


def test_prepare_workspace_copies_runtime_assets_and_externalizes_outputs(
    tmp_path: Path,
) -> None:
    """Prepared workspaces should externalize durable outputs and keep browser artifacts local."""
    provisioner = IsolatedWorkspaceProvisioner(
        repository_root=discover_repository_root(),
        python_executable="/usr/bin/python3",
    )

    prepared_workspace = provisioner.prepare_workspace(launch_directory=tmp_path)

    assert (prepared_workspace.workspace_root / "config/price_search.toml").exists()
    assert (prepared_workspace.workspace_root / "playwright/cli.config.json").exists()
    assert (prepared_workspace.workspace_root / "bin/claude-code-wrapper").exists()
    assert (prepared_workspace.workspace_root / "bin/playwright-cli").exists()
    assert (prepared_workspace.workspace_root / "bin/searxng-search").exists()
    assert (prepared_workspace.workspace_root / "bin/snapshot-inspect").exists()
    assert not (prepared_workspace.workspace_root / ".claude").exists()
    assert os.path.islink(prepared_workspace.workspace_root / "logs")
    assert os.path.islink(prepared_workspace.workspace_root / "out")
    assert not os.path.islink(prepared_workspace.workspace_root / ".playwright-cli")
    assert (prepared_workspace.workspace_root / ".playwright-cli").is_dir()
    assert (tmp_path / "logs").exists()
    assert (tmp_path / "out").exists()
    assert not (tmp_path / ".playwright-cli").exists()

    provisioner.cleanup_workspace(workspace_root=prepared_workspace.workspace_root)


def test_cleanup_workspace_removes_prepared_workspace(tmp_path: Path) -> None:
    """Cleanup should remove the temp workspace directory."""
    provisioner = IsolatedWorkspaceProvisioner(
        repository_root=discover_repository_root(),
        python_executable="/usr/bin/python3",
    )
    prepared_workspace = provisioner.prepare_workspace(launch_directory=tmp_path)

    provisioner.cleanup_workspace(workspace_root=prepared_workspace.workspace_root)

    assert not prepared_workspace.workspace_root.exists()
