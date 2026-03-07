"""Pydantic schemas for request/response validation."""

from typing import List

from pydantic import BaseModel, ConfigDict


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
