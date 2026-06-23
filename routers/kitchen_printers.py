"""Admin API for kitchen printer settings (backend + LAN endpoints)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import KitchenPrinterSettings, PrinterRouteEndpoint, User
from schemas import (
    KitchenPrinterSettingsResponse,
    KitchenPrinterSettingsUpdate,
    PrinterRouteEndpointResponse,
)
from services.printing.config import KNOWN_PRINTER_ROUTES
from services.printing.settings import seed_kitchen_printer_settings

router = APIRouter(prefix="/api/admin")


def _build_settings_response(db: Session) -> KitchenPrinterSettingsResponse:
    seed_kitchen_printer_settings(db)
    settings = db.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    endpoints = {
        row.route_key: row
        for row in db.query(PrinterRouteEndpoint)
        .filter(PrinterRouteEndpoint.route_key.in_(sorted(KNOWN_PRINTER_ROUTES)))
        .all()
    }
    backend = (getattr(settings, "backend", None) or "file").strip().lower()
    if backend not in ("file", "escpos_network"):
        backend = "file"
    render_mode = (getattr(settings, "render_mode", None) or "text").strip().lower()
    if render_mode not in ("text", "image"):
        render_mode = "text"
    paper_width_px = int(getattr(settings, "paper_width_px", None) or 576)
    if paper_width_px not in (384, 576):
        paper_width_px = 576
    routes = [
        PrinterRouteEndpointResponse(
            route_key=route_key,
            host=(endpoints[route_key].host or None) if route_key in endpoints else None,
            port=int(getattr(endpoints.get(route_key), "port", None) or 9100),
        )
        for route_key in sorted(KNOWN_PRINTER_ROUTES)
    ]
    return KitchenPrinterSettingsResponse(
        backend=backend,
        render_mode=render_mode,
        paper_width_px=paper_width_px,
        routes=routes,
    )


@router.get("/kitchen-printers", response_model=KitchenPrinterSettingsResponse)
def get_kitchen_printer_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    """Return kitchen printer backend mode and route LAN endpoints. Admin only."""
    return _build_settings_response(db)


@router.put("/kitchen-printers", response_model=KitchenPrinterSettingsResponse)
def update_kitchen_printer_settings(
    body: KitchenPrinterSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    """Update kitchen printer backend mode and route LAN endpoints. Admin only."""
    seed_kitchen_printer_settings(db)
    settings = db.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    if not settings:
        raise HTTPException(status_code=500, detail="Kitchen printer settings are not initialized")

    settings.backend = body.backend
    settings.render_mode = body.render_mode
    settings.paper_width_px = body.paper_width_px
    endpoints = {
        row.route_key: row
        for row in db.query(PrinterRouteEndpoint)
        .filter(PrinterRouteEndpoint.route_key.in_(sorted(KNOWN_PRINTER_ROUTES)))
        .all()
    }

    for route_update in body.routes:
        endpoint = endpoints.get(route_update.route_key)
        if endpoint is None:
            endpoint = PrinterRouteEndpoint(route_key=route_update.route_key)
            db.add(endpoint)
            endpoints[route_update.route_key] = endpoint
        host = (route_update.host or "").strip() or None
        endpoint.host = host
        endpoint.port = int(route_update.port or 9100)

    db.commit()
    return _build_settings_response(db)
