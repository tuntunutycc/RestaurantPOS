"""Kitchen ticket text and ESC/POS payload builders."""

from __future__ import annotations

from PIL import Image

# A ticket line starting with this marker is a banner. It is printed large and
# inverted (image mode, ESC/POS text) or as a framed block (plain text files),
# so it cannot be overlooked. Used for "COPY n / N" on kitchen slip copies.
BANNER_PREFIX = "@@BANNER@@ "
TICKET_TEXT_WIDTH = 33


def banner_line(text: str) -> str:
    return f"{BANNER_PREFIX}{text.strip()}"


def is_banner_line(line: str) -> bool:
    return line.startswith(BANNER_PREFIX)


def banner_text(line: str) -> str:
    return line[len(BANNER_PREFIX):].strip()


def copy_banner_text(copy_number: int, copy_total: int) -> str:
    return f"COPY {copy_number} / {copy_total}"


def plain_ticket_text(text: str) -> str:
    """Ticket text for plain files: each banner becomes a framed three-line block."""
    if BANNER_PREFIX not in text:
        return text
    edge = "#" * TICKET_TEXT_WIDTH
    out: list[str] = []
    for line in text.split("\n"):
        if is_banner_line(line):
            out.extend([edge, f"###{banner_text(line).center(TICKET_TEXT_WIDTH - 6)}###", edge])
        else:
            out.append(line)
    return "\n".join(out)


def _modifier_ticket_lines(selected_modifiers) -> list[str]:
    """Pattern A: list each topping under the parent item."""
    lines: list[str] = []
    for raw in selected_modifiers or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        try:
            qty = int(raw.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1
        if qty < 1:
            qty = 1
        if qty == 1:
            lines.append(f"   + {name}")
        else:
            lines.append(f"   + {name} x{qty}")
    return lines


def _ticket_header_lines(
    *,
    route: str,
    table_number: str | int | None,
    order_id: int,
    created_at: str,
    order_type: str = "dine_in",
    customer_name: str | None = None,
    title: str = "=== KITCHEN TICKET ===",
) -> list[str]:
    normalized_order_type = (order_type or "dine_in").strip().lower()
    customer = (customer_name or "").strip() or "Walk-in"

    if normalized_order_type == "takeaway":
        header_block = (
            "=================================\n"
            "  [ *** TAKEAWAY / ပါဆယ် *** ]\n"
            f"  Takeaway #{order_id}\n"
            f"  Customer: {customer}\n"
            "================================="
        )
    else:
        header_block = f"Table: {table_number or ''}"

    return [
        title,
        f"Route: {route}",
        header_block,
        f"Order: #{order_id}",
        f"Time: {created_at}",
        "---------------------------------",
    ]


def _item_body_lines(
    *,
    item_name: str,
    quantity: int,
    note: str | None = None,
    selected_modifiers=None,
    is_takeaway: bool = False,
) -> list[str]:
    note_value = (note or "").strip()
    name = f"{item_name} (ပါဆယ်)" if is_takeaway else item_name
    lines = [f"{quantity}x {name}"]
    lines.extend(_modifier_ticket_lines(selected_modifiers))
    if note_value:
        lines.append(f"   *** Note: {note_value} ***")
    return lines


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
    selected_modifiers=None,
    is_takeaway: bool = False,
) -> str:
    """Single-item kitchen ticket (kept for compatibility / unit tests)."""
    lines = _ticket_header_lines(
        route=route,
        table_number=table_number,
        order_id=order_id,
        created_at=created_at,
        order_type=order_type,
        customer_name=customer_name,
        title="=== KITCHEN ITEM TICKET ===",
    )
    lines.extend(
        _item_body_lines(
            item_name=item_name,
            quantity=quantity,
            note=note,
            selected_modifiers=selected_modifiers,
            is_takeaway=is_takeaway,
        )
    )
    lines.extend(["---------------------------------", "[ --- CUT TICKET --- ]", ""])
    return "\n".join(lines)


def build_batch_ticket_text(
    *,
    route: str,
    items: list[dict],
    table_number: str | int | None,
    order_id: int,
    created_at: str,
    order_type: str = "dine_in",
    customer_name: str | None = None,
    batch_number: int | None = None,
    copy_number: int | None = None,
    copy_total: int | None = None,
) -> str:
    """One combined kitchen slip for a submit batch (no prices).

    ``items`` entries: item_name, quantity, note?, selected_modifiers?, is_takeaway?
    With ``copy_total`` > 1 the slip starts with a ``COPY n / N`` banner.
    """
    lines = _ticket_header_lines(
        route=route,
        table_number=table_number,
        order_id=order_id,
        created_at=created_at,
        order_type=order_type,
        customer_name=customer_name,
        title="=== KITCHEN TICKET ===",
    )
    if batch_number is not None:
        # Insert batch after Time line (index 4 is Time, 5 is separator)
        lines.insert(5, f"Batch: #{batch_number}")
    if copy_number and copy_total and int(copy_total) > 1:
        lines.insert(0, banner_line(copy_banner_text(int(copy_number), int(copy_total))))

    body_items = list(items or [])
    if not body_items:
        lines.append("(no items)")
    else:
        for index, raw in enumerate(body_items):
            if index > 0:
                lines.append("---------------------------------")
            lines.extend(
                _item_body_lines(
                    item_name=str(raw.get("item_name") or ""),
                    quantity=int(raw.get("quantity") or 1),
                    note=raw.get("note"),
                    selected_modifiers=raw.get("selected_modifiers") or [],
                    is_takeaway=bool(raw.get("is_takeaway")),
                )
            )

    lines.extend(["---------------------------------", "[ --- CUT TICKET --- ]", ""])
    return "\n".join(lines)


_ESC_ALIGN_CENTER = b"\x1b\x61\x01"
_ESC_ALIGN_LEFT = b"\x1b\x61\x00"
_GS_SIZE_DOUBLE = b"\x1d\x21\x11"  # double width + double height
_GS_SIZE_NORMAL = b"\x1d\x21\x00"
_GS_REVERSE_ON = b"\x1d\x42\x01"  # white on black
_GS_REVERSE_OFF = b"\x1d\x42\x00"


def _escpos_text_with_banners(text: str) -> bytes:
    """Text body where banner lines are centred, double-size and reversed."""
    body = bytearray()
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if is_banner_line(line):
            body.extend(_ESC_ALIGN_CENTER + _GS_SIZE_DOUBLE + _GS_REVERSE_ON)
            body.extend(f" {banner_text(line)} ".encode("utf-8"))
            body.extend(_GS_REVERSE_OFF + _GS_SIZE_NORMAL)
            body.extend(b"\n" + _ESC_ALIGN_LEFT)
            continue
        body.extend(line.encode("utf-8"))
        if index < len(lines) - 1:
            body.extend(b"\n")
    return bytes(body)


def build_escpos_text_payload(text: str) -> bytes:
    """Minimal ESC/POS payload: initialize, UTF-8 text, feed, full cut."""
    payload = bytearray()
    payload.extend(b"\x1b\x40")  # ESC @ initialize
    if BANNER_PREFIX in text:
        payload.extend(_escpos_text_with_banners(text))
    else:
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
