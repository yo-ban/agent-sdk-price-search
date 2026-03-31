"""Upstream SDK への暫定ランタイムパッチ。"""

from __future__ import annotations

from typing import Any

_PATCH_APPLIED = False


def apply_runtime_patches() -> None:
    """現在利用中の claude-agent-sdk に必要な暫定パッチを適用する。"""
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return

    from claude_agent_sdk._internal.query import Query

    async def wait_for_result_and_end_input_without_timeout(self: Any) -> None:
        """Hooks/SDK MCP 利用時でも stdin を早期 close しない upstream patch."""
        if self.sdk_mcp_servers or self.hooks:
            await self._first_result_event.wait()

        await self.transport.end_input()

    Query.wait_for_result_and_end_input = wait_for_result_and_end_input_without_timeout
    _PATCH_APPLIED = True


def is_runtime_patch_applied() -> bool:
    """ランタイムパッチ適用済みかどうかを返す。"""
    return _PATCH_APPLIED
