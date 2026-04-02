"""Infrastructure layer: in-process MCP tool for returning local images to Claude."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from claude_agent_sdk import tool
from mcp.server.fastmcp import Image
from mcp.types import ImageContent
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError

ReadImageArgs = TypedDict(  # noqa: UP013
    "ReadImageArgs",
    {
        "file_path": str,
        "crop_x": NotRequired[int],
        "crop_y": NotRequired[int],
        "crop_width": NotRequired[int],
        "crop_height": NotRequired[int],
    },
)


@dataclass(frozen=True, slots=True)
class CropRegion:
    """Rectangular crop region in source-image pixel coordinates."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """Reject negative positions and non-positive dimensions."""
        if self.x < 0 or self.y < 0:
            raise ValueError("crop coordinates must be zero or positive")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("crop dimensions must be positive")

    @property
    def right(self) -> int:
        """Return the exclusive right edge."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Return the exclusive bottom edge."""
        return self.y + self.height


@tool(
    "ReadImage",
    "Return one local image file directly to Claude. You may optionally request a cropped region.",
    ReadImageArgs,
)
async def READ_IMAGE_TOOL(args: ReadImageArgs) -> dict[str, object]:
    """Return one local image, or a cropped region, as MCP image content."""
    image_content = build_read_image_content(args=args)
    return {
        "content": [
            {
                "type": image_content.type,
                "data": image_content.data,
                "mimeType": image_content.mimeType,
            }
        ]
    }


def build_read_image_content(*, args: ReadImageArgs) -> ImageContent:
    """Build one MCP image content payload from tool arguments."""
    source_path = _resolve_image_path(args["file_path"])
    crop_region = _build_crop_region(args=args)
    if crop_region is None:
        return cast(ImageContent, Image(path=source_path).to_image_content())
    return cast(
        ImageContent,
        Image(
        data=_crop_image(source_path=source_path, crop_region=crop_region),
        format="png",
        ).to_image_content(),
    )


def _resolve_image_path(file_path: str) -> Path:
    """Resolve and validate one local image file path."""
    source_path = Path(file_path).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(source_path)
    try:
        with PillowImage.open(source_path) as image:
            image.load()
    except UnidentifiedImageError as exc:
        raise ValueError(f"not an image file: {source_path}") from exc
    return source_path


def _build_crop_region(*, args: ReadImageArgs) -> CropRegion | None:
    """Convert optional crop arguments into a validated crop region."""
    crop_x = args.get("crop_x")
    crop_y = args.get("crop_y")
    crop_width = args.get("crop_width")
    crop_height = args.get("crop_height")
    crop_values = (crop_x, crop_y, crop_width, crop_height)
    if any(value is not None for value in crop_values) and not all(
        value is not None for value in crop_values
    ):
        raise ValueError("crop_x, crop_y, crop_width, and crop_height must be provided together")
    if crop_x is None:
        return None
    assert crop_y is not None
    assert crop_width is not None
    assert crop_height is not None
    return CropRegion(
        x=crop_x,
        y=crop_y,
        width=crop_width,
        height=crop_height,
    )


def _crop_image(*, source_path: Path, crop_region: CropRegion) -> bytes:
    """Crop one source image and return the cropped PNG bytes."""
    with PillowImage.open(source_path) as image:
        image.load()
        image_width, image_height = image.size
        if crop_region.right > image_width or crop_region.bottom > image_height:
            raise ValueError("crop region falls outside the source image")
        cropped_image = image.crop(
            (crop_region.x, crop_region.y, crop_region.right, crop_region.bottom)
        )
        output_buffer = BytesIO()
        cropped_image.save(output_buffer, format="PNG")
    return output_buffer.getvalue()
