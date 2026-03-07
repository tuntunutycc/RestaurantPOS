"""SQLAlchemy models for the Restaurant POS system."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Category(Base):
    """Menu category (e.g. Appetizers, Mains, Drinks)."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)

    menu_items = relationship("MenuItem", back_populates="category")


class MenuItem(Base):
    """A single menu item with price and category."""

    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    price = Column(Float, nullable=False)
    category_id = Column(
        Integer, ForeignKey("categories.id"), nullable=False, index=True
    )

    category = relationship("Category", back_populates="menu_items")
    order_items = relationship("OrderItem", back_populates="menu_item")


class Order(Base):
    """An order for a table with status and total."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    table_number = Column(Integer, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    total_amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    order_items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    """A line item in an order: menu item + quantity + subtotal."""

    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(
        Integer, ForeignKey("orders.id"), nullable=False, index=True
    )
    menu_item_id = Column(
        Integer, ForeignKey("menu_items.id"), nullable=False, index=True
    )
    quantity = Column(Integer, nullable=False)
    subtotal = Column(Float, nullable=False)

    order = relationship("Order", back_populates="order_items")
    menu_item = relationship("MenuItem", back_populates="order_items")
