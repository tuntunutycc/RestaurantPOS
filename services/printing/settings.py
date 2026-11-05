"""Seed and load printer settings from database with env fallback."""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import KitchenPrinterSettings, Printer, PrinterRouteEndpoint
from services.printing.config import (
    BAR_PRINTER_ROLE,
    CASHIER_PRINTER_ROLE,
    CASHIER_PRINTER_ROUTE,
    KITCHEN_PRINTER_ROLE,
    KNOWN_ENDPOINT_ROUTES,
    ROLE_TO_LEGACY_ROUTE,
    PrinterBackendName,
    PrinterConfig,
    PrinterEndpoint,
    PrinterRenderModeName,
)
from services.printing.routes import role_fallback_chain


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _paper_width_from_env() -> int:
    paper_width_px = _env_int("PRINTER_PAPER_WIDTH_PX", 576)
    return paper_width_px if paper_width_px in (384, 576) else 576


def _normalize_backend(backend_raw: str | None) -> PrinterBackendName:
    raw = (backend_raw or "").strip().lower()
    if raw == "escpos_network":
        return "escpos_network"
    if raw == "windows_printer":
        return "windows_printer"
    return "file"


def _backend_from_env() -> PrinterBackendName:
    return _normalize_backend(os.getenv("PRINTER_BACKEND", "file"))


def _render_mode_from_env() -> PrinterRenderModeName:
    render_mode_raw = os.getenv("PRINTER_RENDER_MODE", "text").strip().lower()
    return "image" if render_mode_raw == "image" else "text"


def _route_endpoint_from_env(route: str) -> PrinterEndpoint | None:
    host = os.getenv(f"PRINTER_{route.upper()}_HOST", "").strip()
    if not host:
        return None
    return PrinterEndpoint(host=host, port=_env_int(f"PRINTER_{route.upper()}_PORT", 9100))


def migrate_legacy_cashier_printers(db: Session) -> None:
    """Copy legacy cashier_printers rows into printers (role=cashier) when needed."""
    try:
        has_legacy = db.execute(
            text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cashier_printers'"
            )
        ).scalar()
    except Exception:
        return
    if not has_legacy:
        return
    if db.query(Printer).filter(Printer.role == CASHIER_PRINTER_ROLE).count() > 0:
        return
    try:
        rows = db.execute(
            text(
                "SELECT name, host, port, is_active FROM cashier_printers ORDER BY id ASC"
            )
        ).mappings().all()
    except Exception:
        return
    for row in rows:
        db.add(
            Printer(
                name=str(row["name"] or "Cashier"),
                host=(str(row["host"]).strip() if row["host"] else None) or None,
                port=int(row["port"] or 9100),
                role=CASHIER_PRINTER_ROLE,
                is_active=bool(row["is_active"]) if row["is_active"] is not None else True,
            )
        )
    if rows:
        db.commit()


def seed_kitchen_printer_settings(db: Session) -> None:
    """Ensure singleton settings row exists (hosts live on Printer table)."""
    settings = db.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    if not settings:
        db.add(
            KitchenPrinterSettings(
                id=1,
                backend=_backend_from_env(),
                render_mode=_render_mode_from_env(),
                paper_width_px=_paper_width_from_env(),
            )
        )
        db.commit()
    seed_default_printers(db)


def seed_default_printers(db: Session) -> None:
    """
    Ensure minimal printers exist: 1 cashier + 1 kitchen.
    Idempotent when any printer rows already exist (after migration).
    """
    migrate_legacy_cashier_printers(db)
    if db.query(Printer).count() > 0:
        return

    cashier_host = None
    cashier_port = 9100
    kitchen_host = None
    kitchen_port = 9100
    bar_host = None
    bar_port = 9100

    legacy_rows = {
        row.route_key: row
        for row in db.query(PrinterRouteEndpoint)
        .filter(PrinterRouteEndpoint.route_key.in_(sorted(KNOWN_ENDPOINT_ROUTES)))
        .all()
    }
    if "cashier" in legacy_rows:
        cashier_host = (legacy_rows["cashier"].host or "").strip() or None
        cashier_port = int(legacy_rows["cashier"].port or 9100)
    if "food" in legacy_rows:
        kitchen_host = (legacy_rows["food"].host or "").strip() or None
        kitchen_port = int(legacy_rows["food"].port or 9100)
    if "drinks" in legacy_rows:
        bar_host = (legacy_rows["drinks"].host or "").strip() or None
        bar_port = int(legacy_rows["drinks"].port or 9100)

    if not cashier_host:
        env_c = _route_endpoint_from_env(CASHIER_PRINTER_ROUTE)
        if env_c:
            cashier_host, cashier_port = env_c.host, env_c.port
    if not kitchen_host:
        env_f = _route_endpoint_from_env("food")
        if env_f:
            kitchen_host, kitchen_port = env_f.host, env_f.port
    if not bar_host:
        env_d = _route_endpoint_from_env("drinks")
        if env_d:
            bar_host, bar_port = env_d.host, env_d.port

    db.add(
        Printer(
            name="Default Cashier Printer",
            host=cashier_host,
            port=cashier_port,
            role=CASHIER_PRINTER_ROLE,
            is_active=True,
        )
    )
    db.add(
        Printer(
            name="Default Kitchen Printer",
            host=kitchen_host,
            port=kitchen_port,
            role=KITCHEN_PRINTER_ROLE,
            is_active=True,
        )
    )
    # If a drinks host was configured historically, seed an optional bar printer too
    # only when env/legacy has a host — still "minimal" when fresh install (no host).
    if bar_host:
        db.add(
            Printer(
                name="Default Bar Printer",
                host=bar_host,
                port=bar_port,
                role=BAR_PRINTER_ROLE,
                is_active=True,
            )
        )
    db.commit()


def resolve_printer_endpoint_for_role(
    db: Session,
    role: str,
    *,
    printer_id: int | None = None,
) -> PrinterEndpoint | None:
    """Resolve LAN endpoint for a printer role (with bar→kitchen fallback)."""
    seed_default_printers(db)
    if printer_id is not None:
        row = (
            db.query(Printer)
            .filter(Printer.id == printer_id, Printer.is_active.is_(True))
            .first()
        )
        if row is None:
            return None
        host = (row.host or "").strip()
        if host:
            return PrinterEndpoint(host=host, port=int(row.port or 9100))
        return None

    for candidate in role_fallback_chain(role):
        row = (
            db.query(Printer)
            .filter(Printer.role == candidate, Printer.is_active.is_(True))
            .order_by(Printer.id.asc())
            .first()
        )
        if row is None:
            continue
        host = (row.host or "").strip()
        if host:
            return PrinterEndpoint(host=host, port=int(row.port or 9100))

    # Legacy env / route table fallback by mapped route key
    legacy_route = ROLE_TO_LEGACY_ROUTE.get((role or "").strip().lower())
    if legacy_route:
        config = _load_printer_config_from_db(db, seed_printers=False)
        return config.routes.get(legacy_route)
    return None


def resolve_cashier_printer_endpoint(
    db: Session,
    printer_id: int | None = None,
) -> PrinterEndpoint | None:
    """Resolve cashier receipt printer endpoint."""
    return resolve_printer_endpoint_for_role(
        db, CASHIER_PRINTER_ROLE, printer_id=printer_id
    )


def resolve_cashier_windows_printer_name(
    db: Session,
    printer_id: int | None = None,
) -> str | None:
    """Resolve Windows queue name for cashier receipts."""
    seed_default_printers(db)
    if printer_id is not None:
        row = (
            db.query(Printer)
            .filter(
                Printer.id == printer_id,
                Printer.role == CASHIER_PRINTER_ROLE,
                Printer.is_active.is_(True),
            )
            .first()
        )
        if row is None:
            return None
        name = (getattr(row, "windows_printer_name", None) or "").strip()
        return name or None

    # Prefer an active cashier row that already has a Windows queue configured.
    named = (
        db.query(Printer)
        .filter(
            Printer.role == CASHIER_PRINTER_ROLE,
            Printer.is_active.is_(True),
            Printer.windows_printer_name.isnot(None),
        )
        .order_by(Printer.id.asc())
        .all()
    )
    for row in named:
        name = (row.windows_printer_name or "").strip()
        if name:
            return name

    row = (
        db.query(Printer)
        .filter(Printer.role == CASHIER_PRINTER_ROLE, Printer.is_active.is_(True))
        .order_by(Printer.id.asc())
        .first()
    )
    if row is None:
        return None
    name = (getattr(row, "windows_printer_name", None) or "").strip()
    return name or None


def _load_printer_config_from_db(db: Session, *, seed_printers: bool = True) -> PrinterConfig:
    settings = db.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    if not settings:
        db.add(
            KitchenPrinterSettings(
                id=1,
                backend=_backend_from_env(),
                render_mode=_render_mode_from_env(),
                paper_width_px=_paper_width_from_env(),
            )
        )
        db.commit()
        settings = db.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    if seed_printers:
        seed_default_printers(db)

    output_dir = os.getenv("KITCHEN_PRINT_OUTPUT_DIR", ".").strip() or "."
    backend_raw = (getattr(settings, "backend", None) or "").strip().lower()
    backend: PrinterBackendName = _normalize_backend(backend_raw)
    render_mode_raw = (getattr(settings, "render_mode", None) or "").strip().lower()
    render_mode: PrinterRenderModeName = (
        "image" if render_mode_raw == "image" else "text"
    )
    paper_width_px = int(getattr(settings, "paper_width_px", None) or 576)
    if paper_width_px not in (384, 576):
        paper_width_px = 576

    routes: dict[str, PrinterEndpoint] = {}
    # Prefer unified Printer table
    for row in (
        db.query(Printer)
        .filter(Printer.is_active.is_(True))
        .order_by(Printer.id.asc())
        .all()
    ):
        legacy = ROLE_TO_LEGACY_ROUTE.get((row.role or "").strip().lower())
        if not legacy or legacy in routes:
            continue
        host = (row.host or "").strip()
        if host:
            routes[legacy] = PrinterEndpoint(host=host, port=int(row.port or 9100))

    # Fill gaps from legacy route table / env
    endpoint_rows = {
        row.route_key: row
        for row in db.query(PrinterRouteEndpoint)
        .filter(PrinterRouteEndpoint.route_key.in_(sorted(KNOWN_ENDPOINT_ROUTES)))
        .all()
    }
    for route in sorted(KNOWN_ENDPOINT_ROUTES):
        if route in routes:
            continue
        row = endpoint_rows.get(route)
        host = (getattr(row, "host", None) or "").strip() if row else ""
        if host:
            routes[route] = PrinterEndpoint(host=host, port=int(getattr(row, "port", None) or 9100))
            continue
        env_endpoint = _route_endpoint_from_env(route)
        if env_endpoint:
            routes[route] = env_endpoint

    if backend_raw == "":
        backend = _backend_from_env()
    if render_mode_raw == "":
        render_mode = _render_mode_from_env()

    return PrinterConfig(
        backend=backend,
        render_mode=render_mode,
        paper_width_px=paper_width_px,
        output_dir=output_dir,
        routes=routes,
        font_path=(os.getenv("KITCHEN_PRINT_FONT_PATH", "").strip() or None),
    )


def load_printer_config(db: Session | None = None) -> PrinterConfig:
    """Load printer config from DB (UI settings), with env fallback for missing hosts."""
    if db is not None:
        return _load_printer_config_from_db(db)

    from database import SessionLocal

    session = SessionLocal()
    try:
        return _load_printer_config_from_db(session)
    finally:
        session.close()


# Backward-compatible aliases
seed_cashier_printers = seed_default_printers
