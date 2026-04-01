"""Composition root for the launcher-backed Web API."""

from __future__ import annotations

import sys

from price_search_web_api.adapters.local_run_backend import LocalRunBackend
from price_search_web_api.application.run_application_service import RunApplicationService
from price_search_web_api.config import load_config


def build_application() -> RunApplicationService:
    """Construct the Web API application service with local adapters."""
    config = load_config()
    backend = LocalRunBackend(
        run_root=config.run_root,
        python_executable=sys.executable,
    )
    return RunApplicationService(backend=backend)
