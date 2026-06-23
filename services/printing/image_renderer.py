"""Render kitchen tickets as thermal-printer-friendly images."""

from __future__ import annotations

import logging
import os

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

DEFAULT_FONT_SIZE = 28
LINE_GAP_PX = 8
PADDING_X_PX = 18
PADDING_Y_PX = 16


def _load_font(font_path: str | None, size: int = DEFAULT_FONT_SIZE) -> ImageFont.ImageFont:
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError as exc:
            logger.warning("Unable to load kitchen print font %s: %s", font_path, exc)

    # Common fallback paths. A bundled font can be supplied later without changing code.
    fallback_paths = [
        "assets/fonts/NotoSansMyanmar-Regular.ttf",
        "static/fonts/NotoSansMyanmar-Regular.ttf",
        "/Library/Fonts/NotoSansMyanmar-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in fallback_paths:
        if not os.path.exists(path):
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue

    logger.warning("No Myanmar-capable kitchen print font found; using Pillow default font")
    return ImageFont.load_default()


def render_ticket_image(
    ticket_text: str,
    *,
    paper_width_px: int = 576,
    font_path: str | None = None,
) -> Image.Image:
    """Render ticket text to a 1-bit image suitable for ESC/POS raster printing."""
    width = paper_width_px if paper_width_px in (384, 576) else 576
    font = _load_font(font_path)
    lines = ticket_text.rstrip("\n").splitlines() or [""]

    probe = Image.new("L", (width, 10), 255)
    draw = ImageDraw.Draw(probe)
    line_heights: list[int] = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line or " ", font=font)
        line_heights.append(max(bbox[3] - bbox[1], DEFAULT_FONT_SIZE))

    height = PADDING_Y_PX * 2 + sum(line_heights) + (len(lines) - 1) * LINE_GAP_PX
    image = Image.new("L", (width, max(height, 1)), 255)
    draw = ImageDraw.Draw(image)

    y = PADDING_Y_PX
    for line, line_height in zip(lines, line_heights, strict=True):
        draw.text((PADDING_X_PX, y), line, fill=0, font=font)
        y += line_height + LINE_GAP_PX

    return image.convert("1")
