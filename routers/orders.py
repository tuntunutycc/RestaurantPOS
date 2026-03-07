"""Orders API: create and manage orders."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import MenuItem, Order, OrderItem
from schemas import OrderCreate

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
