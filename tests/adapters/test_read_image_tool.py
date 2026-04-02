"""Tests for the public ReadImage MCP tool."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from PIL import Image as PillowImage
from price_search.adapters.claude_sdk.read_image_tool import READ_IMAGE_TOOL


def test_read_image_returns_original_image_when_no_crop_is_requested(tmp_path: Path) -> None:
    """The tool should return the original image content when crop args are absent."""
    source_size = (48, 32)
    image_path = _create_test_image(tmp_path=tmp_path, image_size=source_size)

    result = _invoke_tool({"file_path": str(image_path)})
    content = cast(list[dict[str, str]], result["content"])[0]

    assert _decoded_image_size(content["data"]) == source_size


def test_read_image_returns_requested_crop_region(tmp_path: Path) -> None:
    """The tool should return only the requested crop region when crop args are provided."""
    source_size = (64, 40)
    crop_region = {"x": 7, "y": 5, "width": 19, "height": 11}
    image_path = _create_test_image(tmp_path=tmp_path, image_size=source_size)

    result = _invoke_tool(
        {
            "file_path": str(image_path),
            "crop_x": crop_region["x"],
            "crop_y": crop_region["y"],
            "crop_width": crop_region["width"],
            "crop_height": crop_region["height"],
        }
    )
    content = cast(list[dict[str, str]], result["content"])[0]

    assert _decoded_image_size(content["data"]) == (
        crop_region["width"],
        crop_region["height"],
    )


def test_read_image_rejects_partial_crop_arguments(tmp_path: Path) -> None:
    """The tool should reject incomplete crop argument sets."""
    image_path = _create_test_image(tmp_path=tmp_path, image_size=(30, 20))

    try:
        _invoke_tool(
            {
                "file_path": str(image_path),
                "crop_x": 2,
                "crop_y": 3,
            }
        )
    except ValueError:
        return

    raise AssertionError("expected ValueError for partial crop arguments")


def _create_test_image(*, tmp_path: Path, image_size: tuple[int, int]) -> Path:
    """Create one deterministic PNG image for the tool tests."""
    image_path = tmp_path / "test-image.png"
    PillowImage.new("RGB", image_size, color=(20, 40, 60)).save(image_path)
    return image_path


def _decoded_image_size(encoded_image_data: str) -> tuple[int, int]:
    """Decode one base64 image payload and return its pixel size."""
    image_bytes = base64.b64decode(encoded_image_data)
    with PillowImage.open(BytesIO(image_bytes)) as image:
        image.load()
        return image.size


def _invoke_tool(arguments: dict[str, object]) -> dict[str, Any]:
    """Call the decorated tool handler directly and return its MCP-style payload."""
    import asyncio

    async def _invoke() -> dict[str, Any]:
        return await READ_IMAGE_TOOL.handler(arguments)

    return asyncio.run(_invoke())
