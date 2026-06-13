"""Kitchen ticket text and ESC/POS payload builders."""

from __future__ import annotations


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


def build_escpos_payload(text: str) -> bytes:
    """Minimal ESC/POS payload: initialize, UTF-8 text, feed, full cut."""
    payload = bytearray()
    payload.extend(b"\x1b\x40")  # ESC @ initialize
    payload.extend(text.encode("utf-8"))
    payload.extend(b"\n\n")
    payload.extend(b"\x1d\x56\x00")  # GS V 0 full cut
    return bytes(payload)
