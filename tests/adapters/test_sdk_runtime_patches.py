"""Tests for temporary claude-agent-sdk runtime patches."""

from __future__ import annotations

from price_search.adapters.claude_sdk.sdk_runtime_patches import (
    apply_runtime_patches,
    is_runtime_patch_applied,
)


def test_apply_runtime_patches_replaces_query_wait_method() -> None:
    """The upstream timeout-based wait method should be replaced at import time."""
    from claude_agent_sdk._internal.query import Query

    apply_runtime_patches()

    assert is_runtime_patch_applied() is True
    assert Query.wait_for_result_and_end_input.__name__ == (
        "wait_for_result_and_end_input_without_timeout"
    )
