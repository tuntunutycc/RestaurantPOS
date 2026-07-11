"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    """Schema for login request."""

    username: str
    password: str
    device_id: str | None = None


class LoginPinRequest(BaseModel):
    """Schema for PIN login (4-digit code)."""

    pin_code: str
    device_id: str | None = None

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


StaffRole = Literal["root", "admin", "account", "cashier", "waiter"]
AdminStaffRole = Literal["cashier", "waiter", "account"]
RootAdminRole = Literal["admin"]
PrinterRouteLiteral = Literal["drinks", "food"]
PrinterBackendLiteral = Literal["file", "escpos_network"]
PrinterRenderModeLiteral = Literal["text", "image"]
TableStatusLiteral = Literal["available", "occupied"]
OrderItemStatusLiteral = Literal["pending", "cooking", "served", "cancelled"]
OrderStatusLiteral = Literal["pending", "open", "dining", "completed", "paid", "cancelled"]
MenuTaxTypeLiteral = Literal["none", "percentage", "fixed"]
MenuDiscountTypeLiteral = Literal["none", "percentage", "fixed"]


class UserCreateRequest(BaseModel):
    """Admin request body for creating/updating staff (cashier, waiter, account)."""

    username: str
    role: StaffRole
    pin_code: str | None = None
    password: str | None = None

    @field_validator("pin_code")
    @classmethod
    def pin_code_must_be_four_digits(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not (len(v) == 4 and v.isdigit()):
            raise ValueError("pin_code must be exactly 4 digits")
        return v


class RootAdminCreateRequest(BaseModel):
    """Root request body for creating/updating admin users (password login only)."""

    username: str
    password: str = ""


class RootSetupRequest(BaseModel):
    """One-time root account setup."""

    username: str
    password: str


class SetupStatusResponse(BaseModel):
    needs_setup: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    new_password: str


class UserAdminResponse(BaseModel):
    """User representation for the Admin panel (includes pin_code)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    pin_code: str | None = None
    is_active: bool = True


class AdminAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int
    actor_username: str | None = None
    action: str
    target_user_id: int | None = None
    target_username: str | None = None
    detail_json: dict | list | None = None
    created_at: datetime


class CategoryCreate(BaseModel):
    """Schema for creating a category."""

    name: str
    printer_route: PrinterRouteLiteral | None = None


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""

    name: str | None = None
    printer_route: PrinterRouteLiteral | None = None


class PrinterRouteEndpointResponse(BaseModel):
    """LAN endpoint for one kitchen printer route."""

    route_key: PrinterRouteLiteral
    host: str | None = None
    port: int = 9100


class PrinterRouteEndpointUpdate(BaseModel):
    """Update payload for one kitchen printer route endpoint."""

    route_key: PrinterRouteLiteral
    host: str | None = None
    port: int = Field(default=9100, ge=1, le=65535)


class KitchenPrinterSettingsResponse(BaseModel):
    """Admin view of kitchen printer backend + route endpoints."""

    backend: PrinterBackendLiteral = "file"
    render_mode: PrinterRenderModeLiteral = "text"
    paper_width_px: int = 576
    routes: list[PrinterRouteEndpointResponse]


class KitchenPrinterSettingsUpdate(BaseModel):
    """Admin update for kitchen printer backend + route endpoints."""

    backend: PrinterBackendLiteral
    render_mode: PrinterRenderModeLiteral = "text"
    paper_width_px: int = Field(default=576)
    routes: list[PrinterRouteEndpointUpdate]

    @model_validator(mode="after")
    def settings_must_be_valid(self):
        keys = {route.route_key for route in self.routes}
        if keys != {"drinks", "food"}:
            raise ValueError("routes must include exactly drinks and food")
        if self.paper_width_px not in (384, 576):
            raise ValueError("paper_width_px must be 384 or 576")
        return self


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
    printer_route: PrinterRouteLiteral | None = None


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
    discount_type: MenuDiscountTypeLiteral = "none"
    discount_value: float = 0.0
    takeaway_price: float | None = None
    tax_type: MenuTaxTypeLiteral = "none"
    tax_value: float = 0.0
    category_id: int
    description: str | None = None
    image_url: str | None = None
    is_available: bool = True
    is_promoted: bool = False
    modifiers_config: List[ModifierGroup] = Field(default_factory=list)


class MenuItemResponse(BaseModel):
    """Schema for menu item in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    discount_price: float | None = None
    discount_type: MenuDiscountTypeLiteral = "none"
    discount_value: float = 0.0
    takeaway_price: float | None = None
    tax_type: MenuTaxTypeLiteral = "none"
    tax_value: float = 0.0
    category_id: int
    description: str | None = None
    image_url: str | None = None
    is_available: bool = True
    is_promoted: bool = False
    modifiers_config: List[ModifierGroup] = Field(default_factory=list)


class MenuItemRead(MenuItemResponse):
    """Compatibility alias for read responses."""

    pass


class MenuItemUpdate(BaseModel):
    """Partial update schema for menu item updates."""

    name: str | None = None
    price: float | None = None
    discount_price: float | None = None
    discount_type: MenuDiscountTypeLiteral | None = None
    discount_value: float | None = None
    takeaway_price: float | None = None
    tax_type: MenuTaxTypeLiteral | None = None
    tax_value: float | None = None
    category_id: int | None = None
    description: str | None = None
    image_url: str | None = None
    is_available: bool | None = None
    is_promoted: bool | None = None
    modifiers_config: List[ModifierGroup] | None = None


class MenuItemAvailabilityUpdate(BaseModel):
    """Set menu item sold-out / in-stock flag. Admin and cashier only."""

    is_available: bool


class OrderItemCreate(BaseModel):
    """Schema for a single item when creating an order."""

    menu_item_id: int
    quantity: int
    is_takeaway: bool = False
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

    table_id: int | None = None
    order_type: Literal["dine_in", "takeaway"] = "dine_in"
    customer_name: str | None = None
    items: List[OrderItemCreate]


class OrderSubmitRequest(BaseModel):
    """Schema for submit order (create new or add to existing). table_id = table number."""

    order_id: int | None = None
    table_id: int | None = None
    order_type: Literal["dine_in", "takeaway"] = "dine_in"
    customer_name: str | None = None
    items: List[OrderItemCreate]


class OrderSubmitResponse(BaseModel):
    """Response for order submit: indicates new vs add-on and message for UI."""

    id: int
    table_number: int | None = None
    total_amount: float
    is_new_order: bool
    message: str


class OrderCreateResponse(BaseModel):
    """Response for create-order endpoint with summary fields."""

    id: int
    table_number: int | None = None
    status: str
    total_amount: float


class OrderStatusUpdateResponse(BaseModel):
    """Response for order status update endpoint."""

    id: int
    status: str


class OrderItemDetail(BaseModel):
    """Schema for an order line in detailed order response (menu item name + quantity + optional image)."""

    menu_item_name: str
    quantity: int
    subtotal: float
    unit_tax_at_sale: float | None = 0.0
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
    unit_price_at_sale: float | None = None
    unit_discount_at_sale: float | None = 0.0
    unit_tax_at_sale: float | None = 0.0
    item_status: OrderItemStatusLiteral
    is_takeaway: bool = False
    waiter_name: str | None = None
    selected_modifiers: List[SelectedModifier] = Field(default_factory=list)
    note: str | None = None
    special_instructions: str | None = None


class OrderItemRead(OrderItemDetailsResponse):
    """Read schema for order item including note."""

    pass


class OrderItemStatusUpdateRequest(BaseModel):
    """Request body for updating one order item's status."""

    status: OrderItemStatusLiteral

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        return str(v or "").strip().lower()


class OrderDetailsResponse(BaseModel):
    id: int
    table_id: int | None = None
    table_number: int | None = None
    order_type: str = "dine_in"
    customer_name: str | None = None
    status: str
    total_amount: float
    tax_amount: float | None = 0.0
    discount_type: str | None = None
    discount_value: float | None = 0.0
    created_at: datetime
    waiter_name: str | None = None
    served_by_name: str | None = None
    items: List[OrderItemDetailsResponse]
    breakdown_subtotal: float = 0.0
    breakdown_discount_total: float = 0.0
    breakdown_tax_total: float = 0.0
    breakdown_grand_total: float = 0.0


class OrderResponseDetail(BaseModel):
    """Schema for a full order with its items (for KDS and order listing)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    table_id: int | None = None
    table_number: int | None = None
    order_type: str = "dine_in"
    customer_name: str | None = None
    status: str
    total_amount: float
    created_at: datetime
    items: List[OrderItemDetail]
    # Order-taking staff who opened the order.
    waiter_name: str | None = None
    # Latest batch submitter (may differ when another staff adds items).
    served_by_name: str | None = None
    # Payment information for cashier
    payment_method: str | None = None
    amount_tendered: float | None = None
    change_amount: float | None = None
    tax_amount: float | None = 0.0
    discount_type: str | None = None
    discount_value: float | None = 0.0

    @model_validator(mode="wrap")
    @classmethod
    def build_from_order(cls, data, handler):
        """Build from Order ORM: map order_items to items with menu_item name."""
        if hasattr(data, "order_items"):
            order = data
            deleted_item_label = "[Deleted Item]"
            deleted_user_label = "[Deleted User]"
            latest_oi = None
            try:
                latest_oi = max(order.order_items, key=lambda x: getattr(x, "batch_number", 1))
            except Exception:
                latest_oi = None
            served_by_name = (
                (
                    getattr(getattr(latest_oi, "created_by", None), "username", None)
                    if (
                        latest_oi is not None
                        and getattr(latest_oi, "created_by", None) is not None
                        and not bool(getattr(getattr(latest_oi, "created_by", None), "is_deleted", False))
                    )
                    else (
                        deleted_user_label
                        if latest_oi is not None and getattr(latest_oi, "created_by_id", None) is not None
                        else None
                    )
                )
                if latest_oi is not None
                else None
            )
            order_creator = getattr(order, "created_by", None)
            if order_creator is not None and not bool(getattr(order_creator, "is_deleted", False)):
                waiter_name = getattr(order_creator, "username", None)
            elif getattr(order, "created_by_id", None) is not None:
                waiter_name = deleted_user_label
            else:
                waiter_name = None
            items = [
                OrderItemDetail(
                    menu_item_name=(
                        getattr(getattr(oi, "menu_item", None), "name", None)
                        if (
                            getattr(oi, "menu_item", None) is not None
                            and not bool(getattr(getattr(oi, "menu_item", None), "is_deleted", False))
                        )
                        else (getattr(oi, "menu_item_name_at_sale", None) or deleted_item_label)
                    ),
                    quantity=oi.quantity,
                    subtotal=float(oi.subtotal),
                    unit_tax_at_sale=float(getattr(oi, "unit_tax_at_sale", 0.0) or 0.0),
                    batch_number=getattr(oi, "batch_number", 1),
                    item_status=getattr(oi, "item_status", getattr(oi, "status", "pending")),
                    menu_item_image_url=getattr(oi.menu_item, "image_url", None),
                    waiter_name=(
                        getattr(getattr(oi, "created_by", None), "username", None)
                        if (
                            getattr(oi, "created_by", None) is not None
                            and not bool(getattr(getattr(oi, "created_by", None), "is_deleted", False))
                        )
                        else (
                            deleted_user_label
                            if getattr(oi, "created_by_id", None) is not None
                            else None
                        )
                    ),
                    selected_modifiers=getattr(oi, "selected_modifiers", []) or [],
                    note=getattr(oi, "note", None) or getattr(oi, "special_instructions", None),
                    special_instructions=getattr(oi, "special_instructions", None),
                )
                for oi in order.order_items
            ]
            return cls(
                id=order.id,
                table_id=getattr(order, "table_id", None),
                table_number=getattr(order, "table_number", None),
                order_type=getattr(order, "order_type", "dine_in"),
                customer_name=getattr(order, "customer_name", None),
                status=order.status,
                total_amount=float(order.total_amount),
                created_at=order.created_at,
                items=items,
                waiter_name=waiter_name,
                served_by_name=served_by_name,
                payment_method=getattr(order, "payment_method", None),
                amount_tendered=getattr(order, "amount_tendered", None),
                change_amount=getattr(order, "change_amount", None),
                tax_amount=getattr(order, "tax_amount", 0.0),
                discount_type=getattr(order, "discount_type", None),
                discount_value=getattr(order, "discount_value", 0.0),
            )
        return handler(data)


class OrderRead(OrderResponseDetail):
    """Compatibility read schema for full order payload."""

    pass


class OrderCheckoutRequest(BaseModel):
    """Request body for cashier checkout with optional order-level discount."""

    payment_method: str
    amount_tendered: float
    discount_type: Literal["percentage", "amount"] | None = None
    discount_value: float | None = 0.0

    @field_validator("payment_method", mode="before")
    @classmethod
    def normalize_payment_method(cls, v):
        raw = str(v or "").strip().lower().replace(" ", "_")
        if raw in ("cash",):
            return "cash"
        if raw in ("mobile_money", "mobilemoney"):
            return "mobile_money"
        raise ValueError("payment_method must be 'cash' or 'mobile_money'")


class PaymentMethodTotalsResponse(BaseModel):
    """Aggregated sales for one period grouped by payment method."""

    cash: float = 0.0
    mobile_money: float = 0.0
    total: float = 0.0


class SalesBreakdownResponse(BaseModel):
    """Today and current-month sales split by Cash vs Mobile Money."""

    today: PaymentMethodTotalsResponse
    month: PaymentMethodTotalsResponse


class TodaySalesSummaryResponse(BaseModel):
    """Today's sales summary for analytics dashboard."""

    total_sales: float
    total_orders: int
    average_order_value: float


class TopSellingItemResponse(BaseModel):
    """One row for top-selling items chart."""

    item_name: str
    quantity_sold: int


class HourlySalesTrendResponse(BaseModel):
    """One row for hourly sales trend chart."""

    hour: str
    total: float


class DailySalesPointResponse(BaseModel):
    """One row for daily sales history chart."""

    date: str
    total: float


class MonthlySalesPointResponse(BaseModel):
    """One row for monthly sales history chart."""

    month: str
    total: float


class CategorySalesPointResponse(BaseModel):
    """One row for category sales breakdown chart."""

    category_name: str
    total_sales: float


class CancelledItemCountResponse(BaseModel):
    """One row for top cancelled items list."""

    item_name: str
    count: int


class CancellationsSummaryResponse(BaseModel):
    """Summary payload for cancellations analytics."""

    total_cancelled_items: int
    total_lost_revenue: float
    top_cancelled_items: List[CancelledItemCountResponse]


class StaffSalesPointResponse(BaseModel):
    """Sales total attributed to one staff member."""

    user_id: int
    username: str
    role: str
    total_sales: float
    order_count: int = 0


class PromotedStaffSalesResponse(BaseModel):
    """Promoted menu item sales attributed to order-taking staff."""

    user_id: int
    username: str
    role: str
    total_sales: float
    quantity: int = 0
    line_count: int = 0


class ActiveTakeawayOrderResponse(BaseModel):
    """Schema for active takeaway orders list."""

    id: int
    table_id: int | None = None
    order_type: str = "takeaway"
    customer_name: str | None = None
    waiter_name: str | None = None
    served_by_name: str | None = None
    total_amount: float
    created_at: datetime
    items: List[OrderItemDetailsResponse]
    breakdown_subtotal: float = 0.0
    breakdown_discount_total: float = 0.0
    breakdown_tax_total: float = 0.0
    breakdown_grand_total: float = 0.0


class PredefinedInstructionCreate(BaseModel):
    """Schema for creating a predefined instruction tag."""

    text: str

    @field_validator("text")
    @classmethod
    def normalize_text(cls, v):
        text = str(v or "").strip()
        if not text:
            raise ValueError("text is required")
        if len(text) > 255:
            raise ValueError("text must be at most 255 characters")
        return text


class PredefinedInstructionResponse(BaseModel):
    """Predefined instruction tag in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
