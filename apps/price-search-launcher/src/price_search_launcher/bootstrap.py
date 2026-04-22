"""隔離 workspace launcher のコンポジションルート。"""

from __future__ import annotations

import sys

from price_search.config import load_config

from price_search_launcher.adapters.filesystem.isolated_workspace import (
    IsolatedWorkspaceProvisioner,
    discover_repository_root,
)
from price_search_launcher.adapters.process.subprocess_price_search_runner import (
    SubprocessPriceSearchRunner,
)
from price_search_launcher.adapters.runtime.docker_runtime_service import (
    DockerRuntimeService,
)
from price_search_launcher.application.launch_price_search import (
    LaunchPriceSearchUseCase,
)


def build_use_case() -> LaunchPriceSearchUseCase:
    """launcher 用の依存グラフを組み立てる。"""
    repository_root = discover_repository_root()
    runtime_config = load_config()
    return LaunchPriceSearchUseCase(
        runtime_service=DockerRuntimeService(
            repository_root=repository_root,
            search_provider=runtime_config.search_provider,
            searxng_search_url=runtime_config.searxng_search_url,
        ),
        workspace_port=IsolatedWorkspaceProvisioner(
            repository_root=repository_root,
            python_executable=sys.executable,
        ),
        process_runner=SubprocessPriceSearchRunner(
            python_executable=sys.executable
        ),
    )
