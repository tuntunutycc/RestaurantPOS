"""Render kitchen tickets as thermal-printer-friendly images."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

DEFAULT_FONT_SIZE = 28
LINE_GAP_PX = 8
PADDING_X_PX = 18
PADDING_Y_PX = 16
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUNDLED_FONT_DIRS = (
    PROJECT_ROOT / "assets" / "fonts",
    PROJECT_ROOT / "static" / "fonts",
)
PREFERRED_MYANMAR_FONT_NAMES = (
    "NotoSansMyanmar-Regular.ttf",
    "NotoSansMyanmar.ttf",
    "NotoSerifMyanmar-Regular.ttf",
    "Pyidaungsu.ttf",
    "Myanmar3.ttf",
)
SYSTEM_FONT_PATHS = (
    "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansMyanmar-Regular.otf",
    "/Library/Fonts/NotoSansMyanmar-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique_paths: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(path)
    return unique_paths


def _candidate_font_paths(font_path: str | None) -> list[Path]:
    candidates: list[Path] = []
    if font_path:
        candidates.append(Path(font_path))

    for font_dir in BUNDLED_FONT_DIRS:
        candidates.extend(font_dir / name for name in PREFERRED_MYANMAR_FONT_NAMES)

    for font_dir in BUNDLED_FONT_DIRS:
        if not font_dir.exists():
            continue
        candidates.extend(sorted(font_dir.glob("*Myanmar*.ttf")))
        candidates.extend(sorted(font_dir.glob("*Myanmar*.otf")))
        candidates.extend(sorted(font_dir.glob("*Pyidaungsu*.ttf")))
        candidates.extend(sorted(font_dir.glob("*Pyidaungsu*.otf")))

    candidates.extend(Path(path) for path in SYSTEM_FONT_PATHS)
    return _dedupe_paths(candidates)


def _load_font(font_path: str | None, size: int = DEFAULT_FONT_SIZE) -> ImageFont.ImageFont:
    for path in _candidate_font_paths(font_path):
        if not path.exists():
            continue
        try:
            font = ImageFont.truetype(str(path), size=size)
            logger.info("Loaded kitchen print font: %s", path)
            return font
        except OSError as exc:
            logger.warning("Unable to load kitchen print font %s: %s", path, exc)

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
