"""Orders API: create and manage orders."""

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import MenuItem, Order, OrderItem
from schemas import OrderCreate, OrderItemDetail, OrderResponseDetail, OrderSubmitRequest, OrderSubmitResponse

router = APIRouter(prefix="/api")

OPEN_ORDER_STATUSES = ("open", "dining")


@router.post("/orders/")
async def create_order(
    request: Request,
    order_data: OrderCreate,
    db: Session = Depends(get_db),
):
    """
    Create or add to an order for a table (table-centric). If table already has an open/dining
    order, appends items to it; otherwise creates a new order. Keeps one active order per table.
    """
    if not order_data.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

    table_number = order_data.table_number
    existing = (
        db.query(Order)
        .filter(
            Order.table_number == table_number,
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
            subtotal = float(menu_item.price) * line.quantity
            existing_total += subtotal
            db.add(
                OrderItem(
                    order_id=existing.id,
                    menu_item_id=line.menu_item_id,
                    quantity=line.quantity,
                    subtotal=subtotal,
                )
            )
            added_items_detail.append(
                OrderItemDetail(
                    menu_item_name=menu_item.name,
                    quantity=line.quantity,
                    subtotal=subtotal,
                    menu_item_image_url=getattr(menu_item, "image_url", None),
                )
            )
        existing.total_amount = round(existing_total, 2)
        db.commit()
        db.refresh(existing)
        manager = getattr(request.app.state, "ws_manager", None)
        if manager:
            await manager.broadcast(
                "order_updated",
                {"table_id": table_number, "added_items": [d.model_dump(mode="json") for d in added_items_detail]},
            )
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
        subtotal = float(menu_item.price) * line.quantity
        total_amount += subtotal
        order_items_data.append(
            {"menu_item_id": line.menu_item_id, "quantity": line.quantity, "subtotal": subtotal}
        )

    db_order = Order(
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
            )
        )
    db.commit()
    db.refresh(db_order)
    full_order = (
        db.query(Order)
        .options(joinedload(Order.order_items).joinedload(OrderItem.menu_item))
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
):
    """List orders, optionally filtered by status. Eager-loads items and menu_item to avoid N+1."""
    q = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
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
def list_orders_by_table(db: Session = Depends(get_db)):
    """
    List one order per table (the canonical order for checkout). Cashier uses this so each
    table appears once with the order that has ALL items (initial + add-ons) and grand total.
    """
    q = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
        )
        .filter(Order.status.in_(CHECKOUT_ORDER_STATUSES))
        .order_by(Order.table_number, Order.id)
    )
    orders = q.all()
    by_table = {}
    for o in orders:
        by_table.setdefault(o.table_number, []).append(o)
    canonical = [_canonical_order_for_table(ords) for ords in by_table.values()]
    canonical = [o for o in canonical if o is not None]
    canonical.sort(key=lambda o: o.table_number)
    return [OrderResponseDetail.model_validate(o) for o in canonical]


@router.get("/orders/active-by-table/{table_id}", response_model=OrderResponseDetail)
def get_active_order_by_table(table_id: int, db: Session = Depends(get_db)):
    """
    Get the single canonical order for a table (all items + grand total). Prefers the
    order with status open/dining (the one we append add-ons to), then completed, then pending.
    """
    q = (
        db.query(Order)
        .options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
        )
        .filter(
            Order.table_number == table_id,
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


@router.put("/orders/{order_id}/status")
async def update_order_status(
    request: Request,
    order_id: int,
    body: OrderStatusUpdate,
    db: Session = Depends(get_db),
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


@router.post("/orders/submit", response_model=OrderSubmitResponse)
async def submit_order(
    request: Request,
    body: OrderSubmitRequest,
    db: Session = Depends(get_db),
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

    table_number = body.table_id
    # Find existing open/dining order (current dining session)
    order = (
        db.query(Order)
        .filter(
            Order.table_number == table_number,
            Order.status.in_(OPEN_ORDER_STATUSES),
        )
        .first()
    )

    is_new_order = order is None

    if order is None:
        # No open order yet: start new dining session, first batch = 1
        order = Order(table_number=table_number, status="open", total_amount=0.0)
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
        subtotal = float(menu_item.price) * line.quantity
        batch_total += subtotal
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=line.menu_item_id,
                quantity=line.quantity,
                subtotal=subtotal,
                batch_number=new_batch_number,
            )
        )
        batch_items_detail.append(
            OrderItemDetail(
                menu_item_name=menu_item.name,
                quantity=line.quantity,
                subtotal=subtotal,
                batch_number=new_batch_number,
                menu_item_image_url=getattr(menu_item, "image_url", None),
            )
        )

    # Update order running total and persist
    order.total_amount = float(order.total_amount) + batch_total
    db.commit()
    db.refresh(order)

    # Broadcast this batch only for Kitchen (KDS)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "new_order_batch",
            {
                "order_id": order.id,
                "table_number": table_number,
                "batch_number": new_batch_number,
                "is_new_order": is_new_order,
                "created_at": order.created_at.isoformat(),
                "items": [d.model_dump(mode="json") for d in batch_items_detail],
            },
        )

    return OrderSubmitResponse(
        id=order.id,
        table_number=order.table_number,
        total_amount=order.total_amount,
        is_new_order=is_new_order,
        message=(
            f"New order created for Table {table_number}"
            if is_new_order
            else f"Items added to Table {table_number}'s existing order (batch {new_batch_number})"
        ),
    )


class CheckoutRequest(BaseModel):
    """Request body for cashier checkout with payment information."""

    payment_method: str  # 'cash', 'mobile_money', etc.
    amount_tendered: float


@router.put("/orders/{order_id}/checkout", response_model=OrderResponseDetail)
def checkout_order(
    order_id: int,
    body: CheckoutRequest,
    db: Session = Depends(get_db),
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
    db.commit()
    db.refresh(order)
    return OrderResponseDetail.model_validate(order)
