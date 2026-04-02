"""Infrastructure helpers for extracting safe image previews from activity logs."""

from __future__ import annotations

from typing import Any

from price_search_web_api.contracts.run_snapshot import TimelineImage


def extract_timeline_images(*values: Any) -> tuple[TimelineImage, ...]:
    """Extract normalized inline image previews from known content-block shapes."""
    images: list[TimelineImage] = []
    seen_sources: set[str] = set()
    for value in values:
        _collect_known_blocks(value=value, images=images, seen_sources=seen_sources)
    return tuple(images)


def _collect_known_blocks(
    *,
    value: Any,
    images: list[TimelineImage],
    seen_sources: set[str],
) -> None:
    """Collect images only from known content block containers."""
    if isinstance(value, list | tuple):
        for item in value:
            _collect_known_blocks(
                value=item,
                images=images,
                seen_sources=seen_sources,
            )
        return

    if not isinstance(value, dict):
        return

    image = _timeline_image_from_block(value)
    if image is not None:
        _append_image(image=image, images=images, seen_sources=seen_sources)
        return

    if value.get("type") == "tool_result":
        _collect_known_blocks(
            value=value.get("content"),
            images=images,
            seen_sources=seen_sources,
        )


def _append_image(
    *,
    image: TimelineImage,
    images: list[TimelineImage],
    seen_sources: set[str],
) -> None:
    """Append one image if it has not been seen already."""
    if image.src in seen_sources:
        return
    seen_sources.add(image.src)
    images.append(image)


def _timeline_image_from_block(block: dict[str, Any]) -> TimelineImage | None:
    """Normalize one supported image payload into a preview."""
    block_type = str(block.get("type") or "").strip().lower()
    if block_type != "image":
        return None

    source_payload = block.get("source")
    if isinstance(source_payload, dict):
        source_src = _normalize_inline_image_src(
            media_type=source_payload.get("media_type"),
            data=source_payload.get("data"),
        )
        if source_src is not None and str(source_payload.get("type") or "").strip() == "base64":
            return TimelineImage(
                src=source_src,
                media_type=_normalize_media_type(source_payload.get("media_type")),
            )

    file_payload = block.get("file")
    if isinstance(file_payload, dict):
        file_src = _normalize_inline_image_src(
            media_type=file_payload.get("type"),
            data=file_payload.get("base64"),
        )
        if file_src is not None:
            return TimelineImage(
                src=file_src,
                media_type=_normalize_media_type(file_payload.get("type")),
            )

    return None


def _normalize_inline_image_src(
    *,
    media_type: Any,
    data: Any,
) -> str | None:
    """Normalize an inline base64 payload into a data URL."""
    if isinstance(data, str) and data.strip():
        return f"data:{_normalize_media_type(media_type)};base64,{data.strip()}"
    return None


def _normalize_media_type(value: Any) -> str:
    """Return a safe image media type for browser rendering."""
    if isinstance(value, str) and value.strip().startswith("image/"):
        return value.strip()
    return "image/png"
