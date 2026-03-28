"""Orders API: create and manage orders."""

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user
from database import get_db
from models import MenuItem, Order, OrderItem, Table, User
from schemas import (
    OrderCreate,
    OrderDetailsResponse,
    OrderItemDetail,
    OrderItemDetailsResponse,
    OrderResponseDetail,
    OrderSubmitRequest,
    OrderSubmitResponse,
)

router = APIRouter(prefix="/api")

OPEN_ORDER_STATUSES = ("open", "dining")


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


@router.post("/orders/")
async def create_order(
    request: Request,
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or add to an order for a table (table-centric). If table already has an open/dining
    order, appends items to it; otherwise creates a new order. Keeps one active order per table.
    """
    if not order_data.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

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
            subtotal = (float(menu_item.price) + modifiers_total) * line.quantity
            existing_total += subtotal
            db.add(
                OrderItem(
                    order_id=existing.id,
                    menu_item_id=line.menu_item_id,
                    quantity=line.quantity,
                    subtotal=subtotal,
                    created_by_id=current_user.id,
                    selected_modifiers=selected_modifiers,
                    special_instructions=line.special_instructions,
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
                    special_instructions=line.special_instructions,
                )
            )
        existing.total_amount = round(existing_total, 2)
        previous_status = table.status
        table.status = "occupied"
        db.commit()
        db.refresh(existing)
        manager = getattr(request.app.state, "ws_manager", None)
        if manager:
            await manager.broadcast(
                "order_updated",
                {"table_id": table.id, "added_items": [d.model_dump(mode="json") for d in added_items_detail]},
            )
        if previous_status != table.status:
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
        subtotal = (float(menu_item.price) + modifiers_total) * line.quantity
        total_amount += subtotal
        order_items_data.append(
            {
                "menu_item_id": line.menu_item_id,
                "quantity": line.quantity,
                "subtotal": subtotal,
                "selected_modifiers": selected_modifiers,
                "special_instructions": line.special_instructions,
            }
        )

    db_order = Order(
        table_id=table.id,
        table_number=table_number,
        status="open",
        total_amount=round(total_amount, 2),
    )
    db.add(db_order)
    db.flush()
    for item_data in order_items_data:
        db.add(
            OrderItem(
                order_id=db_order.id,
                menu_item_id=item_data["menu_item_id"],
                quantity=item_data["quantity"],
                subtotal=item_data["subtotal"],
                created_by_id=current_user.id,
                selected_modifiers=item_data["selected_modifiers"],
                special_instructions=item_data["special_instructions"],
            )
        )
    previous_status = table.status
    table.status = "occupied"
    db.commit()
    db.refresh(db_order)
    if previous_status != table.status:
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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

    status: str


class BatchStatusUpdate(BaseModel):
    """Request body for updating one batch (ticket) status."""

    status: str


class OrderItemStatusUpdate(BaseModel):
    """Request body for updating one order item's status."""

    status: str


@router.put("/orders/{order_id}/status")
async def update_order_status(
    request: Request,
    order_id: int,
    body: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an order's status (e.g. completed). Broadcasts order_updated via WebSocket for kitchen."""
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


@router.put("/orders/{order_id}/batches/{batch_number}/status")
async def update_order_batch_status(
    request: Request,
    order_id: int,
    batch_number: int,
    body: BatchStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the status of a single batch (ticket) within an order.
    This ONLY touches OrderItem rows that belong to the given (order_id, batch_number).
    Other batches for the same order/table are not affected.
    """
    items = (
        db.query(OrderItem)
        .filter(
            OrderItem.order_id == order_id,
            OrderItem.batch_number == batch_number,
        )
        .all()
    )
    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"No items found for order {order_id} batch {batch_number}",
        )

    for oi in items:
        oi.batch_status = body.status
    db.commit()

    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "batch_completed",
            {
                "order_id": order_id,
                "batch_number": batch_number,
                "status": body.status,
            },
        )

    return {"order_id": order_id, "batch_number": batch_number, "status": body.status}


@router.get("/orders/{order_id}/details", response_model=OrderDetailsResponse)
def get_order_details(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
            special_instructions=getattr(oi, "special_instructions", None),
        )
        for oi in order.order_items
    ]
    return OrderDetailsResponse(
        id=order.id,
        table_id=getattr(order, "table_id", None),
        status=order.status,
        total_amount=float(order.total_amount),
        created_at=order.created_at,
        items=items,
    )


@router.put("/orders/{order_id}/items/{item_id}/status")
async def update_order_item_status(
    request: Request,
    order_id: int,
    item_id: int,
    body: OrderItemStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oi = (
        db.query(OrderItem)
        .filter(
            OrderItem.id == item_id,
            OrderItem.order_id == order_id,
        )
        .first()
    )
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")

    normalized_status = (body.status or "").strip().lower()
    allowed = {"pending", "cooking", "served"}
    if normalized_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Allowed: pending, cooking, served",
        )

    oi.item_status = normalized_status
    db.commit()
    db.refresh(oi)

    table_id = (
        db.query(Order.table_id)
        .filter(Order.id == order_id)
        .scalar()
    )

    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "table_grid_updated",
            {
                "refresh": True,
                "order_id": order_id,
                "item_id": item_id,
                "table_id": table_id,
                "item_status": getattr(getattr(oi, "item_status", None), "value", oi.item_status),
            },
        )

    return {
        "id": oi.id,
        "order_id": oi.order_id,
        "menu_item_id": oi.menu_item_id,
        "menu_item_name": getattr(getattr(oi, "menu_item", None), "name", None),
        "quantity": oi.quantity,
        "subtotal": float(oi.subtotal),
        "item_status": getattr(getattr(oi, "item_status", None), "value", oi.item_status),
        "waiter_name": getattr(getattr(oi, "created_by", None), "username", None),
        "selected_modifiers": getattr(oi, "selected_modifiers", []) or [],
        "special_instructions": getattr(oi, "special_instructions", None),
    }


@router.post("/orders/submit", response_model=OrderSubmitResponse)
async def submit_order(
    request: Request,
    body: OrderSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Table-centric batching submit endpoint.

    - If no open/dining Order for this table: create new Order and add items as batch_number = 1.
    - If open/dining Order exists: append items as a NEW batch (batch_number = max+1).
    - Always updates Order.total_amount.
    - Emits WebSocket event `new_order_batch` with ONLY the items in this batch, table_number and batch_number.
    """
    if not body.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

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
        # No open order yet: start new dining session, first batch = 1
        order = Order(
            table_id=table.id,
            table_number=table_number,
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

    for line in body.items:
        menu_item = db.query(MenuItem).filter(MenuItem.id == line.menu_item_id).first()
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item id {line.menu_item_id} not found")
        if line.quantity < 1:
            raise HTTPException(status_code=400, detail=f"Quantity for {menu_item.name} must be at least 1")
        selected_modifiers = _selected_modifiers_payload(line.selected_modifiers)
        modifiers_total = _selected_modifiers_total(selected_modifiers)
        subtotal = (float(menu_item.price) + modifiers_total) * line.quantity
        batch_total += subtotal
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=line.menu_item_id,
                quantity=line.quantity,
                subtotal=subtotal,
                batch_number=new_batch_number,
                created_by_id=current_user.id,
                batch_status="pending",
                selected_modifiers=selected_modifiers,
                special_instructions=line.special_instructions,
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
                batch_status="pending",
                selected_modifiers=selected_modifiers,
                special_instructions=line.special_instructions,
            )
        )

    # Update order running total and persist
    order.total_amount = float(order.total_amount) + batch_total
    previous_status = table.status
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
                "table_id": table.id,
                "table_number": table_number,
                "batch_number": new_batch_number,
                "is_new_order": is_new_order,
                "created_at": order.created_at.isoformat(),
                "items": [d.model_dump(mode="json") for d in batch_items_detail],
            },
        )
    if previous_status != table.status:
        await _broadcast_table_status_changed(request, table)

    return OrderSubmitResponse(
        id=order.id,
        table_number=order.table_number,
        total_amount=order.total_amount,
        is_new_order=is_new_order,
        message=(
            f"New order created for Table {table.name_or_number}"
            if is_new_order
            else f"Items added to Table {table.name_or_number}'s existing order (batch {new_batch_number})"
        ),
    )


class CheckoutRequest(BaseModel):
    """Request body for cashier checkout with payment information."""

    payment_method: str  # 'cash', 'mobile_money', etc.
    amount_tendered: float


@router.put("/orders/{order_id}/checkout", response_model=OrderResponseDetail)
async def checkout_order(
    request: Request,
    order_id: int,
    body: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Finalize payment for an order:
    - Validate amount_tendered >= total_amount
    - Compute change_amount = amount_tendered - total_amount
    - Set status = 'paid' and store payment details
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

    total = float(order.total_amount)
    tendered = float(body.amount_tendered)
    if tendered < total:
        raise HTTPException(
            status_code=400,
            detail=f"Amount tendered ({tendered:.2f}) is less than total ({total:.2f})",
        )

    change = tendered - total

    order.payment_method = body.payment_method
    order.amount_tendered = tendered
    order.change_amount = change
    order.status = "paid"
    table = db.query(Table).filter(Table.id == order.table_id).first() if order.table_id else None
    previous_status = table.status if table else None
    if table:
        table.status = "available"
    db.commit()
    db.refresh(order)
    if table and previous_status != table.status:
        await _broadcast_table_status_changed(request, table)
    return OrderResponseDetail.model_validate(order)
