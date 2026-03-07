"""Menu API: categories and menu items."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Category, MenuItem
from schemas import CategoryCreate, CategoryResponse, MenuItemCreate, MenuItemResponse

router = APIRouter(prefix="/api")


@router.post("/categories/", response_model=CategoryResponse)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    """Create a new category."""
    db_category = Category(name=category.name)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@router.get("/categories/", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    """Retrieve all categories."""
    return db.query(Category).all()


@router.post("/menu-items/", response_model=MenuItemResponse)
def create_menu_item(item: MenuItemCreate, db: Session = Depends(get_db)):
    """Create a new menu item."""
    db_item = MenuItem(
        name=item.name,
        price=item.price,
        category_id=item.category_id,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/menu-items/", response_model=list[MenuItemResponse])
def list_menu_items(
    category_id: int | None = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db),
):
    """Retrieve all menu items, optionally filtered by category_id."""
    q = db.query(MenuItem)
    if category_id is not None:
        q = q.filter(MenuItem.category_id == category_id)
    return q.all()
