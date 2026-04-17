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

    menu_items = relationship("MenuItem", back_populates="category")


class MenuItem(Base):
    """A single menu item with price, category, optional description and image."""

    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    price = Column(Float, nullable=False)
    discount_price = Column(Float, nullable=True, default=None)
    description = Column(String(1024), nullable=True)
    image_url = Column(String(512), nullable=True)  # e.g. /images/menu/xxx.png
    is_available = Column(Boolean, nullable=False, default=True, index=True)
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
    payment_method = Column(String(32), nullable=True)  # 'cash', 'mobile_money', etc.
    amount_tendered = Column(Float, nullable=True)
    change_amount = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True, default=0.0)
    discount_type = Column(String(32), nullable=True)  # 'percentage' or 'amount'
    discount_value = Column(Float, nullable=True, default=0.0)

    table = relationship("Table", back_populates="orders")
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

    # Who created this specific batch (ticket) in the dining session.
    # We store it per OrderItem row so Kitchen can show waiter per batch.
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    order = relationship("Order", back_populates="order_items")
    menu_item = relationship("MenuItem", back_populates="order_items")
    created_by = relationship("User", back_populates="created_order_items")


class User(Base):
    """User account for authentication. role: admin, waiter, kitchen, cashier.
    Staff use pin_code (4 digits); admins can use username/password.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, index=True)  # admin, waiter, kitchen, cashier
    pin_code = Column(String(4), unique=True, nullable=True, index=True)  # exactly 4 chars, for staff
    created_order_items = relationship("OrderItem", back_populates="created_by")
