"""Admin API for global kitchen printer backend settings (not per-host CRUD)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import KitchenPrinterSettings, User
from schemas import KitchenPrinterSettingsResponse, KitchenPrinterSettingsUpdate
from rbac import ADMIN_PANEL_ROLES
from services.printing.settings import seed_kitchen_printer_settings

router = APIRouter(prefix="/api/admin")


def _build_settings_response(db: Session) -> KitchenPrinterSettingsResponse:
    seed_kitchen_printer_settings(db)
    settings = db.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    backend = (getattr(settings, "backend", None) or "file").strip().lower()
    if backend not in ("file", "escpos_network"):
        backend = "file"
    render_mode = (getattr(settings, "render_mode", None) or "text").strip().lower()
    if render_mode not in ("text", "image"):
        render_mode = "text"
    paper_width_px = int(getattr(settings, "paper_width_px", None) or 576)
    if paper_width_px not in (384, 576):
        paper_width_px = 576
    return KitchenPrinterSettingsResponse(
        backend=backend,
        render_mode=render_mode,
        paper_width_px=paper_width_px,
        routes=[],
    )


@router.get("/kitchen-printers", response_model=KitchenPrinterSettingsResponse)
def get_kitchen_printer_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Return global print backend mode. Hosts are managed via /api/printers CRUD."""
    return _build_settings_response(db)


@router.put("/kitchen-printers", response_model=KitchenPrinterSettingsResponse)
def update_kitchen_printer_settings(
    body: KitchenPrinterSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Update global print backend mode. Route hosts in body are ignored (use Printer CRUD)."""
    seed_kitchen_printer_settings(db)
    settings = db.query(KitchenPrinterSettings).filter(KitchenPrinterSettings.id == 1).first()
    if not settings:
        raise HTTPException(status_code=500, detail="Kitchen printer settings are not initialized")

    settings.backend = body.backend
    settings.render_mode = body.render_mode
    settings.paper_width_px = body.paper_width_px
    db.commit()
    return _build_settings_response(db)
