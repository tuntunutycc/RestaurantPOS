"""FastAPI application for the Restaurant POS system."""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, UploadFile, WebSocket
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from auth import hash_password, require_roles
from database import SessionLocal, engine
from models import Base, Order, Table, User, Zone
from routers import auth, menu, orders, reports, tables, users
from websocket_manager import ConnectionManager


def _ensure_order_items_cancelled_status_constraint():
    """SQLite safety migration for legacy DBs missing cancelled status in check constraint."""
    try:
        from sqlalchemy import text

        with engine.begin() as conn:
            create_sql = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='order_items'")
            ).scalar()
            if not create_sql:
                return

            normalized_sql = str(create_sql).lower()
            if (
                "ck_order_items_status_valid" in normalized_sql
                and "'cancelled'" in normalized_sql
            ):
                return

            cols = {
                row["name"]
                for row in conn.execute(text("PRAGMA table_info(order_items)")).mappings()
            }

            def src(column: str, fallback_sql: str) -> str:
                return column if column in cols else fallback_sql

            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(
                text(
                    """
                    CREATE TABLE order_items_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        order_id INTEGER NOT NULL,
                        menu_item_id INTEGER NOT NULL,
                        quantity INTEGER NOT NULL,
                        subtotal FLOAT NOT NULL,
                        batch_number INTEGER NOT NULL DEFAULT 1,
                        batch_status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        selected_modifiers JSON NOT NULL DEFAULT '[]',
                        note VARCHAR(1024),
                        special_instructions VARCHAR(1024),
                        created_by_id INTEGER,
                        CONSTRAINT ck_order_items_quantity_positive CHECK (quantity > 0),
                        CONSTRAINT ck_order_items_subtotal_nonnegative CHECK (subtotal >= 0),
                        CONSTRAINT ck_order_items_status_valid CHECK (
                            status IN ('pending','cooking','served','cancelled')
                        ),
                        FOREIGN KEY(order_id) REFERENCES orders (id),
                        FOREIGN KEY(menu_item_id) REFERENCES menu_items (id),
                        FOREIGN KEY(created_by_id) REFERENCES users (id)
                    )
                    """
                )
            )

            conn.execute(
                text(
                    f"""
                    INSERT INTO order_items_new (
                        id, order_id, menu_item_id, quantity, subtotal,
                        batch_number, batch_status, status, selected_modifiers,
                        note, special_instructions, created_by_id
                    )
                    SELECT
                        id,
                        order_id,
                        menu_item_id,
                        quantity,
                        subtotal,
                        {src("batch_number", "1")},
                        {src("batch_status", "'pending'")},
                        LOWER(TRIM({src("status", "'pending'")})),
                        {src("selected_modifiers", "'[]'")},
                        {src("note", "NULL")},
                        {src("special_instructions", "NULL")},
                        {src("created_by_id", "NULL")}
                    FROM order_items
                    """
                )
            )

            conn.execute(text("DROP TABLE order_items"))
            conn.execute(text("ALTER TABLE order_items_new RENAME TO order_items"))
            conn.execute(text("CREATE INDEX ix_order_items_id ON order_items (id)"))
            conn.execute(
                text("CREATE INDEX ix_order_items_order_status ON order_items (order_id, status)")
            )
            conn.execute(text("CREATE INDEX ix_order_items_batch_number ON order_items (batch_number)"))
            conn.execute(
                text("CREATE INDEX ix_order_items_order_batch ON order_items (order_id, batch_number)")
            )
            conn.execute(text("CREATE INDEX ix_order_items_menu_item_id ON order_items (menu_item_id)"))
            conn.execute(text("CREATE INDEX ix_order_items_created_by_id ON order_items (created_by_id)"))
            conn.execute(text("CREATE INDEX ix_order_items_order_id ON order_items (order_id)"))
            conn.execute(text("CREATE INDEX ix_order_items_status ON order_items (status)"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
    except Exception:
        # Keep startup resilient in local/dev mode.
        pass


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
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE menu_items "
                    "ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE menu_items "
                    "ADD COLUMN modifiers_config JSON NOT NULL DEFAULT '[]'"
                )
            )
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE menu_items ADD COLUMN discount_price FLOAT"))
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
    # Legacy compatibility: some databases still require batch_status on insert.
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
        pass
    # Add created_by_id to order_items (who created this batch/ticket)
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE order_items "
                    "ADD COLUMN created_by_id INTEGER"
                )
            )
    except Exception:
        # Column may already exist; ignore migration errors.
        pass
    # Add item-level status to order_items.
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE order_items "
                    "ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'pending'"
                )
            )
    except Exception:
        pass
    # Add selected modifiers (JSON) and special instructions to order_items.
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE order_items "
                    "ADD COLUMN selected_modifiers JSON NOT NULL DEFAULT '[]'"
                )
            )
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE order_items "
                    "ADD COLUMN special_instructions VARCHAR(1024)"
                )
            )
    except Exception:
        pass
    # Add note column for per-item special instructions.
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE order_items "
                    "ADD COLUMN note VARCHAR(1024)"
                )
            )
    except Exception:
        pass
    # Backfill note from legacy special_instructions when available.
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE order_items "
                    "SET note = special_instructions "
                    "WHERE note IS NULL AND special_instructions IS NOT NULL"
                )
            )
    except Exception:
        pass
    _ensure_order_items_cancelled_status_constraint()
    # Add payment fields to orders for cashier checkout.
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(32)"))
    except Exception:
        pass
    # Add normalized table relation to orders.
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN table_id INTEGER"))
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
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN tax_amount FLOAT"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN discount_type VARCHAR(32)"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN discount_value FLOAT"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE orders "
                    "ADD COLUMN order_type VARCHAR(32) NOT NULL DEFAULT 'dine_in'"
                )
            )
    except Exception:
        pass
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN customer_name VARCHAR(255)"))
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
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE UNIQUE INDEX idx_one_active_order_per_table_id ON orders(table_id) "
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
    # Ensure default zone exists for table management.
    db = SessionLocal()
    try:
        default_zone = db.query(Zone).filter(Zone.name == "Main").first()
        if not default_zone:
            default_zone = Zone(name="Main")
            db.add(default_zone)
            db.commit()
            db.refresh(default_zone)

        # Backfill tables from legacy orders.table_number where table_id is null.
        legacy_orders = db.query(Order).filter(Order.table_id.is_(None)).all()
        for legacy_order in legacy_orders:
            name_or_number = str(getattr(legacy_order, "table_number", legacy_order.id))
            table = db.query(Table).filter(Table.name_or_number == name_or_number).first()
            if not table:
                table = Table(
                    name_or_number=name_or_number,
                    zone_id=default_zone.id,
                    status=(
                        "occupied"
                        if legacy_order.status in ("open", "dining", "pending", "completed")
                        else "available"
                    ),
                )
                db.add(table)
                db.flush()
            legacy_order.table_id = table.id
        db.commit()
    except Exception:
        db.rollback()
        pass
    finally:
        db.close()

    # Ensure default admin exists (even if staff were added first via scripts)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
                pin_code="1234",
            )
            db.add(admin)
            db.commit()
        else:
            # Backfill: PIN if missing (do not reset password on every boot)
            if getattr(admin, "pin_code", None) is None:
                admin.pin_code = "1234"
                db.commit()
    finally:
        db.close()
    yield
    engine.dispose()


app = FastAPI(title="Restaurant POS API", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(reports.router)
app.include_router(users.router)
app.include_router(tables.router)


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


@app.get("/images/{filename}")
def get_legacy_image(filename: str):
    """Backward-compatible image route for old rows storing /images/<file>."""
    safe_name = Path(filename).name
    candidates = [
        images_dir / safe_name,
        menu_images_dir / safe_name,
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return FileResponse(path)
    return JSONResponse(status_code=404, content={"detail": "Image not found"})


@app.get("/waiter")
def waiter_page():
    """Serve the Waiter POS UI."""
    return FileResponse(static_dir / "waiter.html")


@app.get("/")
def root_page():
    """Start app at the login page."""
    return RedirectResponse(url="/login", status_code=302)


@app.get("/counter")
def counter_page():
    """Serve the Counter / Admin UI."""
    return FileResponse(static_dir / "counter.html")


@app.get("/table-dashboard")
def table_dashboard_page():
    """Serve the shared Table Dashboard (Admin + Waiter)."""
    return FileResponse(static_dir / "table-dashboard.html")


@app.get("/login")
def login_page():
    """Serve the Login page (username/password for admins)."""
    return FileResponse(static_dir / "login.html")


@app.get("/pin-login")
def pin_login_page():
    """Serve the Staff PIN login page (4-digit numpad)."""
    return FileResponse(static_dir / "pin-login.html")


app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
