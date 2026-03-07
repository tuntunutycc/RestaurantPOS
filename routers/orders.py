"""Orders API: create and manage orders."""

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import MenuItem, Order, OrderItem
from schemas import OrderCreate, OrderResponseDetail

router = APIRouter(prefix="/api")


@router.post("/orders/")
def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """Create an order with items. Computes subtotals and total from menu item prices."""
    if not order_data.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

    total_amount = 0.0
    order_items_data = []

    for line in order_data.items:
        menu_item = db.query(MenuItem).filter(MenuItem.id == line.menu_item_id).first()
        if not menu_item:
            raise HTTPException(
                status_code=404,
                detail=f"Menu item with id {line.menu_item_id} not found",
            )
        if line.quantity < 1:
            raise HTTPException(
                status_code=400,
                detail=f"Quantity for item {menu_item.name} must be at least 1",
            )
        subtotal = float(menu_item.price) * line.quantity
        total_amount += subtotal
        order_items_data.append(
            {
                "menu_item_id": line.menu_item_id,
                "quantity": line.quantity,
                "subtotal": subtotal,
            }
        )

    db_order = Order(
        table_number=order_data.table_number,
        status="pending",
        total_amount=round(total_amount, 2),
    )
    db.add(db_order)
    db.flush()  # get db_order.id

    for item_data in order_items_data:
        db_item = OrderItem(
            order_id=db_order.id,
            menu_item_id=item_data["menu_item_id"],
            quantity=item_data["quantity"],
            subtotal=item_data["subtotal"],
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_order)

    return {
        "id": db_order.id,
        "table_number": db_order.table_number,
        "status": db_order.status,
        "total_amount": db_order.total_amount,
    }


@router.get("/orders/", response_model=list[OrderResponseDetail])
def list_orders(
    status: str | None = Query(None, description="Filter by status (e.g. pending, completed)"),
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
    if status is not None:
        q = q.filter(Order.status == status)
    orders = q.all()
    return [OrderResponseDetail.model_validate(o) for o in orders]


class OrderStatusUpdate(BaseModel):
    """Request body for updating order status."""

    status: str


@router.put("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update an order's status (e.g. completed)."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = body.status
    db.commit()
    db.refresh(order)
    return {"id": order.id, "status": order.status}
