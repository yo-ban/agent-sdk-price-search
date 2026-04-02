"""Infrastructure layer: MCP server registrations for Claude Code."""

from __future__ import annotations

from typing import cast

from claude_agent_sdk import create_sdk_mcp_server
from claude_agent_sdk.types import McpServerConfig

from price_search.adapters.claude_sdk.read_image_tool import READ_IMAGE_TOOL


def build_mcp_servers() -> dict[str, McpServerConfig]:
    """Return the in-process MCP servers used by the price research agent."""
    return cast(
        dict[str, McpServerConfig],
        {
            "read-image": create_sdk_mcp_server(
                name="read-image",
                tools=[READ_IMAGE_TOOL],
            )
        },
    )
