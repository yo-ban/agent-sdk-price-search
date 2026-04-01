"""Projection tests for launcher-backed run timeline entries."""

from __future__ import annotations

from price_search_web_api.adapters.run_timeline_projection import build_run_timeline


def test_build_run_timeline_labels_tool_results_with_matching_tool_name() -> None:
    """Tool results should reuse the corresponding assistant tool name when present."""
    timeline = build_run_timeline(
        log_events=(
            {
                "logged_at": "2026-03-29T00:00:00+00:00",
                "event_type": "assistant_message",
                "payload": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_query",
                            "name": "Bash",
                            "input": {"command": "searxng-search ..."},
                        }
                    ]
                },
            },
            {
                "logged_at": "2026-03-29T00:00:01+00:00",
                "event_type": "user_message",
                "payload": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_query",
                            "content": '{"query":"全自動コーヒーメーカー ABC-1234 価格","results":[]}',
                        }
                    ]
                },
            },
        ),
        started_at_ms=0,
    )

    assert timeline[-1].label == "Tool Result: Bash"
    assert "全自動コーヒーメーカー ABC-1234 価格" in timeline[-1].detail


def test_build_run_timeline_marks_skill_instruction_messages_as_system_entries() -> None:
    """Skill bootstrap text should be labeled separately from plain user messages."""
    timeline = build_run_timeline(
        log_events=(
            {
                "logged_at": "2026-03-29T00:00:00+00:00",
                "event_type": "user_message",
                "payload": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Base directory for this skill: "
                                "/tmp/workspace/.claude/skills/playwright-cli-skill\n\n"
                                "# Browser Automation with playwright-cli"
                            ),
                        }
                    ]
                },
            },
        ),
        started_at_ms=0,
    )

    assert timeline[0].kind == "system"
    assert timeline[0].label == "Skill Instructions: playwright-cli-skill"


def test_build_run_timeline_extracts_tool_result_images() -> None:
    """Image blocks inside tool results should become previewable timeline images."""
    timeline = build_run_timeline(
        log_events=(
            {
                "logged_at": "2026-03-29T00:00:00+00:00",
                "event_type": "user_message",
                "payload": {
                    "tool_use_result": {
                        "type": "image",
                        "file": {
                            "base64": "AAAA",
                            "type": "image/png",
                            "originalSize": 191080,
                        },
                    },
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_image",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": "AAAA",
                                    },
                                }
                            ],
                        }
                    ],
                },
            },
        ),
        started_at_ms=0,
    )

    assert timeline[0].detail == ""
    assert len(timeline[0].images) == 1
    assert timeline[0].images[0].media_type == "image/png"
    assert timeline[0].images[0].src == "data:image/png;base64,AAAA"


def test_build_run_timeline_uses_headings_for_assistant_text_labels() -> None:
    """Assistant markdown headings should become stable timeline labels."""
    timeline = build_run_timeline(
        log_events=(
            {
                "logged_at": "2026-03-29T00:00:00+00:00",
                "event_type": "assistant_message",
                "payload": {
                    "content": [
                        {"type": "text", "text": "I found several candidate offers."},
                        {"type": "text", "text": "## Summary\n\nThe best offer is from Amazon."},
                    ]
                },
            },
        ),
        started_at_ms=0,
    )

    assert timeline[0].label == "Assistant Message"
    assert timeline[1].label == "Summary"
