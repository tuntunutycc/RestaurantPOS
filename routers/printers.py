"""Dynamic printer CRUD and terminal list API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import Printer, User
from rbac import ADMIN_PANEL_ROLES, CHECKOUT_ROLES
from schemas import PrinterCreate, PrinterResponse, PrinterUpdate
from services.printing.config import PRINTER_ROLES
from services.printing.settings import seed_default_printers

router = APIRouter(prefix="/api")


def _normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    normalized = role.strip().lower()
    if normalized not in PRINTER_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported printer role; use one of: {', '.join(sorted(PRINTER_ROLES))}",
        )
    return normalized


@router.get("/printers", response_model=list[PrinterResponse])
def list_printers(
    role: str | None = Query(None, description="Optional role filter, e.g. cashier"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CHECKOUT_ROLES + ADMIN_PANEL_ROLES)),
):
    """
    List printers.
    - Non-admin checkout roles: only `role=cashier` (active) for terminal dropdown.
    - Admin/root: all printers, optional role filter (includes inactive).
    """
    seed_default_printers(db)
    normalized_role = _normalize_role(role) if role else None
    user_role = (current_user.role or "").strip().lower()
    is_admin = user_role in ("admin", "root")

    if not is_admin:
        if normalized_role != "cashier":
            raise HTTPException(
                status_code=400,
                detail="Cashiers may only list printers with role=cashier",
            )
        rows = (
            db.query(Printer)
            .filter(Printer.role == "cashier", Printer.is_active.is_(True))
            .order_by(Printer.id.asc())
            .all()
        )
        return rows

    q = db.query(Printer)
    if normalized_role:
        q = q.filter(Printer.role == normalized_role)
    return q.order_by(Printer.id.asc()).all()


@router.post("/printers", response_model=PrinterResponse)
def create_printer(
    body: PrinterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Create a named printer. Admin only."""
    seed_default_printers(db)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="printer name is required")
    row = Printer(
        name=name,
        host=(body.host or "").strip() or None,
        port=int(body.port or 9100),
        role=body.role,
        is_active=bool(body.is_active),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/printers/{printer_id}", response_model=PrinterResponse)
def update_printer(
    printer_id: int,
    body: PrinterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Update a printer. Admin only."""
    row = db.query(Printer).filter(Printer.id == printer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Printer not found")
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="printer name is required")
        row.name = name
    if body.host is not None:
        row.host = body.host.strip() or None
    if body.port is not None:
        row.port = int(body.port)
    if body.role is not None:
        row.role = body.role
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/printers/{printer_id}")
def delete_printer(
    printer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Delete a printer. Admin only."""
    row = db.query(Printer).filter(Printer.id == printer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Printer not found")
    db.delete(row)
    db.commit()
    return {"ok": True, "id": printer_id}
