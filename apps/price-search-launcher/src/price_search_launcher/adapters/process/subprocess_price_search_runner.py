"""Process adapter: price-search subprocess runner。"""

from __future__ import annotations

import os
import subprocess

from price_search_launcher.contracts.prepared_workspace import PreparedWorkspace


class SubprocessPriceSearchRunner:
    """現在の Python 環境で price-search CLI を subprocess 起動する。"""

    def __init__(self, *, python_executable: str) -> None:
        """child process に使う Python 実行ファイルを保持する。"""
        self._python_executable = python_executable

    def run_price_search(
        self,
        *,
        cli_args: tuple[str, ...],
        prepared_workspace: PreparedWorkspace,
    ) -> int:
        """隔離 workspace を cwd にして public CLI を実行する。"""
        command = [
            self._python_executable,
            "-m",
            "price_search.handler.cli",
            *cli_args,
        ]
        env = _build_subprocess_env(prepared_workspace=prepared_workspace)
        completed_process = subprocess.run(
            command,
            cwd=prepared_workspace.workspace_root,
            env=env,
            check=False,
        )
        return completed_process.returncode


def _build_subprocess_env(*, prepared_workspace: PreparedWorkspace) -> dict[str, str]:
    """workspace root と copied config を反映した child env を返す。"""
    child_env = os.environ.copy()
    child_env["PRICE_SEARCH_WORKSPACE_ROOT"] = str(prepared_workspace.workspace_root)
    child_env["PRICE_SEARCH_CONFIG_FILE"] = str(prepared_workspace.config_file)
    if prepared_workspace.local_config_file is not None:
        child_env["PRICE_SEARCH_LOCAL_CONFIG_FILE"] = str(
            prepared_workspace.local_config_file
        )
    else:
        child_env.pop("PRICE_SEARCH_LOCAL_CONFIG_FILE", None)
    return child_env
