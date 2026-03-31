"""Composition root for the launcher-backed Web API."""

from __future__ import annotations

import sys

from price_search_web_api.adapters.local_run_backend import LocalRunBackend
from price_search_web_api.application.cancel_run import CancelRunUseCase
from price_search_web_api.application.delete_run import DeleteRunUseCase
from price_search_web_api.application.get_run import GetRunUseCase
from price_search_web_api.application.list_runs import ListRunsUseCase
from price_search_web_api.application.start_run import StartRunUseCase
from price_search_web_api.config import load_config


def build_application() -> tuple[
    StartRunUseCase,
    GetRunUseCase,
    ListRunsUseCase,
    CancelRunUseCase,
    DeleteRunUseCase,
]:
    """Construct the Web API use cases with local adapters."""
    config = load_config()
    backend = LocalRunBackend(
        run_root=config.run_root,
        python_executable=sys.executable,
    )
    return (
        StartRunUseCase(run_launcher=backend),
        GetRunUseCase(run_query=backend),
        ListRunsUseCase(run_query=backend),
        CancelRunUseCase(run_control=backend),
        DeleteRunUseCase(run_control=backend),
    )
