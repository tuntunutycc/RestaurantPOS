"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Annotated, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.item_names import order_line_display_name


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
PrinterRoleLiteral = Literal["cashier", "kitchen", "bar", "other"]
PrinterRouteLiteral = Literal["drinks", "food"]
PrinterEndpointRouteLiteral = Literal["drinks", "food", "cashier"]
PrinterBackendLiteral = Literal["file", "escpos_network", "windows_printer"]
PrinterRenderModeLiteral = Literal["text", "image"]

TableStatusLiteral = Literal["available", "occupied"]
OrderItemStatusLiteral = Literal["pending", "cooking", "served", "cancelled"]
OrderStatusLiteral = Literal["pending", "open", "dining", "completed", "paid", "cancelled"]
# Sanity limit for any single money amount typed in by staff (1 billion Ks).
# Keeps totals finite; see specs/feature-menu-price-safety.
MAX_MENU_MONEY = 1_000_000_000.0
# Prices, discounts and taxes of a menu item: finite, 0 … MAX.
MenuMoney = Annotated[float, Field(ge=0, le=MAX_MENU_MONEY, allow_inf_nan=False)]
# Modifier option prices may be negative ("no meat -500"), but always finite.
ModifierMoney = Annotated[
    float, Field(ge=-MAX_MENU_MONEY, le=MAX_MENU_MONEY, allow_inf_nan=False)
]

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
    """LAN endpoint for one printer route (kitchen or cashier)."""

    route_key: PrinterEndpointRouteLiteral
    host: str | None = None
    port: int = 9100


class PrinterRouteEndpointUpdate(BaseModel):
    """Update payload for one printer route endpoint."""

    route_key: PrinterEndpointRouteLiteral
    host: str | None = None
    port: int = Field(default=9100, ge=1, le=65535)


# How kitchen slips are printed on submit (specs/feature-kitchen-slip-mode):
# per_item = one slip per order line, combined = one slip per printer route.
KitchenSlipModeLiteral = Literal["per_item", "combined"]


class KitchenPrinterSettingsResponse(BaseModel):
    """Admin view of global print backend settings (hosts live on Printer CRUD)."""

    backend: PrinterBackendLiteral = "file"
    render_mode: PrinterRenderModeLiteral = "text"
    paper_width_px: int = 576
    kitchen_slip_mode: KitchenSlipModeLiteral = "per_item"
    # Copies of each combined kitchen slip; ignored in per_item mode.
    kitchen_slip_copies: int = 1
    routes: list[PrinterRouteEndpointResponse] = Field(default_factory=list)


class KitchenPrinterSettingsUpdate(BaseModel):
    """Admin update for global print backend settings."""

    backend: PrinterBackendLiteral
    render_mode: PrinterRenderModeLiteral = "text"
    paper_width_px: int = Field(default=576)
    # Omitted = keep the stored mode (clients that predate this field).
    kitchen_slip_mode: KitchenSlipModeLiteral | None = None
    # Omitted = keep the stored value. strict: "2" or 2.0 are not accepted.
    kitchen_slip_copies: int | None = Field(default=None, ge=1, le=3, strict=True)
    routes: list[PrinterRouteEndpointUpdate] = Field(default_factory=list)

    @model_validator(mode="after")
    def settings_must_be_valid(self):
        if self.paper_width_px not in (384, 576):
            raise ValueError("paper_width_px must be 384 or 576")
        return self


class PrinterResponse(BaseModel):
    """Named printer with role for Admin CRUD and terminal selection."""

    id: int
    name: str
    host: str | None = None
    port: int = 9100
    windows_printer_name: str | None = None
    role: PrinterRoleLiteral
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class PrinterCreate(BaseModel):
    """Create a printer."""

    name: str = Field(min_length=1, max_length=64)
    host: str | None = None
    port: int = Field(default=9100, ge=1, le=65535)
    windows_printer_name: str | None = Field(default=None, max_length=256)
    role: PrinterRoleLiteral
    is_active: bool = True

    @field_validator("windows_printer_name")
    @classmethod
    def normalize_windows_printer_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class PrinterUpdate(BaseModel):
    """Update a printer (partial)."""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    windows_printer_name: str | None = Field(default=None, max_length=256)
    role: PrinterRoleLiteral | None = None
    is_active: bool | None = None

    @field_validator("windows_printer_name")
    @classmethod
    def normalize_windows_printer_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class WindowsPrinterNameItem(BaseModel):
    name: str


class WindowsPrinterListResponse(BaseModel):
    """Installed Windows print queues (empty when not on Windows / no pywin32)."""

    available: bool
    printers: list[WindowsPrinterNameItem] = Field(default_factory=list)
    message: str | None = None


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
    price: ModifierMoney = 0.0


class ModifierGroup(BaseModel):
    group: str = ""
    is_required: bool = False
    options: List[ModifierOption] = Field(default_factory=list)


class SelectedModifier(BaseModel):
    name: str
    price: ModifierMoney = 0.0
    group: str | None = None
    quantity: int = Field(default=1, ge=1)


def _normalize_modifiers_config(value):
    """Tolerate legacy/null DB values so old installs keep serving menu APIs."""
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    if not value:
        return []
    first = value[0]
    # Legacy flat option list: [{name, price}, ...] → one optional group.
    if isinstance(first, dict) and "options" not in first and "name" in first:
        return [{"group": "", "is_required": False, "options": value}]
    return value


def _clean_menu_item_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("name must not be blank")
    if len(cleaned) > 255:
        raise ValueError("name must be at most 255 characters")
    return cleaned


def _check_percentages(
    discount_type: str | None,
    discount_value: float | None,
    tax_type: str | None,
    tax_value: float | None,
) -> None:
    if discount_type == "percentage" and discount_value is not None and discount_value > 100:
        raise ValueError("discount_value cannot be more than 100 for a percentage discount")
    if tax_type == "percentage" and tax_value is not None and tax_value > 100:
        raise ValueError("tax_value cannot be more than 100 for a percentage tax")


class MenuItemCreate(BaseModel):
    """Schema for creating a menu item."""

    name: str
    price: MenuMoney
    discount_price: MenuMoney | None = None
    discount_type: MenuDiscountTypeLiteral = "none"
    discount_value: MenuMoney = 0.0
    takeaway_price: MenuMoney | None = None
    tax_type: MenuTaxTypeLiteral = "none"
    tax_value: MenuMoney = 0.0
    category_id: int
    description: str | None = None
    image_url: str | None = None
    is_available: bool = True
    is_promoted: bool = False
    modifiers_config: List[ModifierGroup] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return _clean_menu_item_name(v)

    @field_validator("modifiers_config", mode="before")
    @classmethod
    def coerce_modifiers_config(cls, v):
        return _normalize_modifiers_config(v)

    @model_validator(mode="after")
    def percentages_within_100(self):
        _check_percentages(self.discount_type, self.discount_value, self.tax_type, self.tax_value)
        return self


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

    @field_validator("modifiers_config", mode="before")
    @classmethod
    def coerce_modifiers_config(cls, v):
        return _normalize_modifiers_config(v)


class MenuItemRead(MenuItemResponse):
    """Compatibility alias for read responses."""

    pass


# Columns that cannot be empty: sending them as null used to end in a 500.
_MENU_ITEM_NOT_NULLABLE = (
    "name",
    "price",
    "discount_type",
    "discount_value",
    "tax_type",
    "tax_value",
    "category_id",
    "is_available",
    "is_promoted",
    "modifiers_config",
)


class MenuItemUpdate(BaseModel):
    """Partial update schema for menu item updates."""

    name: str | None = None
    price: MenuMoney | None = None
    discount_price: MenuMoney | None = None
    discount_type: MenuDiscountTypeLiteral | None = None
    discount_value: MenuMoney | None = None
    takeaway_price: MenuMoney | None = None
    tax_type: MenuTaxTypeLiteral | None = None
    tax_value: MenuMoney | None = None
    category_id: int | None = None
    description: str | None = None
    image_url: str | None = None
    is_available: bool | None = None
    is_promoted: bool | None = None
    modifiers_config: List[ModifierGroup] | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str | None) -> str | None:
        return None if v is None else _clean_menu_item_name(v)

    @field_validator("modifiers_config", mode="before")
    @classmethod
    def coerce_modifiers_config(cls, v):
        if v is None:
            return None
        return _normalize_modifiers_config(v)

    @model_validator(mode="after")
    def no_null_for_required_fields_and_percentages(self):
        for field in _MENU_ITEM_NOT_NULLABLE:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        _check_percentages(self.discount_type, self.discount_value, self.tax_type, self.tax_value)
        return self


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
    warning: str | None = None


class PrinterRouteHealthItem(BaseModel):
    route: str
    online: bool
    status: Literal["online", "offline", "skipped"]
    host: str | None = None
    port: int | None = None
    message: str


class PrinterNamedHealthItem(BaseModel):
    """Per Admin printer-row probe (Windows queue or LAN TCP)."""

    printer_id: int
    name: str
    role: str
    online: bool
    status: Literal["online", "offline", "skipped"]
    target: str | None = None
    message: str
    backend: str


class PrinterHealthResponse(BaseModel):
    backend: str
    printers: list[PrinterRouteHealthItem] = Field(default_factory=list)
    named_printers: list[PrinterNamedHealthItem] = Field(default_factory=list)
    all_online: bool
    warning: str | None = None


class PrinterTestPrintResponse(BaseModel):
    """Result of admin Print Test for one named printer."""

    ok: bool
    printer_id: int
    printer_name: str
    role: str
    backend: str
    target: str
    message: str
    error: str | None = None
    hint: str | None = None


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
    unit_price_at_sale: float | None = None
    unit_discount_at_sale: float | None = 0.0
    unit_tax_at_sale: float | None = 0.0
    batch_number: int = 1
    item_status: OrderItemStatusLiteral | None = None
    menu_item_image_url: str | None = None
    # For Kitchen tickets: who created this specific batch (ticket)
    waiter_name: str | None = None
    selected_modifiers: List[SelectedModifier] = Field(default_factory=list)
    note: str | None = None
    special_instructions: str | None = None
    is_takeaway: bool = False


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
    # Daily voucher number (YYYYMMDD-NNNN), given at checkout; null before payment.
    voucher_no: str | None = None
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
    # Daily voucher number (YYYYMMDD-NNNN), given at checkout; null before payment
    # and for orders made before the feature (specs/feature-voucher-number).
    voucher_no: str | None = None
    total_amount: float
    created_at: datetime
    items: List[OrderItemDetail]
    # Order-taking staff who opened the order.
    waiter_name: str | None = None
    # Latest batch submitter (may differ when another staff adds items).
    served_by_name: str | None = None
    # Free-text cashier label captured at checkout (receipt).
    cashier_name: str | None = None
    # Payment information for cashier
    # cash | kpay | mmqr | split (mobile_money only on orders from before KPay/MMQR).
    payment_method: str | None = None
    cash_amount: float | None = None
    kpay_amount: float | None = None
    mmqr_amount: float | None = None
    # All mobile money = kpay_amount + mmqr_amount.
    mobile_money_amount: float | None = None
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
                    # Sold-as name first (specs/feature-snapshot-first-names).
                    menu_item_name=order_line_display_name(oi, deleted_item_label),
                    quantity=oi.quantity,
                    subtotal=float(oi.subtotal),
                    unit_price_at_sale=(
                        float(getattr(oi, "unit_price_at_sale"))
                        if getattr(oi, "unit_price_at_sale", None) is not None
                        else None
                    ),
                    unit_discount_at_sale=float(
                        getattr(oi, "unit_discount_at_sale", 0.0) or 0.0
                    ),
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
                    is_takeaway=bool(getattr(oi, "is_takeaway", False)),
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
                voucher_no=getattr(order, "voucher_no", None),
                total_amount=float(order.total_amount),
                created_at=order.created_at,
                items=items,
                waiter_name=waiter_name,
                served_by_name=served_by_name,
                cashier_name=getattr(order, "cashier_name", None),
                payment_method=getattr(order, "payment_method", None),
                cash_amount=getattr(order, "cash_amount", None),
                kpay_amount=getattr(order, "kpay_amount", None),
                mmqr_amount=getattr(order, "mmqr_amount", None),
                mobile_money_amount=getattr(order, "mobile_money_amount", None),
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
    """Checkout body: one method + amount_tendered, or explicit amounts (split).

    Methods: cash | kpay | mmqr | split. See specs/feature-payment-kpay-mmqr.
    """

    payment_method: str | None = None
    # Money fields refuse NaN / Infinity: they compare as "not less than the
    # total", so the order would be marked paid without any money counted.
    amount_tendered: float | None = Field(default=None, allow_inf_nan=False)
    # Cash handed over (may be more than the cash part of the bill → change).
    cash_amount: float | None = Field(default=None, allow_inf_nan=False)
    kpay_amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    mmqr_amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    # No longer accepted. Declared so a client that still sends it gets a clear
    # 422 instead of having part of the payment silently ignored.
    mobile_money_amount: float | None = Field(default=None, allow_inf_nan=False)
    discount_type: Literal["percentage", "amount"] | None = None
    discount_value: float | None = Field(default=0.0, allow_inf_nan=False)
    issue_receipt: bool = True
    printer_id: int | None = None
    cashier_name: str | None = None

    @field_validator("cashier_name", mode="before")
    @classmethod
    def normalize_cashier_name(cls, v):
        if v is None:
            return None
        name = str(v).strip()
        if not name:
            return None
        return name[:128]

    @field_validator("payment_method", mode="before")
    @classmethod
    def normalize_payment_method(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        raw = str(v).strip().lower().replace(" ", "_")
        if raw in ("cash",):
            return "cash"
        if raw in ("kpay", "mmqr", "split"):
            return raw
        if raw in ("mobile_money", "mobilemoney", "mobile"):
            raise ValueError(
                "Mobile Money is no longer a payment method. Choose 'kpay' or 'mmqr'."
            )
        raise ValueError("payment_method must be 'cash', 'kpay', 'mmqr', or 'split'")

    @field_validator("mobile_money_amount", mode="after")
    @classmethod
    def reject_unspecified_mobile_amount(cls, v):
        if v is not None and float(v) != 0.0:
            raise ValueError(
                "mobile_money_amount is no longer accepted. Send kpay_amount and/or mmqr_amount."
            )
        return v


class OrderCheckoutResponse(OrderResponseDetail):
    """Checkout result: paid order payload plus optional receipt-print warning."""

    warning: str | None = None


class PrintJobResponse(BaseModel):
    """One queued slip. Also the payload of WebSocket event `print_job_updated`."""

    id: int
    order_id: int
    order_item_id: int | None = None
    kind: Literal["kitchen", "receipt"]
    route: str
    print_status: Literal["pending", "printed", "failed"]
    error_message: str | None = None
    attempts: int = 0
    # What the slip is ("Mohinga x2", "Receipt") and where it belongs (table / customer).
    item_label: str
    location_label: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    printed_at: datetime | None = None


class PrintRetryResponse(BaseModel):
    """Result of POST /api/orders/{order_id}/retry-print."""

    order_id: int
    requeued: int
    skipped: int
    message: str
    jobs: list[PrintJobResponse] = Field(default_factory=list)


class PaymentMethodTotalsResponse(BaseModel):
    """Aggregated sales for one period grouped by payment method."""

    cash: float = 0.0
    kpay: float = 0.0
    mmqr: float = 0.0
    # All mobile money: kpay + mmqr + mobile money from before they were told apart.
    mobile_money: float = 0.0
    total: float = 0.0
    # Order revenue (tax-aware). `total` remains cash + mobile for backward compatibility.
    subtotal_revenue: float = 0.0
    total_tax: float = 0.0
    grand_total_revenue: float = 0.0


class SalesBreakdownResponse(BaseModel):
    """Today and current-month sales split by Cash, KPay and MMQR."""

    today: PaymentMethodTotalsResponse
    month: PaymentMethodTotalsResponse


class SalesPeriodReportResponse(BaseModel):
    """Aggregated sales for one daily or monthly period (tax-aware)."""

    period: Literal["daily", "monthly"]
    date: str
    total_orders: int = 0
    subtotal_revenue: float = 0.0
    total_tax: float = 0.0
    grand_total_revenue: float = 0.0
    total_cash: float = 0.0
    total_kpay: float = 0.0
    total_mmqr: float = 0.0
    # All mobile money: total_kpay + total_mmqr + mobile money from before they were told apart.
    total_mobile: float = 0.0


class TodaySalesSummaryResponse(BaseModel):
    """Today's sales summary for analytics dashboard."""

    total_sales: float  # tax-inclusive (grand); kept for backward compatibility
    total_orders: int
    average_order_value: float
    subtotal_revenue: float = 0.0
    total_tax: float = 0.0
    grand_total_revenue: float = 0.0


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


class CashierSalesPointResponse(StaffSalesPointResponse):
    """One cashier's paid orders, split by how they were paid."""

    cash: float = 0.0
    kpay: float = 0.0
    mmqr: float = 0.0
    # Mobile money from before KPay / MMQR were told apart; 0 on a cleared database.
    mobile_unspecified: float = 0.0


class PromotedStaffSalesResponse(BaseModel):
    """Promoted menu item sales attributed to order-taking staff."""

    user_id: int
    username: str
    role: str
    total_sales: float
    quantity: int = 0
    line_count: int = 0


class DailyOrderHistoryLine(BaseModel):
    """One active (non-cancelled) line on a paid order for daily history."""

    id: int
    menu_item_name: str
    quantity: int
    subtotal: float
    is_takeaway: bool = False
    selected_modifiers: List[SelectedModifier] = Field(default_factory=list)
    note: str | None = None


class DailyOrderHistoryOrder(BaseModel):
    """Paid order summary for one calendar day (includes lines for detail modal)."""

    id: int
    # Daily voucher number (YYYYMMDD-NNNN); null for orders made before the feature.
    voucher_no: str | None = None
    created_at: datetime
    total_amount: float
    order_type: str = "dine_in"
    customer_name: str | None = None
    table_id: int | None = None
    payment_method: str | None = None
    # Parts of the bill by method (a split shows them in the detail view).
    cash_amount: float | None = None
    kpay_amount: float | None = None
    mmqr_amount: float | None = None
    mobile_money_amount: float | None = None
    items: List[DailyOrderHistoryLine] = Field(default_factory=list)


class DailyOrderHistoryResponse(BaseModel):
    """Daily paid-order history payload."""

    date: str
    orders: List[DailyOrderHistoryOrder] = Field(default_factory=list)
    order_count: int = 0
    grand_total: float = 0.0


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
