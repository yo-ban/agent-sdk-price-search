"""Tests for research validation hooks."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

from claude_agent_sdk.types import HookContext, SyncHookJSONOutput
from price_search.adapters.claude_sdk.research_validation_hooks import (
    BASH_TOOL_NAME,
    READ_TOOL_NAME,
    STRUCTURED_OUTPUT_TOOL_NAME,
    annotate_playwright_navigation_result,
    build_post_tool_use_hooks,
    build_pre_tool_use_hooks,
    validate_bash_command_before_execute,
    validate_candidate_research_result,
    validate_read_request_before_execute,
    validate_structured_output_before_finalize,
)


def test_validate_candidate_research_result_warns_when_no_offers_and_no_substitute() -> None:
    """Missing offers without substitution should force further research."""
    result = validate_candidate_research_result(
        payload={
            "identified_product": {
                "is_substitute": False,
                "substitution_reason": "",
            },
            "offers": [],
        }
    )

    assert result["ok"] is False
    assert any(
        "without researching variants or successor products" in warning
        for warning in result["warnings"]
    )


def test_validate_candidate_research_result_warns_when_xml_tags_are_embedded() -> None:
    """XML-like fragments embedded in structured fields should be rejected."""
    malformed_summary = (
        '</parameter>\n<parameter name="offers">[{"merchant_name":"Amazon"}]'
    )
    result = validate_candidate_research_result(
        payload={
            "identified_product": {
                "is_substitute": True,
                "substitution_reason": "requested variant does not exist",
            },
            "summary": malformed_summary,
        }
    )

    assert result["ok"] is False
    assert any("parameter" in warning for warning in result["warnings"])


def test_validate_structured_output_hook_denies_incomplete_result() -> None:
    """Incomplete structured output should be denied before finalization."""
    hook_context = cast(HookContext, {"signal": None})

    async def run_hook() -> SyncHookJSONOutput:
        return await validate_structured_output_before_finalize(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": "/tmp",
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PreToolUse",
                "tool_name": STRUCTURED_OUTPUT_TOOL_NAME,
                "tool_use_id": "tool-1",
                "tool_input": {
                    "identified_product": {
                        "is_substitute": True,
                        "substitution_reason": "",
                    },
                    "offers": [],
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    hook_output = cast(dict[str, object], result.get("hookSpecificOutput"))
    assert hook_output.get("permissionDecision")
    permission_reason = cast(str, hook_output.get("permissionDecisionReason"))
    assert "Price research result is incomplete." in permission_reason
    assert "not ready to finalize" in permission_reason
    assert "Review <offer_rules> before continuing the research." in permission_reason
    assert "substitution_reason is empty" in permission_reason


def test_build_pre_tool_use_hooks_registers_structured_output_guard() -> None:
    """Structured output, Bash, and Read guards should all be registered."""
    hooks = build_pre_tool_use_hooks()

    assert len(hooks) == 3
    assert any(getattr(hook, "matcher", None) == BASH_TOOL_NAME for hook in hooks)
    assert any(getattr(hook, "matcher", None) == READ_TOOL_NAME for hook in hooks)
    assert any(getattr(hook, "matcher", None) == STRUCTURED_OUTPUT_TOOL_NAME for hook in hooks)


def test_build_post_tool_use_hooks_registers_bash_annotation() -> None:
    """PostToolUse should register the Bash annotation hook."""
    hooks = build_post_tool_use_hooks()

    assert len(hooks) == 1
    assert getattr(hooks[0], "matcher", None) == BASH_TOOL_NAME


def test_validate_bash_command_hook_denies_full_page_text_dump() -> None:
    """Full-page text without any narrowing should be blocked."""
    hook_context = cast(HookContext, {"signal": None})

    async def run_hook() -> SyncHookJSONOutput:
        return await validate_bash_command_before_execute(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": "/tmp",
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PreToolUse",
                "tool_name": BASH_TOOL_NAME,
                "tool_use_id": "tool-2",
                "tool_input": {
                    "command": 'playwright-cli eval "document.body.innerText"',
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    hook_output = cast(dict[str, object], result.get("hookSpecificOutput"))
    permission_reason = cast(str, hook_output.get("permissionDecisionReason"))
    assert hook_output.get("permissionDecision") == "deny"
    assert "full-page text directly" in permission_reason


def test_validate_bash_command_hook_denies_head_pipeline_after_full_page_text_dump() -> None:
    """Full-page text piped through head should be blocked."""
    hook_context = cast(HookContext, {"signal": None})

    async def run_hook() -> SyncHookJSONOutput:
        return await validate_bash_command_before_execute(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": "/tmp",
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PreToolUse",
                "tool_name": BASH_TOOL_NAME,
                "tool_use_id": "tool-2b",
                "tool_input": {
                    "command": (
                        'playwright-cli eval "document.documentElement.innerText" '
                        '| grep -E "ASIN|型番" | head -5'
                    ),
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    hook_output = cast(dict[str, object], result.get("hookSpecificOutput"))
    assert hook_output.get("permissionDecision") == "deny"


def test_validate_bash_command_hook_allows_filtered_eval_inside_browser() -> None:
    """Focused browser-side filtering should remain allowed."""
    hook_context = cast(HookContext, {"signal": None})

    async def run_hook() -> SyncHookJSONOutput:
        return await validate_bash_command_before_execute(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": "/tmp",
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PreToolUse",
                "tool_name": BASH_TOOL_NAME,
                "tool_use_id": "tool-3",
                "tool_input": {
                    "command": (
                        'playwright-cli eval "(() => document.body.innerText'
                        '.split(\'\\\\n\').filter(Boolean).slice(0, 3).join(\'\\\\n\'))()"'
                    ),
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    assert result == {}


def test_validate_bash_command_hook_allows_grep_without_head_or_tail() -> None:
    """Post-filtering without head/tail remains allowed under the current rule."""
    hook_context = cast(HookContext, {"signal": None})

    async def run_hook() -> SyncHookJSONOutput:
        return await validate_bash_command_before_execute(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": "/tmp",
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PreToolUse",
                "tool_name": BASH_TOOL_NAME,
                "tool_use_id": "tool-4",
                "tool_input": {
                    "command": (
                        'playwright-cli eval "document.body.innerText" '
                        '| grep -E "ASIN|型番"'
                    ),
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    assert result == {}


def test_annotate_playwright_navigation_result_warns_on_used_item_snapshot(
    tmp_path: Path,
) -> None:
    """Playwright open/goto results should warn when the snapshot contains used-item text."""
    hook_context = cast(HookContext, {"signal": None})
    snapshot_path = tmp_path / "page.yml"
    snapshot_path.write_text('- text "中古 22,000円" [ref=e1]\n', encoding="utf-8")

    async def run_hook() -> SyncHookJSONOutput:
        return await annotate_playwright_navigation_result(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": str(tmp_path),
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PostToolUse",
                "tool_name": BASH_TOOL_NAME,
                "tool_use_id": "tool-4a",
                "tool_input": {
                    "command": "playwright-cli open https://example.com/product",
                },
                "tool_response": {
                    "stdout": f"### Snapshot\n- [Snapshot]({snapshot_path})\n",
                    "stderr": "",
                    "interrupted": False,
                    "isImage": False,
                    "noOutputExpected": False,
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    hook_output = cast(dict[str, object], result.get("hookSpecificOutput"))
    additional_context = cast(str, hook_output.get("additionalContext"))
    assert hook_output.get("hookEventName") == "PostToolUse"
    assert "contains '中古'" in additional_context


def test_annotate_playwright_navigation_result_ignores_non_navigation_command(
    tmp_path: Path,
) -> None:
    """Only open/goto results should be annotated."""
    hook_context = cast(HookContext, {"signal": None})
    snapshot_path = tmp_path / "page.yml"
    snapshot_path.write_text('- text "中古 22,000円" [ref=e1]\n', encoding="utf-8")

    async def run_hook() -> SyncHookJSONOutput:
        return await annotate_playwright_navigation_result(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": str(tmp_path),
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PostToolUse",
                "tool_name": BASH_TOOL_NAME,
                "tool_use_id": "tool-4b",
                "tool_input": {
                    "command": 'playwright-cli eval "document.title"',
                },
                "tool_response": {
                    "stdout": f"### Snapshot\n- [Snapshot]({snapshot_path})\n",
                    "stderr": "",
                    "interrupted": False,
                    "isImage": False,
                    "noOutputExpected": False,
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    assert result == {}


def test_annotate_playwright_navigation_result_ignores_snapshot_without_used_item_text(
    tmp_path: Path,
) -> None:
    """Navigation results without 中古 in the snapshot should stay unannotated."""
    hook_context = cast(HookContext, {"signal": None})
    snapshot_path = tmp_path / "page.yml"
    snapshot_path.write_text('- text "新品 49,800円" [ref=e1]\n', encoding="utf-8")

    async def run_hook() -> SyncHookJSONOutput:
        return await annotate_playwright_navigation_result(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": str(tmp_path),
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PostToolUse",
                "tool_name": BASH_TOOL_NAME,
                "tool_use_id": "tool-4c",
                "tool_input": {
                    "command": "playwright-cli goto https://example.com/product",
                },
                "tool_response": {
                    "stdout": f"### Snapshot\n- [Snapshot]({snapshot_path})\n",
                    "stderr": "",
                    "interrupted": False,
                    "isImage": False,
                    "noOutputExpected": False,
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    assert result == {}


def test_validate_read_request_hook_denies_large_snapshot_yaml(tmp_path: Path) -> None:
    """Large snapshot YAML should be redirected to snapshot-inspect before Read."""
    hook_context = cast(HookContext, {"signal": None})
    snapshot_path = tmp_path / "page.yaml"
    snapshot_path.write_text(_large_snapshot_text(), encoding="utf-8")

    async def run_hook() -> SyncHookJSONOutput:
        return await validate_read_request_before_execute(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": str(tmp_path),
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PreToolUse",
                "tool_name": READ_TOOL_NAME,
                "tool_use_id": "tool-5",
                "tool_input": {
                    "file_path": str(snapshot_path),
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    hook_output = cast(dict[str, object], result.get("hookSpecificOutput"))
    permission_reason = cast(str, hook_output.get("permissionDecisionReason"))
    assert hook_output.get("permissionDecision") == "deny"
    assert "snapshot-inspect" in permission_reason


def test_validate_read_request_hook_allows_small_snapshot_yaml(tmp_path: Path) -> None:
    """Small snapshot YAML should remain directly readable."""
    hook_context = cast(HookContext, {"signal": None})
    snapshot_path = tmp_path / "small-page.yaml"
    snapshot_path.write_text(
        '- generic [ref=e2]:\n  - button "Add to cart" [ref=e3]\n',
        encoding="utf-8",
    )

    async def run_hook() -> SyncHookJSONOutput:
        return await validate_read_request_before_execute(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": str(tmp_path),
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PreToolUse",
                "tool_name": READ_TOOL_NAME,
                "tool_use_id": "tool-6",
                "tool_input": {
                    "file_path": str(snapshot_path),
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    assert result == {}


def test_validate_read_request_hook_allows_snapshot_yaml_at_size_limit(
    tmp_path: Path,
) -> None:
    """Snapshot YAML at the direct-read limit should remain readable."""
    hook_context = cast(HookContext, {"signal": None})
    snapshot_path = tmp_path / "threshold-page.yaml"
    snapshot_path.write_text(_snapshot_text_of_length(5000), encoding="utf-8")

    async def run_hook() -> SyncHookJSONOutput:
        return await validate_read_request_before_execute(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": str(tmp_path),
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PreToolUse",
                "tool_name": READ_TOOL_NAME,
                "tool_use_id": "tool-6b",
                "tool_input": {
                    "file_path": str(snapshot_path),
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    assert result == {}


def test_validate_read_request_hook_allows_regular_yaml(tmp_path: Path) -> None:
    """Non-snapshot YAML should remain readable."""
    hook_context = cast(HookContext, {"signal": None})
    config_path = tmp_path / "config.yaml"
    config_path.write_text("name: example\nkind: config\n", encoding="utf-8")

    async def run_hook() -> SyncHookJSONOutput:
        return await validate_read_request_before_execute(
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": str(tmp_path),
                "agent_id": "agent-1",
                "agent_type": "default",
                "hook_event_name": "PreToolUse",
                "tool_name": READ_TOOL_NAME,
                "tool_use_id": "tool-6",
                "tool_input": {
                    "file_path": str(config_path),
                },
            },
            None,
            hook_context,
        )

    result = asyncio.run(run_hook())

    assert result == {}


def _large_snapshot_text() -> str:
    """Create a snapshot-like YAML body that crosses the direct-read threshold."""
    lines = ["- generic [ref=e2]:"]
    lines.extend(
        f'  - button "Add to cart {index}" [ref=e{index + 3}]'
        for index in range(250)
    )
    return "\n".join(lines) + "\n"


def _snapshot_text_of_length(length: int) -> str:
    """Create snapshot-like text with an exact character length."""
    seed = '- generic [ref=e2]:\n  - button "Add to cart" [ref=e3]\n'
    repeated = (seed * ((length // len(seed)) + 2))[:length]
    return repeated
