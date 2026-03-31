"""Application tests for isolated price-search launching."""

from __future__ import annotations

from pathlib import Path

import pytest
from price_search_launcher.application.launch_price_search import LaunchPriceSearchUseCase
from price_search_launcher.contracts.isolated_price_search_request import (
    IsolatedPriceSearchRequest,
)
from price_search_launcher.contracts.prepared_workspace import PreparedWorkspace


class FakeRuntimeService:
    """Record runtime preparation calls."""

    def __init__(self, call_log: list[str]) -> None:
        """Store one shared call log."""
        self._call_log = call_log

    def ensure_ready(self) -> None:
        """Record runtime readiness orchestration."""
        self._call_log.append("runtime")


class FakeWorkspacePort:
    """Return a deterministic prepared workspace and track cleanup."""

    def __init__(self, call_log: list[str], prepared_workspace: PreparedWorkspace) -> None:
        """Store one prepared workspace fixture."""
        self._call_log = call_log
        self._prepared_workspace = prepared_workspace
        self.cleaned_workspace_root: Path | None = None

    def prepare_workspace(self, *, launch_directory: Path) -> PreparedWorkspace:
        """Record preparation and return the configured workspace."""
        self._call_log.append("prepare-workspace")
        return self._prepared_workspace

    def cleanup_workspace(self, *, workspace_root: Path) -> None:
        """Record cleanup."""
        self._call_log.append("cleanup-workspace")
        self.cleaned_workspace_root = workspace_root


class FakeProcessRunner:
    """Return a configured exit code while recording invocation."""

    def __init__(self, call_log: list[str], *, exit_code: int) -> None:
        """Store one shared call log and the desired exit code."""
        self._call_log = call_log
        self._exit_code = exit_code
        self.received_args: tuple[str, ...] | None = None
        self.received_workspace: PreparedWorkspace | None = None

    def run_price_search(
        self,
        *,
        cli_args: tuple[str, ...],
        prepared_workspace: PreparedWorkspace,
    ) -> int:
        """Record the run request and return the configured exit code."""
        self._call_log.append("run-price-search")
        self.received_args = cli_args
        self.received_workspace = prepared_workspace
        return self._exit_code


class FailingProcessRunner(FakeProcessRunner):
    """Raise from the subprocess boundary to verify cleanup behavior."""

    def __init__(self, call_log: list[str]) -> None:
        """Provide a dedicated failing runner without a meaningful exit code."""
        super().__init__(call_log, exit_code=1)

    def run_price_search(
        self,
        *,
        cli_args: tuple[str, ...],
        prepared_workspace: PreparedWorkspace,
    ) -> int:
        """Record the request before failing."""
        super().run_price_search(
            cli_args=cli_args,
            prepared_workspace=prepared_workspace,
        )
        raise RuntimeError("process failed")


def test_launch_price_search_prepares_runtime_then_runs_in_workspace() -> None:
    """The launcher use case should prepare runtime before starting the subprocess."""
    call_log: list[str] = []
    prepared_workspace = PreparedWorkspace(
        workspace_root=Path("/tmp/workspace"),
        config_file=Path("/tmp/workspace/config/price_search.toml"),
        local_config_file=None,
    )
    expected_exit_code = 17
    process_runner = FakeProcessRunner(call_log, exit_code=expected_exit_code)
    use_case = LaunchPriceSearchUseCase(
        runtime_service=FakeRuntimeService(call_log),
        workspace_port=FakeWorkspacePort(call_log, prepared_workspace),
        process_runner=process_runner,
    )

    exit_code = use_case.execute(
        IsolatedPriceSearchRequest(
            cli_args=("全自動コーヒーメーカー ABC-1234", "--json"),
            launch_directory=Path("/tmp/launch"),
        )
    )

    assert exit_code == expected_exit_code
    assert process_runner.received_args == ("全自動コーヒーメーカー ABC-1234", "--json")
    assert process_runner.received_workspace == prepared_workspace
    assert call_log == [
        "runtime",
        "prepare-workspace",
        "run-price-search",
        "cleanup-workspace",
    ]


def test_launch_price_search_cleans_workspace_after_runner_failure() -> None:
    """Workspace cleanup should still happen when subprocess execution fails."""
    call_log: list[str] = []
    prepared_workspace = PreparedWorkspace(
        workspace_root=Path("/tmp/workspace"),
        config_file=Path("/tmp/workspace/config/price_search.toml"),
        local_config_file=None,
    )
    workspace_port = FakeWorkspacePort(call_log, prepared_workspace)
    use_case = LaunchPriceSearchUseCase(
        runtime_service=FakeRuntimeService(call_log),
        workspace_port=workspace_port,
        process_runner=FailingProcessRunner(call_log),
    )

    with pytest.raises(RuntimeError):
        use_case.execute(
            IsolatedPriceSearchRequest(
                cli_args=("全自動コーヒーメーカー ABC-1234",),
                launch_directory=Path("/tmp/launch"),
            )
        )

    assert workspace_port.cleaned_workspace_root == prepared_workspace.workspace_root
    assert call_log[-1] == "cleanup-workspace"
