"""Tests for the public price-search composition root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import price_search.bootstrap as bootstrap
from price_search.config import AppConfig


@dataclass
class _CapturedLogger:
    """Captured logger construction details for composition-root tests."""

    log_path: Path
    run_id: str


@dataclass
class _CapturedAgent:
    """Captured agent construction details for composition-root tests."""

    config: AppConfig
    activity_logger: _CapturedLogger


def test_build_use_case_uses_public_activity_log_path_builder(monkeypatch) -> None:
    """build_use_case should delegate log-path resolution to the public helper."""
    captured = _patch_build_use_case_dependencies(monkeypatch)
    resolved_path = Path("/tmp/logs/run.jsonl")

    def fake_build_activity_log_path(**kwargs) -> Path:
        """Capture path-builder inputs and return a deterministic path."""
        captured["path_builder_kwargs"] = kwargs
        return resolved_path

    monkeypatch.setattr(
        bootstrap,
        "build_activity_log_path",
        fake_build_activity_log_path,
    )

    bootstrap.build_use_case(product_name="全自動コーヒーメーカー ABC-1234")

    logger = cast(Any, captured["logger"])
    agent = cast(Any, captured["agent"])
    assert captured["path_builder_kwargs"] == {
        "configured_log_dir": "logs",
        "product_name": "全自動コーヒーメーカー ABC-1234",
        "run_id": "abcdef1234567890",
    }
    assert logger.log_path == resolved_path
    assert logger.run_id == "abcdef1234567890"
    assert agent.activity_logger == logger


def _patch_build_use_case_dependencies(monkeypatch) -> dict[str, object]:
    """Patch composition-root dependencies and capture constructed collaborators."""
    captured: dict[str, object] = {}

    class FakeUuid:
        """UUID replacement exposing a stable hex representation."""

        hex = "abcdef1234567890"

    class FakeLogger:
        """Record the requested log path without touching the filesystem."""

        def __init__(self, log_path: str | Path, run_id: str) -> None:
            """Capture the composition-root logger arguments."""
            self.log_path = Path(log_path)
            self.run_id = run_id
            captured["logger"] = self

    class FakeAgent:
        """Record the injected config and logger from build_use_case."""

        def __init__(self, *, config: AppConfig, activity_logger: _CapturedLogger) -> None:
            """Capture the composition-root agent arguments."""
            captured["agent"] = _CapturedAgent(
                config=config,
                activity_logger=activity_logger,
            )

    class FakeUseCase:
        """Trivial replacement for the concrete use case."""

        def __init__(self, *, agent_port: _CapturedAgent) -> None:
            """Capture the injected agent for later assertions."""
            captured["use_case_agent"] = agent_port

    monkeypatch.setattr(bootstrap, "load_config", lambda: _build_config())
    monkeypatch.setattr(bootstrap, "uuid4", lambda: FakeUuid())
    monkeypatch.setattr(bootstrap, "JsonlAgentActivityLogger", FakeLogger)
    monkeypatch.setattr(bootstrap, "ClaudeCodePriceResearchAgent", FakeAgent)
    monkeypatch.setattr(bootstrap, "RunPriceResearchUseCase", FakeUseCase)
    return captured


def _build_config() -> AppConfig:
    """Create a representative AppConfig for composition-root tests."""
    return AppConfig(
        claude_provider="subscription",
        aws_region="ap-northeast-1",
        aws_profile="default",
        anthropic_api_key=None,
        openrouter_api_key=None,
        primary_model="claude-sonnet-4-6",
        small_model="claude-haiku-4-5",
        primary_model_capabilities=None,
        small_model_capabilities=None,
        agent_thinking_type="enabled",
        agent_thinking_budget_tokens=4096,
        agent_effort="high",
        max_turns=100,
        max_offers=4,
        market="JP",
        currency="JPY",
        agent_activity_log_dir="logs",
        result_output_dir="out",
        searxng_search_url="http://127.0.0.1:18888/search",
        searxng_engines=("google", "brave"),
        searxng_language="ja-JP",
        searxng_result_limit=8,
        workspace_root="/tmp/workspace",
    )
