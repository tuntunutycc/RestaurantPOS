"""FastAPI application for the Restaurant POS system."""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, UploadFile, WebSocket
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from auth import hash_password, require_roles
from database import SessionLocal, engine
from models import Base, User
from routers import auth, menu, orders
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
    # Add pin_code to users table (4-char, unique, nullable)
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN pin_code VARCHAR(4)"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX ix_users_pin_code ON users(pin_code)"))
    except Exception:
        pass
    # Seed default admin user if no users exist; set PIN for admin (and backfill if column new)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
                pin_code="1234",
            )
            db.add(admin)
            db.commit()
        else:
            # Backfill: ensure existing admin has a PIN and a fresh password hash
            admin = db.query(User).filter(User.username == "admin").first()
            if admin:
                if getattr(admin, "pin_code", None) is None:
                    admin.pin_code = "1234"
                # Reset password hash to ensure it uses the current hashing scheme
                admin.password_hash = hash_password("admin123")
                db.commit()
    finally:
        db.close()
    yield
    engine.dispose()


app = FastAPI(title="Restaurant POS API", lifespan=lifespan)
app.include_router(auth.router)
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
async def upload_image(
    file: UploadFile,
    current_user: User = Depends(require_roles(["admin"])),
):
    """Upload an image for menu items. Admin only. Saves to static/images/ and returns the URL path."""
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


@app.get("/login")
def login_page():
    """Serve the Login page (username/password for admins)."""
    return FileResponse(static_dir / "login.html")


@app.get("/pin-login")
def pin_login_page():
    """Serve the Staff PIN login page (4-digit numpad)."""
    return FileResponse(static_dir / "pin-login.html")


app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
