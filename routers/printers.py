"""Dynamic printer CRUD and terminal list API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import Printer, User
from rbac import ADMIN_PANEL_ROLES, CHECKOUT_ROLES, POS_ORDER_ROLES
from schemas import (
    PrinterCreate,
    PrinterHealthResponse,
    PrinterNamedHealthItem,
    PrinterResponse,
    PrinterRouteHealthItem,
    PrinterTestPrintResponse,
    PrinterUpdate,
)
from services.printing.config import PRINTER_ROLES
from services.printing.health import (
    check_all_named_printers_health,
    check_kitchen_printers_health,
    check_named_printer_health,
    warning_for_offline_routes,
)
from services.printing.service import dispatch_printer_test
from services.printing.settings import load_printer_config, seed_default_printers

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


@router.get("/printers/health", response_model=PrinterHealthResponse)
def get_printers_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """Probe kitchen food/drinks LAN; admin also gets each named printer probe."""
    config = load_printer_config(db)
    results = check_kitchen_printers_health(db)
    warning = warning_for_offline_routes(results)
    named: list[PrinterNamedHealthItem] = []
    user_role = (current_user.role or "").strip().lower()
    if user_role in ("admin", "root"):
        named = [
            PrinterNamedHealthItem(
                printer_id=n.printer_id,
                name=n.name,
                role=n.role,
                online=n.online,
                status=n.status,  # type: ignore[arg-type]
                target=n.target,
                message=n.message,
                backend=n.backend,
            )
            for n in check_all_named_printers_health(db)
        ]
        named_offline = [n for n in named if n.status == "offline"]
        if named_offline:
            extra = ", ".join(f"{n.name} ({n.message})" for n in named_offline[:5])
            warning = (
                f"{warning} | Named printers offline: {extra}"
                if warning
                else f"Printer offline: {extra}"
            )
    route_ok = all(r.status != "offline" for r in results)
    named_ok = all(n.status != "offline" for n in named) if named else True
    return PrinterHealthResponse(
        backend=config.backend,
        printers=[
            PrinterRouteHealthItem(
                route=r.route,
                online=r.online,
                status=r.status,  # type: ignore[arg-type]
                host=r.host,
                port=r.port,
                message=r.message,
            )
            for r in results
        ],
        named_printers=named,
        all_online=route_ok and named_ok,
        warning=warning,
    )


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
        windows_printer_name=body.windows_printer_name,
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
    if "windows_printer_name" in body.model_fields_set:
        row.windows_printer_name = body.windows_printer_name
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


@router.get(
    "/printers/{printer_id}/health",
    response_model=PrinterNamedHealthItem,
)
def get_named_printer_health(
    printer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Probe one printer row (Windows queue / LAN). Admin/root only. No print job."""
    try:
        result = check_named_printer_health(db, printer_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PrinterNamedHealthItem(
        printer_id=result.printer_id,
        name=result.name,
        role=result.role,
        online=result.online,
        status=result.status,  # type: ignore[arg-type]
        target=result.target,
        message=result.message,
        backend=result.backend,
    )


@router.post(
    "/printers/{printer_id}/test-print",
    response_model=PrinterTestPrintResponse,
)
async def test_print_printer(
    printer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Send a short TEST PRINT slip to this printer. Admin/root only."""
    try:
        result = await dispatch_printer_test(printer_id=printer_id, db=db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": str(exc),
                "hint": (
                    "Check Print mode, Windows queue / LAN host, USB cable, and "
                    "logs/printing/print.log"
                ),
                "error": str(exc),
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": f"Test print failed: {exc}",
                "hint": "See logs/printing/print.log for spooler / LAN details",
                "error": str(exc),
            },
        ) from exc
    return PrinterTestPrintResponse(**result)
