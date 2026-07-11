"""Orders API: create and manage orders."""

import asyncio
from pydantic import BaseModel, field_validator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user, require_roles
from database import get_db
from models import MenuItem, Order, OrderItem, Table, User
from rbac import CHECKOUT_ROLES, POS_ORDER_ROLES
from services.printing.routes import resolve_printer_route
from services.printing.service import dispatch_kitchen_ticket
from schemas import (
    ActiveTakeawayOrderResponse,
    OrderCheckoutRequest,
    OrderCreateResponse,
    OrderCreate,
    OrderDetailsResponse,
    OrderItemDetail,
    OrderItemDetailsResponse,
    OrderItemStatusUpdateRequest,
    OrderResponseDetail,
    OrderStatusUpdateResponse,
    OrderStatusLiteral,
    OrderSubmitRequest,
    OrderSubmitResponse,
)

router = APIRouter(prefix="/api")

OPEN_ORDER_STATUSES = ("open", "dining")
DELETED_ITEM_LABEL = "[Deleted Item]"
DELETED_USER_LABEL = "[Deleted User]"


def _normalized_item_status_value(item_status) -> str:
    return str(getattr(item_status, "value", item_status or "pending")).strip().lower()


def _recalculate_order_total_excluding_cancelled(order: Order) -> float:
    subtotal = sum(
        float(getattr(oi, "subtotal", 0.0) or 0.0)
        for oi in (order.order_items or [])
        if _normalized_item_status_value(getattr(oi, "item_status", None)) != "cancelled"
    )
    discount_type = (getattr(order, "discount_type", None) or "").strip().lower() or None
    discount_value = float(getattr(order, "discount_value", 0.0) or 0.0)
    if discount_value < 0:
        discount_value = 0.0

    discount_amount = 0.0
    if discount_type == "percentage" and discount_value > 0:
        discount_amount = subtotal * (discount_value / 100.0)
    elif discount_type == "amount" and discount_value > 0:
        discount_amount = discount_value

    return round(max(subtotal - discount_amount, 0.0), 2)


def _order_has_non_cancelled_items(order: Order) -> bool:
    return any(
        _normalized_item_status_value(getattr(oi, "item_status", None)) != "cancelled"
        for oi in (order.order_items or [])
    )


def _release_table_if_order_fully_cancelled(db: Session, order: Order) -> tuple[Table | None, bool]:
    """
    When every line item is cancelled, finalize the order and free the table.
    Returns (released_table, order_auto_cancelled).
    """
    if _order_has_non_cancelled_items(order):
        return None, False

    order_status = str(getattr(order, "status", "") or "").strip().lower()
    if order_status == "paid":
        return None, False

    order_auto_cancelled = order_status != "cancelled"
    if order_auto_cancelled:
        order.status = "cancelled"
    order.total_amount = _recalculate_order_total_excluding_cancelled(order)

    if order.table_id is None:
        return None, order_auto_cancelled

    table = db.query(Table).filter(Table.id == order.table_id).first()
    if not table:
        return None, order_auto_cancelled

    status_value = getattr(table.status, "value", table.status)
    if status_value == "available":
        return None, order_auto_cancelled

    table.status = "available"
    return table, order_auto_cancelled


def _cancel_order_items_and_release_table(db: Session, order: Order) -> Table | None:
    """Mark all items cancelled, finalize order, and release dine-in table."""
    for oi in order.order_items or []:
        if _normalized_item_status_value(getattr(oi, "item_status", None)) != "cancelled":
            oi.item_status = "cancelled"

    order_status = str(getattr(order, "status", "") or "").strip().lower()
    if order_status != "paid":
        order.status = "cancelled"
        order.total_amount = _recalculate_order_total_excluding_cancelled(order)

    if order.table_id is None:
        return None

    table = db.query(Table).filter(Table.id == order.table_id).first()
    if not table:
        return None

    status_value = getattr(table.status, "value", table.status)
    if status_value == "available":
        return None

    table.status = "available"
    return table


def _table_number_from_table(table: Table) -> int:
    """Best-effort integer table number for legacy UI/response compatibility."""
    try:
        return int(str(table.name_or_number).strip())
    except Exception:
        return int(table.id)


def _selected_modifiers_payload(raw_modifiers) -> list[dict]:
    """Normalize validated modifier objects into JSON-serializable dicts."""
    payload = []
    for m in (raw_modifiers or []):
        if hasattr(m, "model_dump"):
            payload.append(m.model_dump(mode="json"))
        elif isinstance(m, dict):
            payload.append(dict(m))
    return payload


def _selected_modifiers_total(selected_modifiers: list[dict]) -> float:
    total = 0.0
    for m in selected_modifiers or []:
        try:
            total += float(m.get("price") or 0.0)
        except Exception:
            continue
    return total


def _round_money(value) -> float:
    """Normalize money values to 2 decimal places deterministically."""
    try:
        return round(float(value or 0.0), 2)
    except Exception:
        return 0.0


def _display_menu_item_name(order_item: OrderItem) -> str:
    menu_item = getattr(order_item, "menu_item", None)
    if menu_item is not None and not bool(getattr(menu_item, "is_deleted", False)):
        return (
            getattr(menu_item, "name", None)
            or getattr(order_item, "menu_item_name_at_sale", None)
            or DELETED_ITEM_LABEL
        )
    return getattr(order_item, "menu_item_name_at_sale", None) or DELETED_ITEM_LABEL


def _display_waiter_name(order_item: OrderItem) -> str | None:
    created_by = getattr(order_item, "created_by", None)
    if created_by is not None and not bool(getattr(created_by, "is_deleted", False)):
        return getattr(created_by, "username", None)
    if getattr(order_item, "created_by_id", None) is not None:
        return DELETED_USER_LABEL
    return None


def _resolve_unit_base_price(menu_item: MenuItem, *, is_takeaway: bool = False) -> float:
    """Effective base before discount/tax (takeaway_price or catalog price)."""
    if is_takeaway:
        raw_takeaway = getattr(menu_item, "takeaway_price", None)
        if raw_takeaway is not None:
            return float(raw_takeaway)
    return float(menu_item.price)


def _menu_item_discount_config(menu_item: MenuItem, effective_base: float) -> tuple[str, float]:
    discount_type = str(getattr(menu_item, "discount_type", "none") or "none").strip().lower()
    discount_value = float(getattr(menu_item, "discount_value", 0.0) or 0.0)
    if discount_type not in ("percentage", "fixed"):
        discount_type = "none"
    if discount_value < 0:
        discount_value = 0.0
    if discount_type == "none":
        try:
            legacy_sale = float(getattr(menu_item, "discount_price", 0) or 0)
        except Exception:
            legacy_sale = 0.0
        if legacy_sale > 0 and effective_base > legacy_sale:
            discount_type = "fixed"
            discount_value = _round_money(effective_base - legacy_sale)
    return discount_type, discount_value


def _calculate_unit_discount_amount(
    base_price: float, discount_type: str, discount_value: float
) -> float:
    if discount_type == "percentage" and discount_value > 0:
        return _round_money(base_price * (discount_value / 100.0))
    if discount_type == "fixed" and discount_value > 0:
        return _round_money(min(discount_value, base_price))
    return 0.0


def _menu_item_tax_config(menu_item: MenuItem) -> tuple[str, float]:
    tax_type = str(getattr(menu_item, "tax_type", "none") or "none").strip().lower()
    tax_value = float(getattr(menu_item, "tax_value", 0.0) or 0.0)
    if tax_type not in ("percentage", "fixed"):
        tax_type = "none"
    if tax_value < 0:
        tax_value = 0.0
    return tax_type, tax_value


def _calculate_unit_tax_amount(base_price: float, tax_type: str, tax_value: float) -> float:
    if tax_type == "percentage" and tax_value > 0:
        return _round_money(base_price * (tax_value / 100.0))
    if tax_type == "fixed" and tax_value > 0:
        return _round_money(tax_value)
    return 0.0


def _calculate_order_line_pricing(
    menu_item: MenuItem,
    *,
    is_takeaway: bool,
    quantity: int,
    selected_modifiers: list[dict],
) -> tuple[float, float, float, float]:
    """Return (base_price, unit_discount, unit_tax, line_subtotal) for one order line."""
    base_price = _resolve_unit_base_price(menu_item, is_takeaway=is_takeaway)
    disc_type, disc_val = _menu_item_discount_config(menu_item, base_price)
    unit_discount = _calculate_unit_discount_amount(base_price, disc_type, disc_val)
    discounted_price = _round_money(base_price - unit_discount)
    tax_type, tax_value = _menu_item_tax_config(menu_item)
    unit_tax = _calculate_unit_tax_amount(discounted_price, tax_type, tax_value)
    modifiers_total = _selected_modifiers_total(selected_modifiers)
    line_subtotal = _round_money((discounted_price + unit_tax + modifiers_total) * quantity)
    return _round_money(base_price), unit_discount, unit_tax, line_subtotal


def _order_lines_tax_total(order: Order) -> float:
    total = 0.0
    for oi in order.order_items or []:
        if _normalized_item_status_value(getattr(oi, "item_status", None)) == "cancelled":
            continue
        unit_tax = float(getattr(oi, "unit_tax_at_sale", 0.0) or 0.0)
        total += unit_tax * int(getattr(oi, "quantity", 0) or 0)
    return _round_money(total)


def _order_price_breakdown(order: Order) -> dict[str, float]:
    """Subtotal, discount, tax, and grand total for non-cancelled lines."""
    breakdown_subtotal = 0.0
    breakdown_discount_total = 0.0
    breakdown_tax_total = 0.0
    breakdown_grand_total = 0.0
    for oi in order.order_items or []:
        if _normalized_item_status_value(getattr(oi, "item_status", None)) == "cancelled":
            continue
        qty = int(getattr(oi, "quantity", 0) or 0)
        base = float(getattr(oi, "unit_price_at_sale", 0.0) or 0.0)
        unit_discount = float(getattr(oi, "unit_discount_at_sale", 0.0) or 0.0)
        unit_tax = float(getattr(oi, "unit_tax_at_sale", 0.0) or 0.0)
        modifiers_total = _selected_modifiers_total(getattr(oi, "selected_modifiers", []) or [])
        breakdown_subtotal += (base + modifiers_total) * qty
        breakdown_discount_total += unit_discount * qty
        breakdown_tax_total += unit_tax * qty
        breakdown_grand_total += float(getattr(oi, "subtotal", 0.0) or 0.0)
    return {
        "breakdown_subtotal": _round_money(breakdown_subtotal),
        "breakdown_discount_total": _round_money(breakdown_discount_total),
        "breakdown_tax_total": _round_money(breakdown_tax_total),
        "breakdown_grand_total": _round_money(breakdown_grand_total),
    }


async def _broadcast_table_status_changed(request: Request, table: Table) -> None:
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "table_status_changed",
            {
                "table_id": table.id,
                "name_or_number": table.name_or_number,
                "zone_id": table.zone_id,
                "status": getattr(table.status, "value", table.status),
            },
        )
        await manager.broadcast("table_grid_updated", {"refresh": True})


async def _broadcast_order_cancelled(
    request: Request,
    order: Order,
    released_table: Table | None = None,
) -> None:
    if released_table:
        await _broadcast_table_status_changed(request, released_table)
    manager = getattr(request.app.state, "ws_manager", None)
    if not manager:
        return
    payload = {
        "id": order.id,
        "order_id": order.id,
        "status": order.status,
        "table_id": order.table_id,
        "order_type": (order.order_type or "dine_in"),
        "total_amount": float(order.total_amount),
    }
    await manager.broadcast("order_updated", payload)
    await manager.broadcast("order_cancelled", payload)
    if (order.order_type or "").strip().lower() == "takeaway":
        await manager.broadcast("takeaways_updated", payload)


def _build_order_item_details_response(oi: OrderItem) -> OrderItemDetailsResponse:
    return OrderItemDetailsResponse(
        id=oi.id,
        menu_item_id=oi.menu_item_id,
        menu_item_name=_display_menu_item_name(oi),
        quantity=oi.quantity,
        subtotal=float(oi.subtotal),
        unit_price_at_sale=float(getattr(oi, "unit_price_at_sale", 0.0) or 0.0),
        unit_discount_at_sale=float(getattr(oi, "unit_discount_at_sale", 0.0) or 0.0),
        unit_tax_at_sale=float(getattr(oi, "unit_tax_at_sale", 0.0) or 0.0),
        item_status=getattr(getattr(oi, "item_status", None), "value", getattr(oi, "item_status", "pending")),
        waiter_name=_display_waiter_name(oi),
        selected_modifiers=getattr(oi, "selected_modifiers", []) or [],
        note=getattr(oi, "note", None) or getattr(oi, "special_instructions", None),
        special_instructions=getattr(oi, "special_instructions", None),
        is_takeaway=bool(getattr(oi, "is_takeaway", False)),
    )


@router.post("/orders/", response_model=OrderCreateResponse)
async def create_order(
    request: Request,
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """
    Create or add to an order for a table (table-centric). If table already has an open/dining
    order, appends items to it; otherwise creates a new order. Keeps one active order per table.
    """
    if not order_data.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

    normalized_order_type = (order_data.order_type or "dine_in").strip().lower()
    if normalized_order_type not in ("dine_in", "takeaway"):
        raise HTTPException(status_code=400, detail="order_type must be 'dine_in' or 'takeaway'")

    table = None
    table_number = None
    existing = None
    if normalized_order_type == "dine_in":
        if order_data.table_id is None:
            raise HTTPException(status_code=400, detail="table_id is required for dine_in orders")
        table = db.query(Table).filter(Table.id == order_data.table_id).first()
        if not table:
            raise HTTPException(status_code=404, detail=f"Table id {order_data.table_id} not found")
        table_number = _table_number_from_table(table)
        existing = (
            db.query(Order)
            .filter(
                Order.table_id == table.id,
                Order.status.in_(OPEN_ORDER_STATUSES),
            )
            .first()
        )

    if existing is not None:
        # Append to existing order (same as submit add-on)
        existing_total = float(existing.total_amount)
        added_items_detail = []
        for line in order_data.items:
            menu_item = (
                db.query(MenuItem)
                .filter(MenuItem.id == line.menu_item_id, MenuItem.is_deleted.is_(False))
                .first()
            )
            if not menu_item:
                raise HTTPException(status_code=404, detail=f"Menu item with id {line.menu_item_id} not found")
            if line.quantity < 1:
                raise HTTPException(status_code=400, detail=f"Quantity for {menu_item.name} must be at least 1")
            selected_modifiers = _selected_modifiers_payload(line.selected_modifiers)
            is_takeaway = bool(getattr(line, "is_takeaway", False))
            base_price, unit_discount, unit_tax, subtotal = _calculate_order_line_pricing(
                menu_item,
                is_takeaway=is_takeaway,
                quantity=line.quantity,
                selected_modifiers=selected_modifiers,
            )
            note_value = (line.note or line.special_instructions or "").strip() or None
            existing_total = _round_money(existing_total + subtotal)
            db.add(
                OrderItem(
                    order_id=existing.id,
                    menu_item_id=line.menu_item_id,
                    quantity=line.quantity,
                    subtotal=subtotal,
                    batch_status="pending",
                    created_by_id=current_user.id,
                    selected_modifiers=selected_modifiers,
                    note=note_value,
                    special_instructions=note_value,
                    menu_item_name_at_sale=menu_item.name,
                    unit_price_at_sale=base_price,
                    unit_discount_at_sale=unit_discount,
                    unit_tax_at_sale=unit_tax,
                    category_name_at_sale=getattr(getattr(menu_item, "category", None), "name", None),
                    is_takeaway=is_takeaway,
                )
            )
            added_items_detail.append(
                OrderItemDetail(
                    menu_item_name=menu_item.name,
                    quantity=line.quantity,
                    subtotal=subtotal,
                    menu_item_image_url=getattr(menu_item, "image_url", None),
                    waiter_name=current_user.username,
                    selected_modifiers=selected_modifiers,
                    note=note_value,
                    special_instructions=note_value,
                )
            )
        existing.total_amount = _round_money(existing_total)
        previous_status = table.status if table else None
        if table:
            table.status = "occupied"
        db.commit()
        db.refresh(existing)
        manager = getattr(request.app.state, "ws_manager", None)
        if manager:
            await manager.broadcast(
                "order_updated",
                {"table_id": table.id if table else None, "added_items": [d.model_dump(mode="json") for d in added_items_detail]},
            )
        if table and previous_status != table.status:
            await _broadcast_table_status_changed(request, table)
        return {
            "id": existing.id,
            "table_number": existing.table_number,
            "status": existing.status,
            "total_amount": existing.total_amount,
        }

    total_amount = 0.0
    order_items_data = []
    for line in order_data.items:
        menu_item = (
            db.query(MenuItem)
            .filter(MenuItem.id == line.menu_item_id, MenuItem.is_deleted.is_(False))
            .first()
        )
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item with id {line.menu_item_id} not found")
        if line.quantity < 1:
            raise HTTPException(status_code=400, detail=f"Quantity for {menu_item.name} must be at least 1")
        selected_modifiers = _selected_modifiers_payload(line.selected_modifiers)
        is_takeaway = bool(getattr(line, "is_takeaway", False))
        base_price, unit_discount, unit_tax, subtotal = _calculate_order_line_pricing(
            menu_item,
            is_takeaway=is_takeaway,
            quantity=line.quantity,
            selected_modifiers=selected_modifiers,
        )
        note_value = (line.note or line.special_instructions or "").strip() or None
        total_amount = _round_money(total_amount + subtotal)
        order_items_data.append(
            {
                "menu_item_id": line.menu_item_id,
                "quantity": line.quantity,
                "subtotal": subtotal,
                "selected_modifiers": selected_modifiers,
                "note": note_value,
                "special_instructions": note_value,
                "menu_item_name_at_sale": menu_item.name,
                "unit_price_at_sale": base_price,
                "unit_discount_at_sale": unit_discount,
                "unit_tax_at_sale": unit_tax,
                "category_name_at_sale": getattr(getattr(menu_item, "category", None), "name", None),
                "is_takeaway": is_takeaway,
            }
        )

    db_order = Order(
        table_id=table.id if table else None,
        table_number=table_number,
        order_type=normalized_order_type,
        customer_name=(order_data.customer_name or "").strip() or None,
        status="open",
        total_amount=_round_money(total_amount),
    )
    db.add(db_order)
    db.flush()
    for item_data in order_items_data:
        db.add(
            OrderItem(
                order_id=db_order.id,
                menu_item_id=item_data["menu_item_id"],
                quantity=item_data["quantity"],
                subtotal=_round_money(item_data["subtotal"]),
                batch_status="pending",
                created_by_id=current_user.id,
                selected_modifiers=item_data["selected_modifiers"],
                note=item_data["note"],
                special_instructions=item_data["special_instructions"],
                menu_item_name_at_sale=item_data["menu_item_name_at_sale"],
                unit_price_at_sale=item_data["unit_price_at_sale"],
                unit_discount_at_sale=item_data["unit_discount_at_sale"],
                unit_tax_at_sale=item_data["unit_tax_at_sale"],
                category_name_at_sale=item_data["category_name_at_sale"],
                is_takeaway=item_data.get("is_takeaway", False),
            )
        )
    previous_status = table.status if table else None
    if table:
        table.status = "occupied"
    db.commit()
    db.refresh(db_order)
    if table and previous_status != table.status:
        await _broadcast_table_status_changed(request, table)
    full_order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .filter(Order.id == db_order.id)
        .first()
    )
    payload = OrderResponseDetail.model_validate(full_order)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast("order_created", payload.model_dump(mode="json"))
    return {
        "id": db_order.id,
        "table_number": db_order.table_number,
        "status": db_order.status,
        "total_amount": db_order.total_amount,
    }


@router.get("/orders/", response_model=list[OrderResponseDetail])
def list_orders(
    status: list[str] | None = Query(None, description="Filter by status(es), e.g. status=pending&status=open"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """List orders, optionally filtered by status. Eager-loads items and menu_item to avoid N+1."""
    q = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .order_by(Order.created_at.desc())
    )
    if status:
        q = q.filter(Order.status.in_(status))
    orders = q.all()
    return [OrderResponseDetail.model_validate(o) for o in orders]


@router.get("/orders/active-takeaways", response_model=list[ActiveTakeawayOrderResponse])
def list_active_takeaways(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """
    Return all active (unpaid) takeaway orders with their related order items.
    """
    orders = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .filter(
            Order.order_type == "takeaway",
            Order.status != "paid",
            Order.status != "cancelled",
        )
        .order_by(Order.created_at.desc())
        .all()
    )

    payload: list[ActiveTakeawayOrderResponse] = []
    for order in orders:
        items = [_build_order_item_details_response(oi) for oi in (order.order_items or [])]
        breakdown = _order_price_breakdown(order)
        payload.append(
            ActiveTakeawayOrderResponse(
                id=order.id,
                customer_name=getattr(order, "customer_name", None),
                total_amount=float(order.total_amount),
                created_at=order.created_at,
                items=items,
                **breakdown,
            )
        )
    return payload


# Statuses that mean "this table has an order ready for checkout" (Cashier view)
CHECKOUT_ORDER_STATUSES = ("open", "dining", "completed", "pending")

# Priority for "canonical" order per table: open/dining is the live tab we append to (has all items)
_STATUS_PRIORITY = {"open": 0, "dining": 1, "completed": 2, "pending": 3}


def _canonical_order_for_table(orders):
    """Pick the single order that represents this table's full tab (all items). Prefer open/dining."""
    if not orders:
        return None
    return min(
        orders,
        key=lambda o: (_STATUS_PRIORITY.get(o.status, 99), -o.id),
    )


@router.get("/orders/tables", response_model=list[OrderResponseDetail])
def list_orders_by_table(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """
    List one order per table (the canonical order for checkout). Cashier uses this so each
    table appears once with the order that has ALL items (initial + add-ons) and grand total.
    """
    q = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .filter(Order.status.in_(CHECKOUT_ORDER_STATUSES))
        .order_by(Order.table_number, Order.id)
    )
    orders = q.all()
    by_table = {}
    for o in orders:
        table_key = o.table_id if getattr(o, "table_id", None) is not None else o.table_number
        by_table.setdefault(table_key, []).append(o)
    canonical = [_canonical_order_for_table(ords) for ords in by_table.values()]
    canonical = [o for o in canonical if o is not None]
    canonical.sort(key=lambda o: o.table_id if getattr(o, "table_id", None) is not None else o.table_number)
    return [OrderResponseDetail.model_validate(o) for o in canonical]


@router.get("/orders/active-by-table/{table_id}", response_model=OrderResponseDetail)
def get_active_order_by_table(
    table_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """
    Get the single canonical order for a table (all items + grand total). Prefers the
    order with status open/dining (the one we append add-ons to), then completed, then pending.
    """
    q = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .filter(
            (Order.table_id == table_id) | (Order.table_number == table_id),
            Order.status.in_(CHECKOUT_ORDER_STATUSES),
        )
    )
    orders = q.all()
    order = _canonical_order_for_table(orders)
    if not order:
        raise HTTPException(status_code=404, detail=f"No order found for table {table_id}")
    return OrderResponseDetail.model_validate(order)


class OrderStatusUpdate(BaseModel):
    """Request body for updating order status."""

    status: OrderStatusLiteral

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        return str(v or "").strip().lower()


@router.put("/orders/{order_id}/status", response_model=OrderStatusUpdateResponse)
async def update_order_status(
    request: Request,
    order_id: int,
    body: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """Update an order's status (e.g. completed). Broadcasts order_updated via WebSocket."""
    order = (
        db.query(Order)
        .options(joinedload(Order.order_items))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    normalized_status = (body.status or "").strip().lower()
    released_table = None
    if normalized_status == "cancelled":
        released_table = _cancel_order_items_and_release_table(db, order)
    else:
        order.status = normalized_status

    db.commit()
    db.refresh(order)
    if released_table:
        await _broadcast_table_status_changed(request, released_table)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast("order_updated", {"id": order.id, "status": order.status})
    return {"id": order.id, "status": order.status}


@router.post("/orders/{order_id}/cancel", response_model=OrderStatusUpdateResponse)
async def cancel_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """Cancel an entire active order, release its table if any, and broadcast realtime updates."""
    order = (
        db.query(Order)
        .options(joinedload(Order.order_items))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order_status = str(getattr(order, "status", "") or "").strip().lower()
    if order_status == "paid":
        raise HTTPException(status_code=400, detail="Cannot cancel a paid order")
    if order_status == "cancelled":
        raise HTTPException(status_code=400, detail="Order is already cancelled")

    released_table = _cancel_order_items_and_release_table(db, order)
    db.commit()
    db.refresh(order)
    await _broadcast_order_cancelled(request, order, released_table)
    return {"id": order.id, "status": order.status}


@router.get("/orders/{order_id}/details", response_model=OrderDetailsResponse)
def get_order_details(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = [_build_order_item_details_response(oi) for oi in order.order_items]
    breakdown = _order_price_breakdown(order)
    return OrderDetailsResponse(
        id=order.id,
        table_id=getattr(order, "table_id", None),
        table_number=getattr(order, "table_number", None),
        order_type=getattr(order, "order_type", "dine_in"),
        customer_name=getattr(order, "customer_name", None),
        status=order.status,
        total_amount=float(order.total_amount),
        tax_amount=float(getattr(order, "tax_amount", 0.0) or 0.0),
        discount_type=getattr(order, "discount_type", None),
        discount_value=float(getattr(order, "discount_value", 0.0) or 0.0),
        created_at=order.created_at,
        items=items,
        **breakdown,
    )


@router.put("/orders/{order_id}/items/{item_id}/status", response_model=OrderResponseDetail)
async def update_order_item_status(
    request: Request,
    order_id: int,
    item_id: int,
    body: OrderItemStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    oi = next((item for item in (order.order_items or []) if item.id == item_id), None)
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")

    normalized_status = (body.status or "").strip().lower()
    allowed = {"pending", "cooking", "served", "cancelled"}
    if normalized_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Allowed: pending, cooking, served, cancelled",
        )

    oi.item_status = normalized_status
    # Paid orders store tax-inclusive totals from checkout; never overwrite with pre-tax recalculation.
    order_status = str(getattr(order, "status", "") or "").strip().lower()
    if order_status != "paid":
        order.total_amount = _recalculate_order_total_excluding_cancelled(order)

    released_table = None
    order_auto_cancelled = False
    if normalized_status == "cancelled":
        released_table, order_auto_cancelled = _release_table_if_order_fully_cancelled(db, order)

    db.commit()
    updated_order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not updated_order:
        raise HTTPException(status_code=404, detail="Order not found after update")

    if order_auto_cancelled:
        await _broadcast_order_cancelled(request, updated_order, released_table)
    else:
        if released_table:
            await _broadcast_table_status_changed(request, released_table)

        manager = getattr(request.app.state, "ws_manager", None)
        if manager:
            await manager.broadcast(
                "table_grid_updated",
                {
                    "refresh": True,
                    "order_id": order_id,
                    "item_id": item_id,
                    "table_id": updated_order.table_id,
                    "item_status": _normalized_item_status_value(getattr(oi, "item_status", None)),
                    "total_amount": float(updated_order.total_amount),
                },
            )
            await manager.broadcast(
                "order_updated",
                {
                    "id": updated_order.id,
                    "status": updated_order.status,
                    "total_amount": float(updated_order.total_amount),
                },
            )
            if (updated_order.order_type or "").strip().lower() == "takeaway":
                await manager.broadcast(
                    "takeaways_updated",
                    {
                        "order_id": updated_order.id,
                        "order_type": updated_order.order_type,
                        "status": updated_order.status,
                        "total_amount": float(updated_order.total_amount),
                    },
                )

    return OrderResponseDetail.model_validate(updated_order)


@router.post("/orders/submit", response_model=OrderSubmitResponse)
async def submit_order(
    request: Request,
    body: OrderSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """
    Submit order endpoint supporting:
    - dine_in (table-centric batching)
    - takeaway (no table required)

    - If no open/dining Order for this table: create new Order and add items as batch_number = 1.
    - If open/dining Order exists: append items as a NEW batch (batch_number = max+1).
    - Always updates Order.total_amount.
    - Emits WebSocket event `new_order_batch` with only the new batch items, table_number and batch_number.
    """
    if not body.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

    normalized_order_type = (body.order_type or "dine_in").strip().lower()
    if normalized_order_type not in ("dine_in", "takeaway"):
        raise HTTPException(status_code=400, detail="order_type must be 'dine_in' or 'takeaway'")
    if body.order_id is not None and normalized_order_type != "takeaway":
        raise HTTPException(status_code=400, detail="order_id is only valid for takeaway append")

    table = None
    table_number = None
    order = None

    if normalized_order_type == "dine_in":
        if body.table_id is None:
            raise HTTPException(status_code=400, detail="table_id is required for dine_in orders")
        table = db.query(Table).filter(Table.id == body.table_id).first()
        if not table:
            raise HTTPException(status_code=404, detail=f"Table id {body.table_id} not found")
        table_number = _table_number_from_table(table)
        # Find existing open/dining order (current dining session)
        order = (
            db.query(Order)
            .filter(
                Order.table_id == table.id,
                Order.status.in_(OPEN_ORDER_STATUSES),
            )
            .first()
        )
    elif body.order_id is not None:
        order = (
            db.query(Order)
            .filter(
                Order.id == body.order_id,
                Order.order_type == "takeaway",
                Order.table_id.is_(None),
                Order.status.in_(OPEN_ORDER_STATUSES),
            )
            .first()
        )
        if not order:
            raise HTTPException(
                status_code=404,
                detail=f"Active takeaway order id {body.order_id} not found",
            )

    is_new_order = order is None

    if order is None:
        # No open order yet: start a new order, first batch = 1
        order = Order(
            table_id=table.id if table else None,
            table_number=table_number,
            order_type=normalized_order_type,
            customer_name=(body.customer_name or "").strip() or None,
            status="open",
            total_amount=0.0,
        )
        db.add(order)
        db.flush()
        new_batch_number = 1
    else:
        # Existing open/dining order: next batch_number = max(existing) + 1
        current_max_batch = (
            db.query(func.max(OrderItem.batch_number))
            .filter(OrderItem.order_id == order.id)
            .scalar()
        )
        current_max_batch = current_max_batch or 1
        new_batch_number = current_max_batch + 1

    batch_total = 0.0
    batch_items_detail: list[OrderItemDetail] = []
    item_print_jobs: list[tuple[str, dict]] = []

    for line in body.items:
        menu_item = (
            db.query(MenuItem)
            .options(joinedload(MenuItem.category))
            .filter(MenuItem.id == line.menu_item_id, MenuItem.is_deleted.is_(False))
            .first()
        )
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item id {line.menu_item_id} not found")
        if line.quantity < 1:
            raise HTTPException(status_code=400, detail=f"Quantity for {menu_item.name} must be at least 1")
        selected_modifiers = _selected_modifiers_payload(line.selected_modifiers)
        is_takeaway = bool(getattr(line, "is_takeaway", False))
        base_price, unit_discount, unit_tax, subtotal = _calculate_order_line_pricing(
            menu_item,
            is_takeaway=is_takeaway,
            quantity=line.quantity,
            selected_modifiers=selected_modifiers,
        )
        note_value = (line.note or line.special_instructions or "").strip() or None
        batch_total = _round_money(batch_total + subtotal)
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=line.menu_item_id,
                quantity=line.quantity,
                subtotal=_round_money(subtotal),
                batch_number=new_batch_number,
                batch_status="pending",
                created_by_id=current_user.id,
                selected_modifiers=selected_modifiers,
                note=note_value,
                special_instructions=note_value,
                menu_item_name_at_sale=menu_item.name,
                unit_price_at_sale=base_price,
                unit_discount_at_sale=unit_discount,
                unit_tax_at_sale=unit_tax,
                category_name_at_sale=getattr(getattr(menu_item, "category", None), "name", None),
                is_takeaway=is_takeaway,
            )
        )
        batch_items_detail.append(
            OrderItemDetail(
                menu_item_name=menu_item.name,
                quantity=line.quantity,
                subtotal=subtotal,
                batch_number=new_batch_number,
                menu_item_image_url=getattr(menu_item, "image_url", None),
                waiter_name=current_user.username,
                selected_modifiers=selected_modifiers,
                note=note_value,
                special_instructions=note_value,
            )
        )
        category = getattr(menu_item, "category", None)
        printer_route = resolve_printer_route(getattr(category, "printer_route", None))
        item_print_jobs.append(
            (
                printer_route,
                {
                    "item_name": menu_item.name,
                    "quantity": line.quantity,
                    "note": note_value,
                    "table_number": table_number if table_number is not None else (order.customer_name or "Takeaway"),
                    "order_id": order.id,
                    "date": order.created_at.isoformat() if order.created_at else "",
                },
            )
        )

    # Update order running total and persist
    order.total_amount = _round_money(float(order.total_amount) + batch_total)
    previous_status = table.status if table else None
    if table:
        table.status = "occupied"
    db.commit()
    db.refresh(order)

    # Broadcast this batch only for Kitchen (KDS)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "new_order_batch",
            {
                "order_id": order.id,
                "order_type": normalized_order_type,
                "table_id": table.id if table else None,
                "table_number": table_number,
                "batch_number": new_batch_number,
                "is_new_order": is_new_order,
                "created_at": order.created_at.isoformat(),
                "items": [d.model_dump(mode="json") for d in batch_items_detail],
            },
        )
    if table and previous_status != table.status:
        await _broadcast_table_status_changed(request, table)

    # Print each item as a separate ticket (single-item ticketing).
    if item_print_jobs:
        await asyncio.gather(
            *[
                dispatch_kitchen_ticket(
                    printer_route,
                    item_ticket,
                    order_type=getattr(order, "order_type", "dine_in"),
                    customer_name=getattr(order, "customer_name", None),
                )
                for printer_route, item_ticket in item_print_jobs
            ],
            return_exceptions=True,
        )

    return OrderSubmitResponse(
        id=order.id,
        table_number=order.table_number,
        total_amount=_round_money(order.total_amount),
        is_new_order=is_new_order,
        message=(
            (
                f"New takeaway order created for {order.customer_name or 'Walk-in'}"
                if is_new_order
                else f"Items added to takeaway order for {order.customer_name or 'Walk-in'} (batch {new_batch_number})"
            )
            if normalized_order_type == "takeaway"
            else (
                f"New order created for Table {table.name_or_number}"
                if is_new_order
                else f"Items added to Table {table.name_or_number}'s existing order (batch {new_batch_number})"
            )
        ),
    )


@router.post("/orders/{order_id}/checkout", response_model=OrderResponseDetail)
@router.put("/orders/{order_id}/checkout", response_model=OrderResponseDetail)
async def checkout_order(
    request: Request,
    order_id: int,
    body: OrderCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CHECKOUT_ROLES)),
):
    """
    Finalize payment for an order with optional order-level discount:
    - Recalculate subtotal from order items
    - Apply discount_type/discount_value if provided
    - Ensure final total is never below 0
    - Validate amount_tendered >= final total
    - Set status = 'paid' and store payment + discount details
    - Return full receipt for cashier
    """
    order = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.order_items).joinedload(OrderItem.created_by),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    subtotal = _round_money(sum(
        float(getattr(i, "subtotal", 0.0) or 0.0)
        for i in (order.order_items or [])
        if _normalized_item_status_value(getattr(i, "item_status", None)) != "cancelled"
    ))
    normalized_discount_type = (body.discount_type or "").strip().lower() or None
    discount_value = float(body.discount_value or 0.0)
    if discount_value < 0:
        raise HTTPException(status_code=400, detail="discount_value cannot be negative")
    if normalized_discount_type not in (None, "percentage", "amount"):
        raise HTTPException(status_code=400, detail="discount_type must be 'percentage' or 'amount'")

    discount_amount = 0.0
    if normalized_discount_type == "percentage" and discount_value > 0:
        discount_amount = subtotal * (discount_value / 100.0)
    elif normalized_discount_type == "amount" and discount_value > 0:
        discount_amount = discount_value
    discount_amount = _round_money(discount_amount)

    tax_amount = _order_lines_tax_total(order)
    final_total = _round_money(max(subtotal - discount_amount, 0.0))

    tendered = float(body.amount_tendered)
    if tendered < final_total:
        raise HTTPException(
            status_code=400,
            detail=f"Amount tendered ({tendered:.2f}) is less than total ({final_total:.2f})",
        )

    change = _round_money(tendered - final_total)

    order.total_amount = _round_money(final_total)
    order.discount_type = normalized_discount_type
    order.discount_value = _round_money(discount_value) if normalized_discount_type else 0.0
    order.payment_method = body.payment_method
    order.amount_tendered = _round_money(tendered)
    order.change_amount = _round_money(change)
    order.tax_amount = _round_money(tax_amount)
    order.status = "paid"
    order.checked_out_by_id = current_user.id
    # For takeaway orders, table_id is NULL, so skip table status update safely.
    table = db.query(Table).filter(Table.id == order.table_id).first() if order.table_id is not None else None
    previous_status = table.status if table else None
    if table:
        table.status = "available"
    db.commit()
    db.refresh(order)
    if table and previous_status != table.status:
        await _broadcast_table_status_changed(request, table)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        payload = {
            "order_id": order.id,
            "order_type": (order.order_type or "dine_in"),
            "status": order.status,
            "table_id": order.table_id,
        }
        await manager.broadcast(
            "order_updated",
            {"id": order.id, "status": order.status, "table_id": order.table_id},
        )
        await manager.broadcast("order_completed", payload)
        if (order.order_type or "").strip().lower() == "takeaway":
            await manager.broadcast("takeaways_updated", payload)
    return OrderResponseDetail.model_validate(order)
