"""Kitchen ticket text and ESC/POS payload builders."""

from __future__ import annotations

from PIL import Image


def build_ticket_text(
    *,
    route: str,
    item_name: str,
    quantity: int,
    note: str | None,
    table_number: str | int | None,
    order_id: int,
    created_at: str,
    order_type: str = "dine_in",
    customer_name: str | None = None,
) -> str:
    note_value = (note or "").strip()
    normalized_order_type = (order_type or "dine_in").strip().lower()
    customer = (customer_name or "").strip() or "Walk-in"

    if normalized_order_type == "takeaway":
        header_block = (
            "=================================\n"
            "  [ *** TAKEAWAY / ပါဆယ် *** ]\n"
            f"  Takeaway #{order_id}\n"
            f"  Customer: {customer}\n"
            "=================================\n"
        )
    else:
        header_block = f"Table: {table_number or ''}\n"

    lines = [
        "=== KITCHEN ITEM TICKET ===",
        f"Route: {route}",
        header_block.rstrip("\n"),
        f"Order: #{order_id}",
        f"Time: {created_at}",
        "---------------------------------",
        f"{quantity}x {item_name}",
    ]
    if note_value:
        lines.append(f"   *** Note: {note_value} ***")
    lines.extend(["---------------------------------", "[ --- CUT TICKET --- ]", ""])
    return "\n".join(lines)


def build_escpos_text_payload(text: str) -> bytes:
    """Minimal ESC/POS payload: initialize, UTF-8 text, feed, full cut."""
    payload = bytearray()
    payload.extend(b"\x1b\x40")  # ESC @ initialize
    payload.extend(text.encode("utf-8"))
    payload.extend(b"\n\n")
    payload.extend(b"\x1d\x56\x00")  # GS V 0 full cut
    return bytes(payload)


def build_escpos_payload(text: str) -> bytes:
    """Backward-compatible alias for text payloads."""
    return build_escpos_text_payload(text)


def build_escpos_raster_payload(image: Image.Image) -> bytes:
    """Build an ESC/POS GS v 0 raster payload from a 1-bit thermal image."""
    bw = image.convert("1")
    width, height = bw.size
    width_bytes = (width + 7) // 8
    x_l = width_bytes % 256
    x_h = width_bytes // 256
    y_l = height % 256
    y_h = height // 256

    pixels = bw.load()
    raster = bytearray()
    for y in range(height):
        for byte_x in range(width_bytes):
            value = 0
            for bit in range(8):
                x = byte_x * 8 + bit
                if x < width and pixels[x, y] == 0:
                    value |= 0x80 >> bit
            raster.append(value)

    payload = bytearray()
    payload.extend(b"\x1b\x40")  # initialize
    payload.extend(b"\x1d\x76\x30\x00")  # GS v 0, normal raster mode
    payload.extend(bytes([x_l, x_h, y_l, y_h]))
    payload.extend(raster)
    payload.extend(b"\n\n")
    payload.extend(b"\x1d\x56\x00")  # full cut
    return bytes(payload)
