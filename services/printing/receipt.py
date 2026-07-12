"""Cashier checkout receipt text builder (thermal / image print)."""

from __future__ import annotations

import os
from typing import Any, Sequence


def shop_name() -> str:
    return (os.getenv("SHOP_NAME", "") or "").strip() or "My Restaurant"


def _money(value: float | int | None) -> str:
    return f"{float(value or 0.0):.2f}"


def _payment_label(method: str | None) -> str:
    raw = (method or "").strip().lower().replace(" ", "_")
    if raw == "mobile_money":
        return "Mobile Money"
    if raw == "cash":
        return "Cash"
    return (method or "").strip() or "—"


def build_receipt_text(
    *,
    order_id: int,
    served_by: str | None,
    location_label: str,
    items: Sequence[dict[str, Any]],
    subtotal: float,
    discount_amount: float,
    tax_amount: float,
    grand_total: float,
    payment_method: str | None,
    amount_tendered: float | None = None,
    change_amount: float | None = None,
    created_at: str | None = None,
) -> str:
    """Build a plain-text cashier receipt for Pillow/ESC/POS rendering."""
    lines = [
        "=================================",
        f"  {shop_name()}",
        "=================================",
        f"Order: #{order_id}",
        f"Location: {location_label}",
        f"Served by: {(served_by or '').strip() or 'Unknown'}",
    ]
    if created_at:
        lines.append(f"Time: {created_at}")
    lines.append("---------------------------------")
    for item in items:
        name = str(item.get("name") or item.get("menu_item_name") or "Item")
        qty = int(item.get("quantity") or 1)
        line_total = float(item.get("subtotal") or 0.0)
        lines.append(f"{qty}x {name}")
        lines.append(f"    {_money(line_total)}")
    lines.extend(
        [
            "---------------------------------",
            f"Subtotal:     {_money(subtotal)}",
            f"Discount:    -{_money(discount_amount)}",
            f"Tax:          {_money(tax_amount)}",
            f"Grand Total:  {_money(grand_total)}",
            f"Payment:      {_payment_label(payment_method)}",
        ]
    )
    if amount_tendered is not None:
        lines.append(f"Tendered:     {_money(amount_tendered)}")
    if change_amount is not None:
        lines.append(f"Change:       {_money(change_amount)}")
    lines.extend(
        [
            "---------------------------------",
            "Thank you!",
            "[ --- CUT RECEIPT --- ]",
            "",
        ]
    )
    return "\n".join(lines)
