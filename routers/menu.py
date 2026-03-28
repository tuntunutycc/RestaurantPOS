"""Menu API: categories and menu items."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from auth import get_current_user, require_roles
from database import get_db
from models import Category, MenuItem, OrderItem, User
from schemas import CategoryCreate, CategoryResponse, MenuItemCreate, MenuItemResponse

router = APIRouter(prefix="/api")

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


@router.post("/categories/", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    """Create a new category. Admin only."""
    db_category = Category(name=category.name)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@router.get("/categories/", response_model=list[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all categories. Requires authentication."""
    return db.query(Category).all()


@router.post("/menu-items/", response_model=MenuItemResponse)
async def create_menu_item(
    request: Request,
    item: MenuItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    """Create a new menu item (JSON). Admin only. Broadcasts menu_item_added via WebSocket."""
    db_item = MenuItem(
        name=item.name,
        price=item.price,
        category_id=item.category_id,
        description=item.description,
        image_url=item.image_url,
        is_available=item.is_available,
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
    current_user: User = Depends(require_roles(["admin"])),
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
    if category_id is not None:
        q = q.filter(MenuItem.category_id == category_id)
    return q.all()


@router.put("/menu-items/{item_id}/toggle-availability", response_model=MenuItemResponse)
async def toggle_menu_item_availability(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    """Toggle a menu item's availability. Admin only."""
    db_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
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
    current_user: User = Depends(require_roles(["admin"])),
):
    """Delete a menu item only if it has no order history. Admin only."""
    db_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    used_in_orders = (
        db.query(OrderItem.id)
        .filter(OrderItem.menu_item_id == item_id)
        .first()
        is not None
    )
    if used_in_orders:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete item with order history. Disable it instead.",
        )

    db.delete(db_item)
    db.commit()

    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "menu_item_deleted",
            {"id": item_id},
        )
    return {"deleted": True, "item_id": item_id}
