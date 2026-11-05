"""SQLAlchemy models for the Restaurant POS system."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import relationship, synonym

from database import Base


class Category(Base):
    """Menu category (e.g. Appetizers, Mains, Drinks)."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    # Kitchen print route: drinks | food | null (null defaults to food at dispatch).
    printer_route = Column(String(32), nullable=True)

    menu_items = relationship("MenuItem", back_populates="category")


class KitchenPrinterSettings(Base):
    """Singleton print backend mode (file | escpos_network | windows_printer)."""

    __tablename__ = "kitchen_printer_settings"

    id = Column(Integer, primary_key=True, default=1)
    backend = Column(String(32), nullable=False, default="file")
    render_mode = Column(String(32), nullable=False, default="text")
    paper_width_px = Column(Integer, nullable=False, default=576)


class PrinterRouteEndpoint(Base):
    """Legacy LAN host/port by route_key (kept for DB compat; prefer `Printer`)."""

    __tablename__ = "printer_route_endpoints"

    route_key = Column(String(32), primary_key=True)
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=False, default=9100)


class Printer(Base):
    """Named printer with a role (cashier, kitchen, bar, other).

    LAN uses host/port. Windows cashier receipts use windows_printer_name
    when KitchenPrinterSettings.backend is windows_printer.
    """

    __tablename__ = "printers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=False, default=9100)
    windows_printer_name = Column(String(256), nullable=True)
    role = Column(String(32), nullable=False, default="kitchen", index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)


class MenuItem(Base):
    """A single menu item with price, category, optional description and image."""

    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    price = Column(Float, nullable=False)
    discount_price = Column(Float, nullable=True, default=None)
    discount_type = Column(String(32), nullable=False, default="none")
    discount_value = Column(Float, nullable=False, default=0.0)
    takeaway_price = Column(Float, nullable=True, default=None)
    tax_type = Column(String(32), nullable=False, default="none")
    tax_value = Column(Float, nullable=False, default=0.0)
    description = Column(String(1024), nullable=True)
    image_url = Column(String(512), nullable=True)  # e.g. /images/menu/xxx.png
    is_available = Column(Boolean, nullable=False, default=True, index=True)
    is_promoted = Column(Boolean, nullable=False, default=False, index=True)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    # Flexible modifier groups/options config for this menu item.
    modifiers_config = Column(JSON, nullable=False, default=list)
    category_id = Column(
        Integer, ForeignKey("categories.id"), nullable=False, index=True
    )

    category = relationship("Category", back_populates="menu_items")
    order_items = relationship("OrderItem", back_populates="menu_item")


class TableStatus(str, PyEnum):
    available = "available"
    occupied = "occupied"


class OrderItemStatus(str, PyEnum):
    pending = "pending"
    cooking = "cooking"
    served = "served"
    cancelled = "cancelled"


class Zone(Base):
    """Physical dining zone (e.g. Indoor, Outdoor)."""

    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)

    tables = relationship("Table", back_populates="zone", cascade="all, delete-orphan")


class Table(Base):
    """A physical table belonging to a zone."""

    __tablename__ = "tables"
    __table_args__ = (
        Index("ix_tables_zone_status", "zone_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    # New canonical attribute: "name" (DB column remains name_or_number for compatibility).
    name = Column("name_or_number", String(50), nullable=False, unique=True, index=True)
    # Backward-compatible alias used by older frontend/backends.
    name_or_number = synonym("name")
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False, index=True)
    status = Column(
        Enum(TableStatus, name="table_status"),
        nullable=False,
        default=TableStatus.available,
        index=True,
    )

    zone = relationship("Zone", back_populates="tables")
    orders = relationship("Order", back_populates="table")


class Order(Base):
    """An order for a table with status and total."""

    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_table_status", "table_id", "status"),
        Index("ix_orders_status_created_at", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    # New normalized relation: order belongs to a table record.
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True, index=True)
    # Legacy field kept only for backward compatibility with existing data/UI.
    table_number = Column(Integer, nullable=True, index=True)
    order_type = Column(String(32), nullable=False, default="dine_in")
    customer_name = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    total_amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # Payment information (filled at checkout)
    payment_method = Column(String(32), nullable=True)  # cash | mobile_money | split
    cash_amount = Column(Float, nullable=True)  # applied bill portion paid in cash
    mobile_money_amount = Column(Float, nullable=True)  # applied bill portion paid via mobile
    amount_tendered = Column(Float, nullable=True)
    change_amount = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True, default=0.0)
    discount_type = Column(String(32), nullable=True)  # 'percentage' or 'amount'
    discount_value = Column(Float, nullable=True, default=0.0)
    # Cashier who finalized payment (for per-cashier sales reporting).
    checked_out_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # Free-text cashier label for receipt / terminal (may differ from login username).
    cashier_name = Column(String(128), nullable=True)
    # Staff who opened / took the order (waiter or cashier at first submit).
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    table = relationship("Table", back_populates="orders")
    checked_out_by = relationship("User", foreign_keys=[checked_out_by_id], back_populates="checked_out_orders")
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_orders")
    order_items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base):
    """A line item in an order: menu item + quantity + subtotal."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint("subtotal >= 0", name="ck_order_items_subtotal_nonnegative"),
        CheckConstraint(
            "status IN ('pending','cooking','served','cancelled')",
            name="ck_order_items_status_valid",
        ),
        Index("ix_order_items_order_status", "order_id", "status"),
        Index("ix_order_items_order_batch", "order_id", "batch_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(
        Integer, ForeignKey("orders.id"), nullable=False, index=True
    )
    menu_item_id = Column(
        Integer, ForeignKey("menu_items.id"), nullable=False, index=True
    )
    quantity = Column(Integer, nullable=False)
    subtotal = Column(Float, nullable=False)
    # Batch of ordering within a dining session (1 = first round, 2 = add-on, etc.)
    batch_number = Column(Integer, nullable=False, default=1, index=True)
    # Legacy compatibility:
    # Some existing SQLite databases still contain this old NOT NULL column.
    # Keep writing a default value so inserts do not fail on those databases.
    batch_status = Column(String(32), nullable=False, default="pending")
    # New canonical attribute: item_status.
    # DB column is still "status" for backward compatibility in existing databases.
    item_status = Column(
        "status",
        String(32),
        nullable=False,
        default="pending",
        index=True,
    )
    # Backward-compatible alias for existing code.
    status = synonym("item_status")
    # Selected modifiers for this specific line item (JSON list).
    selected_modifiers = Column(JSON, nullable=False, default=list)
    # Preferred field for per-item note/special instruction.
    note = Column(String(1024), nullable=True)
    # Free-text instructions for kitchen (e.g. "No MSG").
    special_instructions = Column(String(1024), nullable=True)
    # Historical snapshots to preserve reporting even if related records change/delete.
    menu_item_name_at_sale = Column(String(255), nullable=True)
    unit_price_at_sale = Column(Float, nullable=True)
    unit_discount_at_sale = Column(Float, nullable=True)
    unit_tax_at_sale = Column(Float, nullable=True)
    category_name_at_sale = Column(String(255), nullable=True)
    is_takeaway = Column(Boolean, nullable=False, default=False, index=True)

    # Who created this specific batch (ticket) in the dining session.
    # We store it per OrderItem row so Kitchen can show waiter per batch.
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    order = relationship("Order", back_populates="order_items")
    menu_item = relationship("MenuItem", back_populates="order_items")
    created_by = relationship("User", back_populates="created_order_items")


class User(Base):
    """User account for authentication.
    Roles: root, admin (password login); cashier, waiter, account (PIN login).
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, index=True)
    pin_code = Column(String(4), unique=True, nullable=True, index=True)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    created_order_items = relationship("OrderItem", back_populates="created_by")
    created_orders = relationship(
        "Order",
        foreign_keys="Order.created_by_id",
        back_populates="created_by",
    )
    checked_out_orders = relationship(
        "Order",
        foreign_keys="Order.checked_out_by_id",
        back_populates="checked_out_by",
    )
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_active(self) -> bool:
        return not bool(self.is_deleted)


class UserSession(Base):
    """Active login session tied to JWT jti claim."""

    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_revoked", "user_id", "revoked_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    jti = Column(String(64), nullable=False, unique=True, index=True)
    device_id = Column(String(128), nullable=False, default="unknown")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")


class AdminAuditLog(Base):
    """Audit trail for admin staff-management actions (visible to root)."""

    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    detail_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    actor = relationship("User", foreign_keys=[actor_user_id])
    target = relationship("User", foreign_keys=[target_user_id])


class PredefinedInstruction(Base):
    """Store-wide quick tags for waiter special instructions."""

    __tablename__ = "predefined_instructions"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(255), nullable=False, unique=True, index=True)
