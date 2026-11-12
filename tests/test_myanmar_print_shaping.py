"""Myanmar vowel shaping for image-mode kitchen/cashier tickets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageChops

from services.printing.image_renderer import render_ticket_image
from services.printing.myanmar_shaper import (
    harfbuzz_available,
    raqm_available,
    render_shaped_text,
    shaping_backend,
)

PYIDAUNGSU = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Pyidaungsu.ttf"
# က + ေ (storage order); correct shaping places ေ to the left of က
MYANMAR_KE = "\u1000\u1031"
SAMPLE_MENU = "ဘောင်ဒရီ လက်ဖက်ရည်"


def test_shaping_backend_is_not_basic_when_engine_available():
    assert raqm_available() or harfbuzz_available()
    assert shaping_backend() in {"raqm", "harfbuzz"}


def test_shaped_e_vowel_differs_from_pillow_basic():
    assert PYIDAUNGSU.exists()
    shaped = render_shaped_text(MYANMAR_KE, str(PYIDAUNGSU), size=28)

    basic_font = ImageFont.truetype(
        str(PYIDAUNGSU),
        size=28,
        layout_engine=ImageFont.Layout.BASIC,
    )
    bbox = basic_font.getbbox(MYANMAR_KE)
    basic = Image.new("L", shaped.size, 255)
    draw = ImageDraw.Draw(basic)
    draw.text((-bbox[0], -bbox[1]), MYANMAR_KE, fill=0, font=basic_font)

    # Resize basic to shaped size for a fair-ish diff if bbox differs
    if basic.size != shaped.size:
        canvas = Image.new("L", shaped.size, 255)
        canvas.paste(basic, (0, 0))
        basic = canvas

    diff = ImageChops.difference(shaped, basic)
    changed = sum(1 for pixel in diff.getdata() if pixel)
    assert changed > 0, "shaped output must differ from unshaped BASIC layout"


def test_ticket_image_renders_myanmar_menu_line():
    image = render_ticket_image(
        f"{SAMPLE_MENU}\nGrand Total: 1.00\n",
        paper_width_px=576,
    )
    assert image.size[0] == 576
    assert image.size[1] > 0
    # Must contain black ink
    assert 0 in image.getdata()
