"""Kitchen ticket text and ESC/POS payload builders."""

from __future__ import annotations

from PIL import Image


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
) -> list[str]:
    note_value = (note or "").strip()
    lines = [f"{quantity}x {item_name}"]
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
) -> str:
    """One combined kitchen slip for a submit batch (no prices).

    ``items`` entries: item_name, quantity, note?, selected_modifiers?
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
                )
            )

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
