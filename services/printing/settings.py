"""Seed and load printer settings from database with env fallback."""

from __future__ import annotations

import os

from sqlalchemy.orm import Session

from models import KitchenPrinterSettings, PrinterRouteEndpoint
from services.printing.config import (
    KNOWN_ENDPOINT_ROUTES,
    PrinterBackendName,
    PrinterConfig,
    PrinterEndpoint,
    PrinterRenderModeName,
)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _paper_width_from_env() -> int:
    paper_width_px = _env_int("PRINTER_PAPER_WIDTH_PX", 576)
    return paper_width_px if paper_width_px in (384, 576) else 576


def seed_kitchen_printer_settings(db: Session) -> None:
    """Ensure singleton settings row and default route endpoint rows exist."""
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

    existing_keys = {
        row.route_key
        for row in db.query(PrinterRouteEndpoint)
        .filter(PrinterRouteEndpoint.route_key.in_(sorted(KNOWN_ENDPOINT_ROUTES)))
        .all()
    }
    for route_key in sorted(KNOWN_ENDPOINT_ROUTES):
        if route_key not in existing_keys:
            db.add(PrinterRouteEndpoint(route_key=route_key, host=None, port=9100))
    db.commit()


def _backend_from_env() -> PrinterBackendName:
    backend_raw = os.getenv("PRINTER_BACKEND", "file").strip().lower()
    return "escpos_network" if backend_raw == "escpos_network" else "file"


def _render_mode_from_env() -> PrinterRenderModeName:
    render_mode_raw = os.getenv("PRINTER_RENDER_MODE", "text").strip().lower()
    return "image" if render_mode_raw == "image" else "text"


def _route_endpoint_from_env(route: str) -> PrinterEndpoint | None:
    host = os.getenv(f"PRINTER_{route.upper()}_HOST", "").strip()
    if not host:
        return None
    return PrinterEndpoint(host=host, port=_env_int(f"PRINTER_{route.upper()}_PORT", 9100))


def _load_printer_config_from_db(db: Session) -> PrinterConfig:
    seed_kitchen_printer_settings(db)
    output_dir = os.getenv("KITCHEN_PRINT_OUTPUT_DIR", ".").strip() or "."

    settings = db.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    backend_raw = (getattr(settings, "backend", None) or "").strip().lower()
    backend: PrinterBackendName = (
        "escpos_network" if backend_raw == "escpos_network" else "file"
    )
    render_mode_raw = (getattr(settings, "render_mode", None) or "").strip().lower()
    render_mode: PrinterRenderModeName = (
        "image" if render_mode_raw == "image" else "text"
    )
    paper_width_px = int(getattr(settings, "paper_width_px", None) or 576)
    if paper_width_px not in (384, 576):
        paper_width_px = 576

    endpoint_rows = {
        row.route_key: row
        for row in db.query(PrinterRouteEndpoint)
        .filter(PrinterRouteEndpoint.route_key.in_(sorted(KNOWN_ENDPOINT_ROUTES)))
        .all()
    }

    routes: dict[str, PrinterEndpoint] = {}
    for route in sorted(KNOWN_ENDPOINT_ROUTES):
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
