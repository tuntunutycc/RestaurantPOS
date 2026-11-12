"""Render kitchen tickets as thermal-printer-friendly images."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from services.printing.print_log import ensure_print_file_logging

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
    "Pyidaungsu.ttf",
    "Pyidaungsu-2.5.3_Regular.ttf",
    "Pyidaungsu Regular.ttf",
    "NotoSansMyanmar-Regular.ttf",
    "NotoSansMyanmar.ttf",
    "NotoSerifMyanmar-Regular.ttf",
    "Myanmar3.ttf",
)
PREFERRED_LATIN_FONT_NAMES = (
    "NotoSans-Regular.ttf",
    "NotoSans.ttf",
    "DejaVuSans.ttf",
    "Arial.ttf",
)
SYSTEM_MYANMAR_FONT_PATHS = (
    "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansMyanmar-Regular.otf",
    "/Library/Fonts/NotoSansMyanmar-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)
SYSTEM_LATIN_FONT_PATHS = (
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
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


def _looks_like_myanmar_font(path: Path) -> bool:
    """Match common Myanmar font downloads, including spaced/versioned names."""
    stem = path.stem.lower().replace(" ", "").replace("-", "").replace("_", "")
    return (
        "pyidaungsu" in stem
        or "myanmar" in stem
        or stem.startswith("myanmar3")
    )


def _candidate_font_paths(font_path: str | None) -> list[Path]:
    candidates: list[Path] = []
    if font_path:
        candidates.append(Path(font_path))

    for font_dir in BUNDLED_FONT_DIRS:
        candidates.extend(font_dir / name for name in PREFERRED_MYANMAR_FONT_NAMES)

    for font_dir in BUNDLED_FONT_DIRS:
        if not font_dir.exists():
            continue
        for path in sorted(font_dir.iterdir()):
            if path.suffix.lower() not in {".ttf", ".otf"}:
                continue
            if _looks_like_myanmar_font(path):
                candidates.append(path)

    candidates.extend(Path(path) for path in SYSTEM_MYANMAR_FONT_PATHS)
    return _dedupe_paths(candidates)


def _candidate_latin_font_paths() -> list[Path]:
    candidates: list[Path] = []
    for font_dir in BUNDLED_FONT_DIRS:
        candidates.extend(font_dir / name for name in PREFERRED_LATIN_FONT_NAMES)

    for font_dir in BUNDLED_FONT_DIRS:
        if not font_dir.exists():
            continue
        candidates.extend(sorted(font_dir.glob("*NotoSans*.ttf")))
        candidates.extend(sorted(font_dir.glob("*NotoSans*.otf")))
        candidates.extend(sorted(font_dir.glob("*DejaVuSans*.ttf")))
        candidates.extend(sorted(font_dir.glob("*DejaVuSans*.otf")))

    candidates.extend(Path(path) for path in SYSTEM_LATIN_FONT_PATHS)
    return _dedupe_paths(candidates)


def _load_first_font(
    paths: list[Path],
    *,
    size: int,
    label: str,
) -> ImageFont.ImageFont | None:
    ensure_print_file_logging()
    existing = [path for path in paths if path.exists()]
    logger.info(
        "Font search label=%s candidates=%s existing=%s",
        label,
        len(paths),
        [str(path) for path in existing[:8]],
    )
    for path in paths:
        if not path.exists():
            continue
        try:
            font = ImageFont.truetype(str(path), size=size)
            logger.info("Loaded kitchen print %s font: %s", label, path)
            return font
        except OSError as exc:
            logger.warning("Unable to load kitchen print font %s: %s", path, exc)
    return None


def _load_font(font_path: str | None, size: int = DEFAULT_FONT_SIZE) -> ImageFont.ImageFont:
    ensure_print_file_logging()
    font = _load_first_font(_candidate_font_paths(font_path), size=size, label="Myanmar")
    if font is not None:
        return font

    logger.warning(
        "No Myanmar-capable kitchen print font found; using Pillow default font. "
        "Place Pyidaungsu.ttf under assets/fonts and use render_mode=image."
    )
    return ImageFont.load_default()


def _load_font_chain(
    font_path: str | None,
    size: int = DEFAULT_FONT_SIZE,
) -> tuple[ImageFont.ImageFont, ImageFont.ImageFont]:
    myanmar_font = _load_font(font_path, size=size)
    latin_font = _load_first_font(
        _candidate_latin_font_paths(),
        size=size,
        label="Latin fallback",
    )
    if latin_font is None:
        logger.warning("No kitchen print Latin fallback font found; using Myanmar/default font")
        latin_font = myanmar_font
    return myanmar_font, latin_font


def _is_myanmar_char(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x1000 <= codepoint <= 0x109F
        or 0xAA60 <= codepoint <= 0xAA7F
        or 0xA9E0 <= codepoint <= 0xA9FF
    )


def _font_for_char(
    char: str,
    myanmar_font: ImageFont.ImageFont,
    latin_font: ImageFont.ImageFont,
) -> ImageFont.ImageFont:
    if _is_myanmar_char(char):
        return myanmar_font
    return latin_font


def _line_runs(
    line: str,
    myanmar_font: ImageFont.ImageFont,
    latin_font: ImageFont.ImageFont,
) -> list[tuple[str, ImageFont.ImageFont]]:
    runs: list[tuple[str, ImageFont.ImageFont]] = []
    current_text = ""
    current_font: ImageFont.ImageFont | None = None
    for char in line:
        font = _font_for_char(char, myanmar_font, latin_font)
        if current_font is None or font is current_font:
            current_text += char
            current_font = font
            continue
        runs.append((current_text, current_font))
        current_text = char
        current_font = font
    if current_text and current_font is not None:
        runs.append((current_text, current_font))
    return runs


def _text_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> tuple[int, int, int, int]:
    return draw.textbbox((0, 0), text or " ", font=font)


def _measure_line(
    draw: ImageDraw.ImageDraw,
    line: str,
    myanmar_font: ImageFont.ImageFont,
    latin_font: ImageFont.ImageFont,
) -> tuple[int, int]:
    runs = _line_runs(line or " ", myanmar_font, latin_font)
    width = 0
    height = DEFAULT_FONT_SIZE
    for text, font in runs:
        bbox = _text_bbox(draw, text, font)
        width += max(bbox[2] - bbox[0], 0)
        height = max(height, bbox[3] - bbox[1])
    return width, height


def _draw_line(
    draw: ImageDraw.ImageDraw,
    line: str,
    *,
    x: int,
    y: int,
    myanmar_font: ImageFont.ImageFont,
    latin_font: ImageFont.ImageFont,
) -> None:
    cursor_x = x
    for text, font in _line_runs(line or " ", myanmar_font, latin_font):
        bbox = _text_bbox(draw, text, font)
        draw.text((cursor_x - bbox[0], y - bbox[1]), text, fill=0, font=font)
        cursor_x += max(bbox[2] - bbox[0], 0)


def render_ticket_image(
    ticket_text: str,
    *,
    paper_width_px: int = 576,
    font_path: str | None = None,
) -> Image.Image:
    """Render ticket text to a 1-bit image suitable for ESC/POS raster printing."""
    width = paper_width_px if paper_width_px in (384, 576) else 576
    logger.info(
        "Rendering print image width_px=%s font_path_override=%s",
        width,
        font_path or "(auto)",
    )
    myanmar_font, latin_font = _load_font_chain(font_path)
    lines = ticket_text.rstrip("\n").splitlines() or [""]

    probe = Image.new("L", (width, 10), 255)
    draw = ImageDraw.Draw(probe)
    line_heights: list[int] = []
    for line in lines:
        _line_width, line_height = _measure_line(draw, line, myanmar_font, latin_font)
        line_heights.append(line_height)

    height = PADDING_Y_PX * 2 + sum(line_heights) + (len(lines) - 1) * LINE_GAP_PX
    image = Image.new("L", (width, max(height, 1)), 255)
    draw = ImageDraw.Draw(image)

    y = PADDING_Y_PX
    for line, line_height in zip(lines, line_heights, strict=True):
        _draw_line(
            draw,
            line,
            x=PADDING_X_PX,
            y=y,
            myanmar_font=myanmar_font,
            latin_font=latin_font,
        )
        y += line_height + LINE_GAP_PX

    return image.convert("1")
