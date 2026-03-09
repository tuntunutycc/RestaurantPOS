"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, model_validator


class CategoryCreate(BaseModel):
    """Schema for creating a category."""

    name: str


class CategoryResponse(BaseModel):
    """Schema for category in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MenuItemCreate(BaseModel):
    """Schema for creating a menu item."""

    name: str
    price: float
    category_id: int
    description: str | None = None
    image_url: str | None = None


class MenuItemResponse(BaseModel):
    """Schema for menu item in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    category_id: int
    description: str | None = None
    image_url: str | None = None


class OrderItemCreate(BaseModel):
    """Schema for a single item when creating an order."""

    menu_item_id: int
    quantity: int


class OrderCreate(BaseModel):
    """Schema for creating an order."""

    table_number: int
    items: List[OrderItemCreate]


class OrderSubmitRequest(BaseModel):
    """Schema for submit order (create new or add to existing). table_id = table number."""

    table_id: int
    items: List[OrderItemCreate]


class OrderSubmitResponse(BaseModel):
    """Response for order submit: indicates new vs add-on and message for UI."""

    id: int
    table_number: int
    total_amount: float
    is_new_order: bool
    message: str


class OrderItemDetail(BaseModel):
    """Schema for an order line in detailed order response (menu item name + quantity + optional image)."""

    menu_item_name: str
    quantity: int
    subtotal: float
    batch_number: int = 1
    batch_status: str | None = None
    menu_item_image_url: str | None = None


class OrderResponseDetail(BaseModel):
    """Schema for a full order with its items (for KDS and order listing)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    table_number: int
    status: str
    total_amount: float
    created_at: datetime
    items: List[OrderItemDetail]
    # Payment information for cashier
    payment_method: str | None = None
    amount_tendered: float | None = None
    change_amount: float | None = None

    @model_validator(mode="wrap")
    @classmethod
    def build_from_order(cls, data, handler):
        """Build from Order ORM: map order_items to items with menu_item name."""
        if hasattr(data, "order_items"):
            order = data
            items = [
                OrderItemDetail(
                    menu_item_name=oi.menu_item.name,
                    quantity=oi.quantity,
                    subtotal=float(oi.subtotal),
                    batch_number=getattr(oi, "batch_number", 1),
                    batch_status=getattr(oi, "batch_status", "pending"),
                    menu_item_image_url=getattr(oi.menu_item, "image_url", None),
                )
                for oi in order.order_items
            ]
            return cls(
                id=order.id,
                table_number=order.table_number,
                status=order.status,
                total_amount=float(order.total_amount),
                created_at=order.created_at,
                items=items,
                payment_method=getattr(order, "payment_method", None),
                amount_tendered=getattr(order, "amount_tendered", None),
                change_amount=getattr(order, "change_amount", None),
            )
        return handler(data)
