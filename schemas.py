"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    """Schema for login request."""

    username: str
    password: str


class LoginPinRequest(BaseModel):
    """Schema for PIN login (4-digit code)."""

    pin_code: str

    @model_validator(mode="after")
    def pin_must_be_four_digits(self):
        if not (self.pin_code and len(self.pin_code) == 4 and self.pin_code.isdigit()):
            raise ValueError("pin_code must be exactly 4 digits")
        return self


class UserResponse(BaseModel):
    """Schema for user in API responses (no password)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str


class TokenResponse(BaseModel):
    """Schema for login response with JWT and user."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


StaffRole = Literal["admin", "waiter", "kitchen", "cashier"]
TableStatusLiteral = Literal["available", "occupied"]
OrderItemStatusLiteral = Literal["pending", "cooking", "served"]


class UserCreateRequest(BaseModel):
    """Admin request body for creating/updating a staff/admin user via PIN login."""

    username: str
    role: StaffRole
    pin_code: str

    @field_validator("pin_code")
    @classmethod
    def pin_code_must_be_four_digits(cls, v: str) -> str:
        if not (v and len(v) == 4 and v.isdigit()):
            raise ValueError("pin_code must be exactly 4 digits")
        return v


class UserAdminResponse(BaseModel):
    """User representation for the Admin panel (includes pin_code)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: StaffRole
    pin_code: str | None = None


class CategoryCreate(BaseModel):
    """Schema for creating a category."""

    name: str


class ZoneCreate(BaseModel):
    name: str


class ZoneUpdate(BaseModel):
    name: str


class ZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TableCreate(BaseModel):
    name: str
    zone_id: int
    status: TableStatusLiteral = "available"

    @model_validator(mode="before")
    @classmethod
    def support_legacy_name_or_number(cls, data):
        # Accept legacy payload shape: { name_or_number: "A1" }
        if isinstance(data, dict) and "name" not in data and "name_or_number" in data:
            data = dict(data)
            data["name"] = data.get("name_or_number")
        return data

    @property
    def name_or_number(self) -> str:
        return self.name


class TableUpdate(BaseModel):
    name: str | None = None
    zone_id: int | None = None
    status: TableStatusLiteral | None = None

    @model_validator(mode="before")
    @classmethod
    def support_legacy_name_or_number(cls, data):
        if isinstance(data, dict) and "name" not in data and "name_or_number" in data:
            data = dict(data)
            data["name"] = data.get("name_or_number")
        return data

    @property
    def name_or_number(self) -> str | None:
        return self.name


class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    zone_id: int
    status: TableStatusLiteral

    @property
    def name_or_number(self) -> str:
        return self.name


class ZoneGridResponse(ZoneResponse):
    tables: List[TableResponse] = []


# Backward-compatible alias used by existing routers.
class ZoneWithTablesResponse(ZoneGridResponse):
    pass


class TableGridItemResponse(TableResponse):
    active_order_id: int | None = None


class ZoneTableGridResponse(ZoneResponse):
    tables: List[TableGridItemResponse] = []


class CategoryResponse(BaseModel):
    """Schema for category in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ModifierOption(BaseModel):
    name: str
    price: float = 0.0


class ModifierGroup(BaseModel):
    group: str
    is_required: bool = False
    options: List[ModifierOption] = Field(default_factory=list)


class SelectedModifier(BaseModel):
    name: str
    price: float = 0.0
    group: str | None = None


class MenuItemCreate(BaseModel):
    """Schema for creating a menu item."""

    name: str
    price: float
    discount_price: float | None = None
    category_id: int
    description: str | None = None
    image_url: str | None = None
    is_available: bool = True
    modifiers_config: List[ModifierGroup] = Field(default_factory=list)


class MenuItemResponse(BaseModel):
    """Schema for menu item in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    discount_price: float | None = None
    category_id: int
    description: str | None = None
    image_url: str | None = None
    is_available: bool = True
    modifiers_config: List[ModifierGroup] = Field(default_factory=list)


class MenuItemRead(MenuItemResponse):
    """Compatibility alias for read responses."""

    pass


class MenuItemUpdate(BaseModel):
    """Partial update schema for menu item updates."""

    name: str | None = None
    price: float | None = None
    discount_price: float | None = None
    category_id: int | None = None
    description: str | None = None
    image_url: str | None = None
    is_available: bool | None = None
    modifiers_config: List[ModifierGroup] | None = None


class OrderItemCreate(BaseModel):
    """Schema for a single item when creating an order."""

    menu_item_id: int
    quantity: int
    selected_modifiers: List[SelectedModifier] = Field(default_factory=list)
    note: str | None = None
    special_instructions: str | None = None

    @model_validator(mode="before")
    @classmethod
    def support_note_alias(cls, data):
        if isinstance(data, dict):
            note = data.get("note")
            special = data.get("special_instructions")
            if note is None and special is not None:
                data = dict(data)
                data["note"] = special
            elif note is not None and special is None:
                data = dict(data)
                data["special_instructions"] = note
        return data


class OrderCreate(BaseModel):
    """Schema for creating an order."""

    table_id: int
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
    item_status: OrderItemStatusLiteral | None = None
    menu_item_image_url: str | None = None
    # For Kitchen tickets: who created this specific batch (ticket)
    waiter_name: str | None = None
    selected_modifiers: List[SelectedModifier] = Field(default_factory=list)
    note: str | None = None
    special_instructions: str | None = None


class OrderItemDetailsResponse(BaseModel):
    id: int
    menu_item_id: int
    menu_item_name: str
    quantity: int
    subtotal: float
    item_status: OrderItemStatusLiteral
    waiter_name: str | None = None
    selected_modifiers: List[SelectedModifier] = Field(default_factory=list)
    note: str | None = None
    special_instructions: str | None = None


class OrderItemRead(OrderItemDetailsResponse):
    """Read schema for order item including note."""

    pass


class OrderDetailsResponse(BaseModel):
    id: int
    table_id: int | None = None
    status: str
    total_amount: float
    discount_type: str | None = None
    discount_value: float | None = 0.0
    created_at: datetime
    items: List[OrderItemDetailsResponse]


class OrderResponseDetail(BaseModel):
    """Schema for a full order with its items (for KDS and order listing)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    table_id: int | None = None
    table_number: int
    status: str
    total_amount: float
    created_at: datetime
    items: List[OrderItemDetail]
    # For Cashier receipt: who served the latest (most recent) batch in this dining session.
    served_by_name: str | None = None
    # Payment information for cashier
    payment_method: str | None = None
    amount_tendered: float | None = None
    change_amount: float | None = None
    discount_type: str | None = None
    discount_value: float | None = 0.0

    @model_validator(mode="wrap")
    @classmethod
    def build_from_order(cls, data, handler):
        """Build from Order ORM: map order_items to items with menu_item name."""
        if hasattr(data, "order_items"):
            order = data
            # Served by = waiter who created the latest batch (highest batch_number).
            latest_oi = None
            try:
                latest_oi = max(order.order_items, key=lambda x: getattr(x, "batch_number", 1))
            except Exception:
                latest_oi = None
            served_by_name = (
                getattr(getattr(latest_oi, "created_by", None), "username", None)
                if latest_oi is not None
                else None
            )
            items = [
                OrderItemDetail(
                    menu_item_name=oi.menu_item.name,
                    quantity=oi.quantity,
                    subtotal=float(oi.subtotal),
                    batch_number=getattr(oi, "batch_number", 1),
                    item_status=getattr(oi, "item_status", getattr(oi, "status", "pending")),
                    menu_item_image_url=getattr(oi.menu_item, "image_url", None),
                    waiter_name=getattr(getattr(oi, "created_by", None), "username", None),
                    selected_modifiers=getattr(oi, "selected_modifiers", []) or [],
                    note=getattr(oi, "note", None) or getattr(oi, "special_instructions", None),
                    special_instructions=getattr(oi, "special_instructions", None),
                )
                for oi in order.order_items
            ]
            return cls(
                id=order.id,
                table_id=getattr(order, "table_id", None),
                table_number=order.table_number,
                status=order.status,
                total_amount=float(order.total_amount),
                created_at=order.created_at,
                items=items,
                served_by_name=served_by_name,
                payment_method=getattr(order, "payment_method", None),
                amount_tendered=getattr(order, "amount_tendered", None),
                change_amount=getattr(order, "change_amount", None),
                discount_type=getattr(order, "discount_type", None),
                discount_value=getattr(order, "discount_value", 0.0),
            )
        return handler(data)


class OrderRead(OrderResponseDetail):
    """Compatibility read schema for full order payload."""

    pass


class OrderCheckoutRequest(BaseModel):
    """Request body for cashier checkout with optional order-level discount."""

    payment_method: str  # 'cash', 'mobile_money', etc.
    amount_tendered: float
    discount_type: Literal["percentage", "amount"] | None = None
    discount_value: float | None = 0.0


class TodaySalesSummaryResponse(BaseModel):
    """Today's sales summary for analytics dashboard."""

    total_sales: float
    total_orders: int
    average_order_value: float
