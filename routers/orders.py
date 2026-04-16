"""Orders API: create and manage orders."""

import asyncio
import re
from pydantic import BaseModel, field_validator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user, require_roles
from database import get_db
from models import MenuItem, Order, OrderItem, Table, User
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


def _printer_name_for_category(category_name: str | None) -> str:
    """
    Resolve a target printer name from menu category.
    Example: "Hot Drinks" -> "hot_drinks_printer".
    """
    cleaned = re.sub(r"[^a-z0-9]+", "_", (category_name or "").strip().lower()).strip("_")
    return f"{cleaned or 'general'}_printer"


async def mock_send_to_printer(
    printer_name: str,
    item_ticket: dict,
    order_type: str = "dine_in",
    customer_name: str | None = None,
) -> None:
    """
    Mock printer writer for ONE item ticket.
    Appends a standalone ticket to <printer_name>_output.txt.
    """
    output_path = f"{printer_name}_output.txt"
    note_value = (item_ticket.get("note") or "").strip()
    normalized_order_type = (order_type or "dine_in").strip().lower()
    customer = (customer_name or "").strip() or "Walk-in"
    header_block = (
        "=================================\n"
        "  [ *** TAKEAWAY / ပါဆယ် *** ]\n"
        f"  Customer: {customer}\n"
        "=================================\n"
        if normalized_order_type == "takeaway"
        else f"Table: {item_ticket.get('table_number', '')}\n"
    )
    ticket_text = (
        "=== KITCHEN ITEM TICKET ===\n"
        f"Printer: {printer_name}\n"
        + header_block
        + f"Order: #{item_ticket.get('order_id', '')}\n"
        + f"Time: {item_ticket.get('date', '')}\n"
        + "---------------------------------\n"
        + f"{item_ticket.get('quantity', 1)}x {item_ticket.get('item_name', '')}\n"
        + (f"   *** Note: {note_value} ***\n" if note_value else "")
        + "---------------------------------\n"
        + "[ --- CUT TICKET --- ]\n"
    )
    await asyncio.to_thread(
        _append_text_file,
        output_path,
        ticket_text,
    )


def _append_text_file(path: str, text: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)


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


def _base_price_with_discount(menu_item: MenuItem) -> float:
    """
    Use discount price when it exists and is > 0, otherwise use standard price.
    """
    try:
        discount = float(getattr(menu_item, "discount_price", 0) or 0)
    except Exception:
        discount = 0.0
    if discount > 0:
        return discount
    return float(menu_item.price)


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


@router.post("/orders/", response_model=OrderCreateResponse)
async def create_order(
    request: Request,
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cashier", "waiter"])),
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
            menu_item = db.query(MenuItem).filter(MenuItem.id == line.menu_item_id).first()
            if not menu_item:
                raise HTTPException(status_code=404, detail=f"Menu item with id {line.menu_item_id} not found")
            if line.quantity < 1:
                raise HTTPException(status_code=400, detail=f"Quantity for {menu_item.name} must be at least 1")
            selected_modifiers = _selected_modifiers_payload(line.selected_modifiers)
            modifiers_total = _selected_modifiers_total(selected_modifiers)
            base_price = _base_price_with_discount(menu_item)
            subtotal = _round_money((base_price + modifiers_total) * line.quantity)
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
        menu_item = db.query(MenuItem).filter(MenuItem.id == line.menu_item_id).first()
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item with id {line.menu_item_id} not found")
        if line.quantity < 1:
            raise HTTPException(status_code=400, detail=f"Quantity for {menu_item.name} must be at least 1")
        selected_modifiers = _selected_modifiers_payload(line.selected_modifiers)
        modifiers_total = _selected_modifiers_total(selected_modifiers)
        base_price = _base_price_with_discount(menu_item)
        subtotal = _round_money((base_price + modifiers_total) * line.quantity)
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
    current_user: User = Depends(require_roles(["admin", "cashier", "waiter"])),
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
    current_user: User = Depends(require_roles(["admin", "cashier", "waiter"])),
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
        )
        .order_by(Order.created_at.desc())
        .all()
    )

    payload: list[ActiveTakeawayOrderResponse] = []
    for order in orders:
        items = [
            OrderItemDetailsResponse(
                id=oi.id,
                menu_item_id=oi.menu_item_id,
                menu_item_name=getattr(getattr(oi, "menu_item", None), "name", ""),
                quantity=oi.quantity,
                subtotal=float(oi.subtotal),
                item_status=getattr(getattr(oi, "item_status", None), "value", getattr(oi, "item_status", "pending")),
                waiter_name=getattr(getattr(oi, "created_by", None), "username", None),
                selected_modifiers=getattr(oi, "selected_modifiers", []) or [],
                note=getattr(oi, "note", None) or getattr(oi, "special_instructions", None),
                special_instructions=getattr(oi, "special_instructions", None),
            )
            for oi in (order.order_items or [])
        ]
        payload.append(
            ActiveTakeawayOrderResponse(
                id=order.id,
                customer_name=getattr(order, "customer_name", None),
                total_amount=float(order.total_amount),
                created_at=order.created_at,
                items=items,
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
    current_user: User = Depends(require_roles(["admin", "cashier", "waiter"])),
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
    current_user: User = Depends(require_roles(["admin", "cashier", "waiter"])),
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
    current_user: User = Depends(require_roles(["admin", "cashier", "waiter"])),
):
    """Update an order's status (e.g. completed). Broadcasts order_updated via WebSocket."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = body.status
    db.commit()
    db.refresh(order)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast("order_updated", {"id": order.id, "status": order.status})
    return {"id": order.id, "status": order.status}


@router.get("/orders/{order_id}/details", response_model=OrderDetailsResponse)
def get_order_details(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cashier", "waiter"])),
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

    items = [
        OrderItemDetailsResponse(
            id=oi.id,
            menu_item_id=oi.menu_item_id,
            menu_item_name=getattr(getattr(oi, "menu_item", None), "name", ""),
            quantity=oi.quantity,
            subtotal=float(oi.subtotal),
            item_status=getattr(getattr(oi, "item_status", None), "value", getattr(oi, "item_status", "pending")),
            waiter_name=getattr(getattr(oi, "created_by", None), "username", None),
            selected_modifiers=getattr(oi, "selected_modifiers", []) or [],
            note=getattr(oi, "note", None) or getattr(oi, "special_instructions", None),
            special_instructions=getattr(oi, "special_instructions", None),
        )
        for oi in order.order_items
    ]
    return OrderDetailsResponse(
        id=order.id,
        table_id=getattr(order, "table_id", None),
        table_number=getattr(order, "table_number", None),
        order_type=getattr(order, "order_type", "dine_in"),
        customer_name=getattr(order, "customer_name", None),
        status=order.status,
        total_amount=float(order.total_amount),
        created_at=order.created_at,
        items=items,
    )


@router.put("/orders/{order_id}/items/{item_id}/status", response_model=OrderResponseDetail)
async def update_order_item_status(
    request: Request,
    order_id: int,
    item_id: int,
    body: OrderItemStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cashier", "waiter"])),
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
    order.total_amount = _recalculate_order_total_excluding_cancelled(order)
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
    current_user: User = Depends(require_roles(["admin", "cashier", "waiter"])),
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
            .filter(MenuItem.id == line.menu_item_id)
            .first()
        )
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item id {line.menu_item_id} not found")
        if line.quantity < 1:
            raise HTTPException(status_code=400, detail=f"Quantity for {menu_item.name} must be at least 1")
        selected_modifiers = _selected_modifiers_payload(line.selected_modifiers)
        modifiers_total = _selected_modifiers_total(selected_modifiers)
        base_price = _base_price_with_discount(menu_item)
        subtotal = _round_money((base_price + modifiers_total) * line.quantity)
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
        category_name = getattr(getattr(menu_item, "category", None), "name", None)
        printer_name = _printer_name_for_category(category_name)
        item_print_jobs.append(
            (
                printer_name,
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
                mock_send_to_printer(
                    printer_name,
                    item_ticket,
                    order_type=getattr(order, "order_type", "dine_in"),
                    customer_name=getattr(order, "customer_name", None),
                )
                for printer_name, item_ticket in item_print_jobs
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
    current_user: User = Depends(require_roles(["admin", "cashier"])),
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
    order.status = "paid"
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
        await manager.broadcast("order_completed", payload)
        if (order.order_type or "").strip().lower() == "takeaway":
            await manager.broadcast("takeaways_updated", payload)
    return OrderResponseDetail.model_validate(order)
