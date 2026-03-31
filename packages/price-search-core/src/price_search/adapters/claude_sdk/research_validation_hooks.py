"""価格調査エージェントの PreToolUse hooks。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from claude_agent_sdk import HookMatcher
from claude_agent_sdk.types import (
    HookCallback,
    HookContext,
    PreToolUseHookInput,
    SyncHookJSONOutput,
)

HookMatcherType = HookMatcher

STRUCTURED_OUTPUT_TOOL_NAME = "StructuredOutput"
BASH_TOOL_NAME = "Bash"
READ_TOOL_NAME = "Read"
INCOMPLETE_RESULT_REASON = "Price research result is incomplete."
REVIEW_OFFER_RULES_GUIDANCE = "This result is not ready to finalize. Review <offer_rules> before continuing the research."
PLAYWRIGHT_EVAL_GUIDANCE = "Do not dump full-page text directly. Use a focused playwright-cli eval that filters inside the browser and returns only the final value or a few matching lines."
PLAYWRIGHT_SNAPSHOT_READ_GUIDANCE = (
    "Do not read Playwright snapshot YAML directly. Use snapshot-inspect first, "
    "for example `snapshot-inspect summary <path>` or `snapshot-inspect find <path> --text \"...\"`."
)
MAX_DIRECT_SNAPSHOT_READ_CHARS = 5000
XML_MARKERS = (
    "<parameter",
    "</parameter>",
    "<summary>",
    "</summary>",
)
FULL_PAGE_TEXT_EVAL_PATTERN = re.compile(
    r"playwright-cli(?:\s+--debug)?\s+eval\b.*document\.(?:body|documentElement)\.(?:innerText|textContent)\s*(?:[\"'`]|$|\|)",
    re.DOTALL,
)
HEAD_OR_TAIL_PATTERN = re.compile(r"\|\s*(?:head|tail)\b")


def build_pre_tool_use_hooks() -> list[HookMatcherType]:
    """価格調査エージェント用の PreToolUse hook 群を返す。"""
    return [
        HookMatcher(
            matcher=BASH_TOOL_NAME,
            hooks=[cast(HookCallback, validate_bash_command_before_execute)],
        ),
        HookMatcher(
            matcher=READ_TOOL_NAME,
            hooks=[cast(HookCallback, validate_read_request_before_execute)],
        ),
        HookMatcher(
            matcher=STRUCTURED_OUTPUT_TOOL_NAME,
            hooks=[cast(HookCallback, validate_structured_output_before_finalize)],
        ),
    ]


def validate_candidate_research_result(*, payload: dict[str, Any]) -> dict[str, Any]:
    """候補の structured output が継続調査を要するかどうかを判定する。"""
    identified_product = payload.get("identified_product", {})
    has_offers_field = "offers" in payload
    offers = payload.get("offers", [])
    is_substitute = bool(identified_product.get("is_substitute", False))
    substitution_reason = str(identified_product.get("substitution_reason") or "").strip()
    text_values = tuple(_iter_text_values(payload))

    warnings: list[str] = []
    if any(marker in text for text in text_values for marker in XML_MARKERS):
        warnings.append(
            "The StructuredOutput payload contains XML-like tags. Do not embed parameter or summary tags inside structured fields."
        )
    if not has_offers_field:
        return {"ok": not warnings, "warnings": warnings}
    if not isinstance(offers, list):
        return {"ok": not warnings, "warnings": warnings}

    if not offers and not is_substitute:
        warnings.append(
            "No offer candidates were collected. You are trying to answer without researching variants or successor products."
        )
    elif not offers and is_substitute:
        warnings.append(
            "No offer candidates were collected. You identified a substitute product, but its price research is not complete."
        )
    if is_substitute and not substitution_reason:
        warnings.append(
            "A substitute product is being returned, but substitution_reason is empty. State why the substitute was chosen."
        )

    return {
        "ok": not warnings,
        "warnings": warnings,
    }


def _iter_text_values(value: Any) -> list[str]:
    """Payload 内の文字列値を再帰的に収集する。"""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(_iter_text_values(item))
        return values
    if isinstance(value, list | tuple):
        values: list[str] = []
        for item in value:
            values.extend(_iter_text_values(item))
        return values
    return []


async def validate_structured_output_before_finalize(
    input_data: PreToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> SyncHookJSONOutput:
    """不完全な structured output を deny し、LLM に継続調査を促す。"""
    del tool_use_id, context
    validation = validate_candidate_research_result(payload=input_data["tool_input"])
    if validation["ok"]:
        return {}

    warnings = "\n".join(f"- {warning}" for warning in validation["warnings"])
    return {
        "hookSpecificOutput": {
            "hookEventName": input_data["hook_event_name"],
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{INCOMPLETE_RESULT_REASON}\n"
                f"{REVIEW_OFFER_RULES_GUIDANCE}\n"
                f"{warnings}"
            ),
        }
    }


async def validate_bash_command_before_execute(
    input_data: PreToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> SyncHookJSONOutput:
    """巨大な本文ダンプを返す playwright-cli eval を拒否する。"""
    del tool_use_id, context
    command = _string_field(input_data.get("tool_input"), "command")
    if not _is_blocked_playwright_eval(command):
        return {}

    return {
        "hookSpecificOutput": {
            "hookEventName": input_data["hook_event_name"],
            "permissionDecision": "deny",
            "permissionDecisionReason": PLAYWRIGHT_EVAL_GUIDANCE,
        }
    }


async def validate_read_request_before_execute(
    input_data: PreToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> SyncHookJSONOutput:
    """Playwright snapshot YAML の直接 Read を拒否する。"""
    del tool_use_id, context
    file_path = _string_field(input_data.get("tool_input"), "file_path")
    if not _looks_like_playwright_snapshot(file_path):
        return {}

    return {
        "hookSpecificOutput": {
            "hookEventName": input_data["hook_event_name"],
            "permissionDecision": "deny",
            "permissionDecisionReason": PLAYWRIGHT_SNAPSHOT_READ_GUIDANCE,
        }
    }


def _is_blocked_playwright_eval(command: str) -> bool:
    """生の全文取得か head/tail 付き全文取得だけを拒否する。"""
    if not command:
        return False
    if not FULL_PAGE_TEXT_EVAL_PATTERN.search(command):
        return False
    if "|" not in command:
        return True
    return HEAD_OR_TAIL_PATTERN.search(command) is not None


def _looks_like_playwright_snapshot(file_path: str) -> bool:
    """snapshot accessibility tree YAML らしい Read 対象だけを検出する。"""
    if not file_path:
        return False
    path = Path(file_path)
    if path.suffix.lower() not in {".yml", ".yaml"}:
        return False
    if not path.exists() or not path.is_file():
        return False
    if path.suffix.lower() == ".yml" and ".playwright-cli" in path.parts:
        return path.stat().st_size > MAX_DIRECT_SNAPSHOT_READ_CHARS
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if len(content) <= MAX_DIRECT_SNAPSHOT_READ_CHARS:
        return False
    prefix = content[:512]
    return "[ref=" in prefix and prefix.lstrip().startswith("- ")


def _string_field(payload: Any, key: str) -> str:
    """dict-like payload から文字列値を取り出す。"""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get(key) or "")
