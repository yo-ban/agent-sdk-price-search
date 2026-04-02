"""Infrastructure layer: Claude Code SDK による価格調査 adapter。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import (
    ThinkingConfigAdaptive,
    ThinkingConfigDisabled,
    ThinkingConfigEnabled,
)

from price_search.adapters.claude_sdk.agent_activity_serialization import (
    stream_message_to_log_event,
)
from price_search.adapters.claude_sdk.mcp_servers import build_mcp_servers
from price_search.adapters.claude_sdk.price_research_prompt import (
    PriceResearchPrompt,
    build_price_research_prompt,
)
from price_search.adapters.claude_sdk.provider_environment import build_claude_code_env
from price_search.adapters.claude_sdk.research_validation_hooks import (
    build_post_tool_use_hooks,
    build_pre_tool_use_hooks,
)
from price_search.adapters.claude_sdk.structured_output import (
    build_structured_output_schema,
    raw_identified_product_from_payload,
    raw_offer_from_payload,
)
from price_search.config import AppConfig
from price_search.domain.models import ProductResearchQuery
from price_search.ports.agent_activity_log_port import (
    AgentActivityLogEvent,
    AgentActivityLogPort,
)
from price_search.ports.price_research_agent_port import (
    PriceResearchAgentPort,
    RawResearchResult,
)

LOGGER = logging.getLogger(__name__)
SDK_JSON_BUFFER_SIZE_BYTES = 8 * 1024 * 1024

# エージェントに使わせない組み込みツール
DISALLOWED_BUILT_IN_TOOLS = [
    "AskUserQuestion",
    "CronCreate",
    "CronDelete",
    "CronList",
    "EnterPlanMode",
    "EnterWorktree",
    "ExitPlanMode",
    "ExitWorktree",
    "LSP",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "RemoteTrigger"
]


class ClaudeCodePriceResearchAgent(PriceResearchAgentPort):
    """Claude Code SDK を利用する価格調査の具象アダプター。"""

    def __init__(
        self,
        config: AppConfig,
        activity_logger: AgentActivityLogPort,
    ) -> None:
        """実行設定と監査ロガーを保持する。"""
        self._config = config
        self._activity_logger = activity_logger

    async def research(self, query: ProductResearchQuery) -> RawResearchResult:
        """Claude Code SDK を用いて商品価格を調査する。"""
        structured_output: dict[str, Any] | None = None
        final_text = ""
        result_subtype = ""
        self._record_event(
            AgentActivityLogEvent(
                event_type="research_started",
                payload={
                    "product_name": query.product_name,
                    "market": query.market,
                    "currency": query.currency,
                    "max_offers": query.max_offers,
                    "claude_provider": self._config.claude_provider,
                },
            )
        )

        research_prompt = build_price_research_prompt(query=query)
        async for message in query_agent(
            prompt=research_prompt.user_message,
            options=_build_options(
                config=self._config,
                research_prompt=research_prompt,
            ),
        ):
            stream_event = stream_message_to_log_event(message)
            if stream_event is not None:
                self._record_event(stream_event)
            if hasattr(message, "structured_output") and message.structured_output is not None:
                structured_output = message.structured_output
            if hasattr(message, "result") and isinstance(message.result, str):
                final_text = message.result
            if hasattr(message, "subtype") and isinstance(message.subtype, str):
                result_subtype = message.subtype

        if structured_output is None:
            raise RuntimeError(
                "Claude Agent SDK did not return structured output "
                f"(result_subtype={result_subtype or 'unknown'})."
            )

        identified_product = raw_identified_product_from_payload(
            structured_output.get("identified_product", {}),
        )
        offers = tuple(raw_offer_from_payload(payload) for payload in structured_output["offers"])
        summary = structured_output.get("summary", "").strip() or final_text.strip()
        return RawResearchResult(
            identified_product=identified_product,
            summary=summary,
            offers=offers,
        )

    def _record_event(self, event: AgentActivityLogEvent) -> None:
        """監査イベントを永続化する。ログ書き込み失敗では処理を中断しない。"""
        try:
            self._activity_logger.log_event(event)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Failed to write agent activity log: %s", exc)


def query_agent(*, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[Any]:
    """SDK 呼び出しを分離するシーム。文字列 prompt でも streaming input を使う。"""
    return query(prompt=_single_prompt_stream(prompt=prompt), options=options)


async def _single_prompt_stream(*, prompt: str) -> AsyncIterator[dict[str, Any]]:
    """単一の文字列 prompt を SDK の streaming input 形式へ変換する。"""
    yield {
        "type": "user",
        "session_id": "",
        "message": {
            "role": "user",
            "content": prompt,
        },
        "parent_tool_use_id": None,
    }


def _build_options(
    config: AppConfig,
    research_prompt: PriceResearchPrompt,
) -> ClaudeAgentOptions:
    """価格調査ユースケース用の Claude Agent SDK オプションを構築する。"""
    workspace_root = Path(config.workspace_root).resolve()
    return ClaudeAgentOptions(
        model=config.primary_model,
        thinking=_build_thinking_config(config=config),
        effort=config.agent_effort,
        system_prompt=research_prompt.system_append,
        hooks={
            "PreToolUse": build_pre_tool_use_hooks(),
            "PostToolUse": build_post_tool_use_hooks(),
        },
        disallowed_tools=DISALLOWED_BUILT_IN_TOOLS,
        permission_mode="bypassPermissions",
        fallback_model=config.small_model,
        max_turns=config.max_turns,
        setting_sources=["project"],
        add_dirs=[Path.home()],
        cli_path=workspace_root / "bin" / "claude-code-wrapper",
        mcp_servers=build_mcp_servers(),
        env=build_claude_code_env(config=config),
        max_buffer_size=SDK_JSON_BUFFER_SIZE_BYTES,
        output_format={
            "type": "json_schema",
            "schema": build_structured_output_schema(),
        },
    )


def _build_thinking_config(
    *,
    config: AppConfig,
) -> ThinkingConfigEnabled | ThinkingConfigAdaptive | ThinkingConfigDisabled:
    """共通の thinking 設定を Claude Agent SDK の型へ変換する。"""
    if config.agent_thinking_type == "adaptive":
        return ThinkingConfigAdaptive(type="adaptive")
    if config.agent_thinking_type == "disabled":
        return ThinkingConfigDisabled(type="disabled")
    return ThinkingConfigEnabled(
        type="enabled",
        budget_tokens=config.agent_thinking_budget_tokens,
    )
