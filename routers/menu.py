"""Menu API: categories and menu items."""

from datetime import datetime
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user, require_roles
from database import get_db
from models import Category, MenuItem, Order, OrderItem, User
from rbac import ADMIN_PANEL_ROLES
from schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
)

router = APIRouter(prefix="/api")

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

FINALIZED_ORDER_STATUSES = ("paid", "cancelled")
MENU_ITEM_DELETE_ACTIVE_ORDER_MSG = (
    "Cannot delete menu item. It is currently part of an active order."
)


def _menu_item_in_active_order(db: Session, menu_item_id: int) -> bool:
    """True if item appears on a non-finalized order line (excluding cancelled lines)."""
    row = (
        db.query(OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(
            OrderItem.menu_item_id == menu_item_id,
            Order.status.notin_(FINALIZED_ORDER_STATUSES),
            OrderItem.item_status != "cancelled",
        )
        .first()
    )
    return row is not None


@router.post("/categories/", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Create a new category. Admin only."""
    db_category = Category(name=category.name, printer_route=category.printer_route)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    body: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Update category name and/or kitchen printer route. Admin only."""
    db_category = db.query(Category).filter(Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail=f"Category id {category_id} not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    if "name" in updates:
        name = (updates["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Category name must be non-empty")
        db_category.name = name

    if "printer_route" in updates:
        db_category.printer_route = updates["printer_route"]

    db.commit()
    db.refresh(db_category)
    return db_category


ARCHIVED_CATEGORY_NAME = "__system_archived__"
_CATEGORY_DELETE_BLOCKED_MSG = (
    "Cannot delete category. Please delete all menu items under this category first."
)


def _get_or_create_archived_category(db: Session) -> Category:
    """Hidden bucket for soft-deleted menu items that still have order history."""
    cat = db.query(Category).filter(Category.name == ARCHIVED_CATEGORY_NAME).first()
    if not cat:
        cat = Category(name=ARCHIVED_CATEGORY_NAME, printer_route="food")
        db.add(cat)
        db.flush()
    return cat


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Delete a category when it has no active menu items. Admin only."""
    db_category = db.query(Category).filter(Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail=f"Category id {category_id} not found")

    active_item_count = (
        db.query(MenuItem)
        .filter(MenuItem.category_id == category_id, MenuItem.is_deleted.is_(False))
        .count()
    )
    if active_item_count > 0:
        raise HTTPException(status_code=400, detail=_CATEGORY_DELETE_BLOCKED_MSG)

    archived_category = _get_or_create_archived_category(db)

    # Remove soft-deleted items with no order lines (safe to hard-delete).
    soft_deleted_ids = [
        row[0]
        for row in db.query(MenuItem.id)
        .filter(
            MenuItem.category_id == category_id,
            MenuItem.is_deleted.is_(True),
            ~exists().where(OrderItem.menu_item_id == MenuItem.id),
        )
        .all()
    ]
    if soft_deleted_ids:
        db.query(MenuItem).filter(MenuItem.id.in_(soft_deleted_ids)).delete(
            synchronize_session=False
        )

    # Keep soft-deleted items that have order history; move them off this category.
    db.query(MenuItem).filter(
        MenuItem.category_id == category_id,
        MenuItem.is_deleted.is_(True),
    ).update(
        {MenuItem.category_id: archived_category.id},
        synchronize_session=False,
    )

    try:
        db.delete(db_category)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=_CATEGORY_DELETE_BLOCKED_MSG) from None

    return {"deleted": True, "category_id": category_id}


@router.get("/categories/", response_model=list[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all categories. Requires authentication."""
    return (
        db.query(Category)
        .filter(Category.name != ARCHIVED_CATEGORY_NAME)
        .all()
    )


@router.post("/menu-items/", response_model=MenuItemResponse)
async def create_menu_item(
    request: Request,
    item: MenuItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Create a new menu item (JSON). Admin only. Broadcasts menu_item_added via WebSocket."""
    db_item = MenuItem(
        name=item.name,
        price=item.price,
        discount_price=item.discount_price,
        category_id=item.category_id,
        description=item.description,
        image_url=item.image_url,
        is_available=item.is_available,
        is_promoted=item.is_promoted,
        modifiers_config=[m.model_dump(mode="json") for m in item.modifiers_config],
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    item_response = MenuItemResponse.model_validate(db_item)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast("menu_item_added", item_response.model_dump(mode="json"))
    return item_response


@router.post("/menu-items/upload", response_model=MenuItemResponse)
async def create_menu_item_upload(
    request: Request,
    name: str = Form(...),
    price: float = Form(...),
    category_id: int = Form(...),
    description: str | None = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """
    Create a menu item from form data (name, price, description, category_id, image file).
    Saves image to static/images/menu/ and stores relative URL in DB. Broadcasts menu_item_added via WebSocket.
    """
    image_url: str | None = None
    if image and image.filename:
        suffix = Path(image.filename).suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Image must be jpg, jpeg, png, gif, or webp",
            )
        menu_images_dir = Path(__file__).resolve().parent.parent / "static" / "images" / "menu"
        menu_images_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{uuid.uuid4().hex}{suffix}"
        path = menu_images_dir / fname
        content = await image.read()
        path.write_bytes(content)
        image_url = f"/images/menu/{fname}"

    db_item = MenuItem(
        name=name.strip(),
        price=price,
        category_id=category_id,
        description=description.strip() if description else None,
        image_url=image_url,
        is_available=True,
        modifiers_config=[],
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    item_response = MenuItemResponse.model_validate(db_item)

    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast("menu_item_added", item_response.model_dump(mode="json"))

    return item_response


@router.get("/menu-items/", response_model=list[MenuItemResponse])
def list_menu_items(
    category_id: int | None = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all menu items, optionally filtered by category_id. Requires authentication."""
    q = db.query(MenuItem)
    q = q.filter(MenuItem.is_deleted.is_(False))
    if category_id is not None:
        q = q.filter(MenuItem.category_id == category_id)
    return q.all()


@router.put("/menu-items/{item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    request: Request,
    item_id: int,
    item_update: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """
    Update an existing menu item. Admin only.
    Supports partial updates for name, price, description, category_id, image_url,
    is_available, and modifiers_config.
    """
    db_item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.is_deleted.is_(False))
        .first()
    )
    if not db_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    update_data = item_update.model_dump(exclude_unset=True)
    if "modifiers_config" in update_data and update_data["modifiers_config"] is not None:
        update_data["modifiers_config"] = [
            m.model_dump(mode="json") if hasattr(m, "model_dump") else m
            for m in update_data["modifiers_config"]
        ]

    for field, value in update_data.items():
        setattr(db_item, field, value)

    db.commit()
    db.refresh(db_item)
    item_response = MenuItemResponse.model_validate(db_item)

    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast("menu_item_updated", item_response.model_dump(mode="json"))
    return item_response


@router.put("/menu-items/{item_id}/toggle-promoted", response_model=MenuItemResponse)
async def toggle_menu_item_promoted(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Toggle a menu item's promoted flag. Admin panel only."""
    db_item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.is_deleted.is_(False))
        .first()
    )
    if not db_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    db_item.is_promoted = not bool(getattr(db_item, "is_promoted", False))
    db.commit()
    db.refresh(db_item)

    item_response = MenuItemResponse.model_validate(db_item)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "menu_item_updated",
            item_response.model_dump(mode="json"),
        )
    return item_response


@router.put("/menu-items/{item_id}/toggle-availability", response_model=MenuItemResponse)
async def toggle_menu_item_availability(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Toggle a menu item's availability. Admin only."""
    db_item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.is_deleted.is_(False))
        .first()
    )
    if not db_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    db_item.is_available = not bool(getattr(db_item, "is_available", True))
    db.commit()
    db.refresh(db_item)

    item_response = MenuItemResponse.model_validate(db_item)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "menu_item_availability_toggled",
            item_response.model_dump(mode="json"),
        )
    return item_response


@router.delete("/menu-items/{item_id}")
async def delete_menu_item(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Soft-delete a menu item. Historical order rows remain intact."""
    db_item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.is_deleted.is_(False))
        .first()
    )
    if not db_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    if _menu_item_in_active_order(db, item_id):
        raise HTTPException(status_code=400, detail=MENU_ITEM_DELETE_ACTIVE_ORDER_MSG)

    db_item.is_deleted = True
    db_item.deleted_at = datetime.utcnow()
    db_item.is_available = False
    db.commit()

    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "menu_item_deleted",
            {"id": item_id},
        )
    return {"deleted": True, "item_id": item_id}
