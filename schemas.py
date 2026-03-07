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


class MenuItemResponse(BaseModel):
    """Schema for menu item in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    category_id: int


class OrderItemCreate(BaseModel):
    """Schema for a single item when creating an order."""

    menu_item_id: int
    quantity: int


class OrderCreate(BaseModel):
    """Schema for creating an order."""

    table_number: int
    items: List[OrderItemCreate]


class OrderItemDetail(BaseModel):
    """Schema for an order line in detailed order response (menu item name + quantity)."""

    menu_item_name: str
    quantity: int
    subtotal: float


class OrderResponseDetail(BaseModel):
    """Schema for a full order with its items (for KDS and order listing)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    table_number: int
    status: str
    total_amount: float
    created_at: datetime
    items: List[OrderItemDetail]

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
            )
        return handler(data)
