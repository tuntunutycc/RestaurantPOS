"""Myanmar (and other complex-script) text shaping for thermal print images.

Pillow BASIC layout leaves Myanmar vowels (especially U+1031 ေ) in storage
order. Prefer Pillow RAQM when available; otherwise shape with HarfBuzz and
rasterize glyphs via FreeType.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

logger = logging.getLogger(__name__)

try:
    import uharfbuzz as hb
except ImportError:  # pragma: no cover - optional until installed
    hb = None

try:
    from freetype import FT_LOAD_RENDER, Face
except ImportError:  # pragma: no cover - optional until installed
    Face = None
    FT_LOAD_RENDER = None


def raqm_available() -> bool:
    try:
        return bool(features.check("raqm"))
    except Exception:
        return False


def harfbuzz_available() -> bool:
    return hb is not None and Face is not None


def shaping_backend() -> str:
    if raqm_available():
        return "raqm"
    if harfbuzz_available():
        return "harfbuzz"
    return "basic"


def load_truetype(
    path: str | Path,
    *,
    size: int,
) -> ImageFont.ImageFont:
    """Load a Pillow font, forcing RAQM when the build supports it."""
    path_str = str(path)
    if raqm_available():
        return ImageFont.truetype(
            path_str,
            size=size,
            layout_engine=ImageFont.Layout.RAQM,
        )
    return ImageFont.truetype(path_str, size=size)


@lru_cache(maxsize=8)
def _hb_font(font_path: str, size: int):
    assert hb is not None
    data = Path(font_path).read_bytes()
    face = hb.Face(hb.Blob(data))
    font = hb.Font(face)
    font.scale = (size * 64, size * 64)
    return font


@lru_cache(maxsize=8)
def _ft_face(font_path: str, size: int):
    assert Face is not None
    face = Face(font_path)
    face.set_char_size(size * 64)
    return face


def shape_text_width(text: str, font_path: str, *, size: int) -> int:
    """Advance width in pixels after HarfBuzz shaping."""
    if not text:
        return 0
    if not harfbuzz_available():
        font = load_truetype(font_path, size=size)
        bbox = font.getbbox(text)
        return max(bbox[2] - bbox[0], 0)
    font = _hb_font(font_path, size)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return max(sum(pos.x_advance for pos in buf.glyph_positions) // 64, 0)


def render_shaped_text(
    text: str,
    font_path: str,
    *,
    size: int,
) -> Image.Image:
    """Render ``text`` to an L-mode mask (white bg, black ink) with shaping.

    Prefers Pillow RAQM. Falls back to HarfBuzz + FreeType. Last resort is
    Pillow BASIC (incorrect Myanmar vowels).
    """
    if not text:
        return Image.new("L", (1, size), 255)

    backend = shaping_backend()
    if backend == "raqm":
        font = load_truetype(font_path, size=size)
        bbox = font.getbbox(text)
        left, top, right, bottom = bbox
        width = max(right - left, 1)
        height = max(bottom - top, size)
        image = Image.new("L", (width, height), 255)
        draw = ImageDraw.Draw(image)
        draw.text((-left, -top), text, fill=0, font=font)
        return image

    if backend == "harfbuzz":
        return _render_with_harfbuzz(text, font_path, size=size)

    logger.warning(
        "Myanmar print shaping unavailable (no RAQM/HarfBuzz); "
        "vowels like U+1031 may appear in the wrong place"
    )
    font = load_truetype(font_path, size=size)
    bbox = font.getbbox(text)
    left, top, right, bottom = bbox
    width = max(right - left, 1)
    height = max(bottom - top, size)
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    draw.text((-left, -top), text, fill=0, font=font)
    return image


def _render_with_harfbuzz(text: str, font_path: str, *, size: int) -> Image.Image:
    assert hb is not None and Face is not None and FT_LOAD_RENDER is not None
    hb_font = _hb_font(font_path, size)
    ft_face = _ft_face(font_path, size)

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf)
    infos = buf.glyph_infos
    positions = buf.glyph_positions

    # Measure ink bounds in pixel space before allocating the canvas.
    min_x = 0
    min_y = 0
    max_x = 0
    max_y = size
    pen_x = 0
    baseline = size
    glyph_blits: list[tuple[Image.Image, int, int]] = []

    for info, pos in zip(infos, positions, strict=True):
        ft_face.load_glyph(info.codepoint, FT_LOAD_RENDER)
        bitmap = ft_face.glyph.bitmap
        w, h = bitmap.width, bitmap.rows
        gx = pen_x + (pos.x_offset // 64) + ft_face.glyph.bitmap_left
        gy = baseline - (pos.y_offset // 64) - ft_face.glyph.bitmap_top
        if w and h:
            pitch = bitmap.pitch
            raw = bytes(bitmap.buffer)
            if pitch == w:
                data = raw
            else:
                data = b"".join(raw[row : row + w] for row in range(0, pitch * h, pitch))
            glyph = Image.frombytes("L", (w, h), data)
            glyph_blits.append((glyph, gx, gy))
            min_x = min(min_x, gx)
            min_y = min(min_y, gy)
            max_x = max(max_x, gx + w)
            max_y = max(max_y, gy + h)
        pen_x += pos.x_advance // 64
        max_x = max(max_x, pen_x)

    width = max(max_x - min_x, 1)
    height = max(max_y - min_y, 1)
    image = Image.new("L", (width, height), 255)
    origin_x = -min_x
    origin_y = -min_y

    for glyph, gx, gy in glyph_blits:
        _blit_coverage(image, glyph, origin_x + gx, origin_y + gy)

    return image


def _blit_coverage(
    canvas: Image.Image,
    coverage: Image.Image,
    x: int,
    y: int,
) -> None:
    """Alpha-blend FreeType coverage glyph onto a white L canvas as black ink."""
    cw, ch = canvas.size
    gw, gh = coverage.size
    canvas_px = canvas.load()
    cov_px = coverage.load()
    for row in range(gh):
        py = y + row
        if py < 0 or py >= ch:
            continue
        for col in range(gw):
            px = x + col
            if px < 0 or px >= cw:
                continue
            cov = cov_px[col, row]
            if not cov:
                continue
            cur = canvas_px[px, py]
            # coverage 255 → full black (0)
            canvas_px[px, py] = (cur * (255 - cov)) // 255
