"""FastAPI application for the Restaurant POS system."""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile, WebSocket
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from database import engine
from models import Base
from routers import menu, orders
from websocket_manager import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    app.state.ws_manager = ConnectionManager()
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE menu_items ADD COLUMN image_url VARCHAR(512)"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE menu_items ADD COLUMN description VARCHAR(1024)"))
    except Exception:
        pass
    # Add batch_number to existing order_items if missing (SQLite dev migration).
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE order_items "
                    "ADD COLUMN batch_number INTEGER NOT NULL DEFAULT 1"
                )
            )
    except Exception:
        # Column may already exist; ignore migration errors.
        pass
    # Add batch_status to order_items for per-batch completion tracking.
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE order_items "
                    "ADD COLUMN batch_status VARCHAR(32) NOT NULL DEFAULT 'pending'"
                )
            )
    except Exception:
        # Column may already exist; ignore migration errors.
        pass
    # Add payment fields to orders for cashier checkout.
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(32)"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN amount_tendered FLOAT"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN change_amount FLOAT"))
    except Exception:
        pass
    # One active order per table: at most one row per table_number with status open/dining
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE UNIQUE INDEX idx_one_active_order_per_table ON orders(table_number) "
                "WHERE status IN ('open','dining')"
            ))
    except Exception:
        pass
    yield
    engine.dispose()


app = FastAPI(title="Restaurant POS API", lifespan=lifespan)
app.include_router(menu.router)
app.include_router(orders.router)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"message": "POS Server is running"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Avoid 404 when browsers request favicon.ico."""
    return Response(status_code=204)


static_dir = Path(__file__).parent / "static"
images_dir = static_dir / "images"
images_dir.mkdir(exist_ok=True)
menu_images_dir = images_dir / "menu"
menu_images_dir.mkdir(exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates (e.g. menu_item_added)."""
    manager: ConnectionManager = websocket.app.state.ws_manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep connection alive; ignore client messages
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket)


@app.post("/api/upload")
async def upload_image(file: UploadFile):
    """Upload an image for menu items. Saves to static/images/ and returns the URL path."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={"detail": "Allowed types: jpg, jpeg, png, gif, webp"},
        )
    name = f"{uuid.uuid4().hex}{suffix}"
    path = images_dir / name
    content = await file.read()
    path.write_bytes(content)
    return {"url": f"/images/{name}"}


@app.get("/waiter")
def waiter_page():
    """Serve the Waiter POS UI."""
    return FileResponse(static_dir / "waiter.html")


@app.get("/kitchen")
def kitchen_page():
    """Serve the Kitchen Display System UI."""
    return FileResponse(static_dir / "kitchen.html")


@app.get("/counter")
def counter_page():
    """Serve the Counter / Admin UI."""
    return FileResponse(static_dir / "counter.html")


app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
