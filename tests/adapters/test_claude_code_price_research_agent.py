"""Adapter tests for the public ClaudeCodePriceResearchAgent interface."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_agent_sdk import AssistantMessage, ToolUseBlock
from price_search.adapters.claude_sdk.price_research_agent import (
    DISALLOWED_BUILT_IN_TOOLS,
    ClaudeCodePriceResearchAgent,
)
from price_search.config import AppConfig
from price_search.domain.models import ProductResearchQuery
from price_search.ports.agent_activity_log_port import AgentActivityLogEvent


class InMemoryActivityLogger:
    """Collect audit events in memory for adapter tests."""

    def __init__(self) -> None:
        """Initialize an empty event sink."""
        self.events: list[AgentActivityLogEvent] = []

    def log_event(self, event: AgentActivityLogEvent) -> None:
        """Record one event."""
        self.events.append(event)


@dataclass
class FakeSdkResult:
    """Minimal SDK-like result payload for adapter tests."""

    structured_output: dict[str, Any] | None
    result: str = ""
    subtype: str = "success"


def test_research_builds_bedrock_sdk_options_and_logs_provider(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Research should pass provider-aware Bedrock options through the public adapter API."""
    config = _build_config(
        tmp_path,
        primary_model_capabilities="tool-use,reasoning",
        small_model_capabilities="tool-use",
    )
    query = _build_query()
    structured_output = _structured_output_payload(query=query)
    tool_name = "Bash"
    logger = InMemoryActivityLogger()
    adapter = ClaudeCodePriceResearchAgent(config=config, activity_logger=logger)
    captured: dict[str, Any] = {}

    async def fake_query_agent(*, prompt: str, options) -> Any:
        captured["prompt"] = prompt
        captured["options"] = options
        yield AssistantMessage(
            content=[
                ToolUseBlock(
                    id="tool-use-1",
                    name=tool_name,
                    input={"command": "searxng-search 全自動コーヒーメーカー ABC-1234"},
                )
            ],
            model=config.primary_model,
        )
        yield FakeSdkResult(structured_output=structured_output)

    monkeypatch.setattr(
        "price_search.adapters.claude_sdk.price_research_agent.query_agent",
        fake_query_agent,
    )

    result = asyncio.run(adapter.research(query=query))

    options = captured["options"]
    assert query.product_name in captured["prompt"]
    assert options.model == config.primary_model
    assert options.fallback_model == config.small_model
    assert options.disallowed_tools == DISALLOWED_BUILT_IN_TOOLS
    assert Path(options.cli_path) == (Path(config.workspace_root) / "bin" / "claude-code-wrapper")
    assert options.env["CLAUDE_CODE_USE_BEDROCK"]
    assert "ANTHROPIC_API_KEY" not in options.env
    assert "ANTHROPIC_AUTH_TOKEN" not in options.env
    assert "ANTHROPIC_BASE_URL" not in options.env
    assert "OPENROUTER_API_KEY" not in options.env
    assert "ANTHROPIC_AUTH_TOKEN" in options.env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    assert "OPENROUTER_API_KEY" in options.env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    assert (
        options.env["ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES"]
        == config.primary_model_capabilities
    )
    assert (
        options.env["ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES"]
        == config.small_model_capabilities
    )
    assert (
        "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES"
        not in options.env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    )
    assert (
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES"
        not in options.env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    )
    assert "PRICE_SEARCH_PLAYWRIGHT_USER_AGENT" not in options.env
    assert result.identified_product.name == structured_output["identified_product"]["name"]
    assert (
        result.offers[0].merchant_product_url
        == structured_output["offers"][0]["merchant_product_url"]
    )
    assert logger.events[0].payload["claude_provider"] == config.claude_provider
    assert logger.events[0].payload["product_name"] == query.product_name
    assert logger.events[1].payload["content"][0]["name"] == tool_name


def test_research_passes_api_key_for_anthropic_provider(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Anthropic mode should inject API-key auth through the public adapter interface."""
    config = _build_config(
        tmp_path,
        claude_provider="anthropic",
        anthropic_api_key="test-api-key",
        primary_model="claude-sonnet-4-6",
        small_model="claude-haiku-4-5",
    )
    adapter = ClaudeCodePriceResearchAgent(
        config=config,
        activity_logger=InMemoryActivityLogger(),
    )
    captured: dict[str, Any] = {}
    query = _build_query()

    async def fake_query_agent(*, prompt: str, options) -> Any:
        captured["options"] = options
        yield FakeSdkResult(structured_output=_structured_output_payload(query=query))

    monkeypatch.setattr(
        "price_search.adapters.claude_sdk.price_research_agent.query_agent",
        fake_query_agent,
    )

    asyncio.run(adapter.research(query=query))

    assert Path(captured["options"].cli_path) == (
        Path(config.workspace_root) / "bin" / "claude-code-wrapper"
    )
    assert captured["options"].env["ANTHROPIC_API_KEY"] == config.anthropic_api_key
    assert "CLAUDE_CODE_USE_BEDROCK" not in captured["options"].env
    assert "ANTHROPIC_AUTH_TOKEN" not in captured["options"].env
    assert "ANTHROPIC_BASE_URL" not in captured["options"].env
    assert (
        "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES"
        not in captured["options"].env
    )
    assert (
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES"
        not in captured["options"].env
    )
    assert (
        "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES"
        in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    )
    assert (
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES"
        in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    )
    assert "CLAUDE_CODE_USE_BEDROCK" in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    assert captured["options"].env["ANTHROPIC_MODEL"] == config.primary_model


def test_research_uses_subscription_mode_without_forcing_provider_flags(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Subscription mode should avoid forcing Bedrock or API-key auth flags."""
    config = _build_config(
        tmp_path,
        claude_provider="subscription",
        primary_model="claude-sonnet-4-6",
        small_model="claude-haiku-4-5",
    )
    adapter = ClaudeCodePriceResearchAgent(
        config=config,
        activity_logger=InMemoryActivityLogger(),
    )
    captured: dict[str, Any] = {}
    query = _build_query()

    async def fake_query_agent(*, prompt: str, options) -> Any:
        captured["options"] = options
        yield FakeSdkResult(structured_output=_structured_output_payload(query=query))

    monkeypatch.setattr(
        "price_search.adapters.claude_sdk.price_research_agent.query_agent",
        fake_query_agent,
    )

    asyncio.run(adapter.research(query=query))

    assert Path(captured["options"].cli_path) == (
        Path(config.workspace_root) / "bin" / "claude-code-wrapper"
    )
    assert "CLAUDE_CODE_USE_BEDROCK" not in captured["options"].env
    assert "ANTHROPIC_API_KEY" not in captured["options"].env
    assert "ANTHROPIC_AUTH_TOKEN" not in captured["options"].env
    assert "ANTHROPIC_BASE_URL" not in captured["options"].env
    assert "OPENROUTER_API_KEY" not in captured["options"].env
    assert (
        "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES"
        not in captured["options"].env
    )
    assert (
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES"
        not in captured["options"].env
    )
    assert (
        "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES"
        in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    )
    assert (
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES"
        in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    )
    assert "ANTHROPIC_API_KEY" in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    assert "CLAUDE_CODE_USE_BEDROCK" in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    assert captured["options"].env["ANTHROPIC_MODEL"] == config.primary_model


def test_research_uses_openrouter_anthropic_compatible_env(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """OpenRouter mode should inject Anthropic-compatible endpoint env values."""
    config = _build_config(
        tmp_path,
        claude_provider="openrouter",
        openrouter_api_key="test-openrouter-key",
        primary_model="anthropic/claude-sonnet-4.6",
        small_model="anthropic/claude-haiku-4.5",
    )
    adapter = ClaudeCodePriceResearchAgent(
        config=config,
        activity_logger=InMemoryActivityLogger(),
    )
    captured: dict[str, Any] = {}
    query = _build_query()

    async def fake_query_agent(*, prompt: str, options) -> Any:
        captured["options"] = options
        yield FakeSdkResult(structured_output=_structured_output_payload(query=query))

    monkeypatch.setattr(
        "price_search.adapters.claude_sdk.price_research_agent.query_agent",
        fake_query_agent,
    )

    asyncio.run(adapter.research(query=query))

    assert Path(captured["options"].cli_path) == (
        Path(config.workspace_root) / "bin" / "claude-code-wrapper"
    )
    assert captured["options"].env["OPENROUTER_API_KEY"] == config.openrouter_api_key
    assert captured["options"].env["ANTHROPIC_AUTH_TOKEN"] == config.openrouter_api_key
    assert captured["options"].env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"
    assert "ANTHROPIC_API_KEY" not in captured["options"].env
    assert "CLAUDE_CODE_USE_BEDROCK" not in captured["options"].env
    assert (
        "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES"
        not in captured["options"].env
    )
    assert (
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES"
        not in captured["options"].env
    )
    assert (
        "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES"
        in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    )
    assert (
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES"
        in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]
    )
    assert "ANTHROPIC_API_KEY" in captured["options"].env["PRICE_SEARCH_CLAUDE_UNSET_ENV"]


def _build_config(
    tmp_path: Path,
    *,
    claude_provider: str = "bedrock",
    anthropic_api_key: str | None = None,
    openrouter_api_key: str | None = None,
    primary_model: str = "global.anthropic.claude-sonnet-4-6",
    small_model: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    primary_model_capabilities: str | None = None,
    small_model_capabilities: str | None = None,
) -> AppConfig:
    """Create a representative runtime config for adapter tests."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        claude_provider=claude_provider,  # type: ignore[arg-type]
        aws_region="ap-northeast-1",
        aws_profile="default",
        anthropic_api_key=anthropic_api_key,
        openrouter_api_key=openrouter_api_key,
        primary_model=primary_model,
        small_model=small_model,
        primary_model_capabilities=primary_model_capabilities,
        small_model_capabilities=small_model_capabilities,
        agent_thinking_type="enabled",
        agent_thinking_budget_tokens=4096,
        agent_effort="high",
        max_turns=100,
        max_offers=5,
        market="JP",
        currency="JPY",
        agent_activity_log_dir=str(tmp_path / "logs"),
        result_output_dir=str(tmp_path / "out"),
        searxng_search_url="http://127.0.0.1:18888/search",
        searxng_engines=("google", "brave"),
        searxng_language="ja-JP",
        searxng_result_limit=8,
        workspace_root=str(workspace_root),
    )


def _build_query() -> ProductResearchQuery:
    """Create a stable query for adapter tests."""
    return ProductResearchQuery(
        product_name="全自動コーヒーメーカー ABC-1234",
        market="JP",
        currency="JPY",
        max_offers=3,
    )


def _structured_output_payload(*, query: ProductResearchQuery) -> dict[str, Any]:
    """Create a stable structured output payload for adapter tests."""
    return {
        "identified_product": {
            "name": query.product_name,
            "model_number": "BEE-001",
            "manufacturer": "ExampleMaker",
            "product_url": "https://example.com/products/abc-1234",
            "release_date": "2026-03-27",
            "is_substitute": False,
            "substitution_reason": "",
        },
        "summary": "価格差があります。",
        "offers": [
            {
                "merchant_name": "Yodobashi",
                "merchant_product_name": query.product_name,
                "merchant_product_url": "https://example.com/item",
                "currency": "JPY",
                "item_price": 69980,
                "availability": "在庫あり",
                "evidence": "販売ページに在庫ありと税込価格の記載がある。",
            }
        ],
    }
