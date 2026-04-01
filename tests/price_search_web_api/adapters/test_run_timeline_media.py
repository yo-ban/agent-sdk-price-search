"""Tests for safe timeline image extraction."""

from __future__ import annotations

from price_search_web_api.adapters.run_timeline_media import extract_timeline_images


def test_extract_timeline_images_accepts_tool_use_result_file_payload() -> None:
    """Real activity logs store previewable images under tool_use_result.file.base64."""
    images = extract_timeline_images(
        {
            "type": "image",
            "file": {
                "base64": "BBBB",
                "type": "image/png",
                "originalSize": 191080,
            },
        }
    )

    assert len(images) == 1
    assert images[0].src == "data:image/png;base64,BBBB"
    assert images[0].media_type == "image/png"


def test_extract_timeline_images_ignores_top_level_data_payloads() -> None:
    """Top-level image blocks without file.base64 should not drive previews."""
    images = extract_timeline_images(
        {"type": "image", "media_type": "image/png", "data": "AAAA"}
    )

    assert images == ()


def test_extract_timeline_images_rejects_external_urls() -> None:
    """External image URLs should not be passed through to the browser."""
    images = extract_timeline_images(
        {"type": "image", "file": {"image_url": "https://example.com/preview.png", "type": "image/png"}}
    )

    assert images == ()


def test_extract_timeline_images_ignores_tool_result_source_payloads() -> None:
    """Nested tool_result image payloads should not drive previews."""
    images = extract_timeline_images(
        [
            {
                "type": "tool_result",
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
        ]
    )

    assert images == ()


def test_extract_timeline_images_ignores_unrelated_nested_dicts() -> None:
    """Only supported image block containers should be inspected."""
    images = extract_timeline_images(
        {
            "tool_use_result": {
                "metadata": {
                    "type": "image",
                    "data": "AAAA",
                    "media_type": "image/png",
                }
            }
        }
    )

    assert images == ()
