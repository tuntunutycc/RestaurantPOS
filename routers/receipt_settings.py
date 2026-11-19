"""Admin API for the receipt texts (shop name, address, phone, thank-you, footer).

Spec: specs/feature-receipt-text
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import ReceiptSettings, User
from rbac import ADMIN_PANEL_ROLES
from schemas import ReceiptSettingsResponse, ReceiptSettingsUpdate

router = APIRouter(prefix="/api/admin")

_FIELDS = ("shop_name", "address", "phone", "thank_you", "footer_note")


def _response(row: ReceiptSettings | None) -> ReceiptSettingsResponse:
    return ReceiptSettingsResponse(**{name: (getattr(row, name, None) or "") for name in _FIELDS})


@router.get("/receipt-settings", response_model=ReceiptSettingsResponse)
def get_receipt_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Texts printed on the cashier receipt. Blank = built-in default."""
    return _response(db.query(ReceiptSettings).filter(ReceiptSettings.id == 1).first())


@router.put("/receipt-settings", response_model=ReceiptSettingsResponse)
def update_receipt_settings(
    body: ReceiptSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Save the receipt texts. An omitted field keeps its value; "" clears it."""
    row = db.query(ReceiptSettings).filter(ReceiptSettings.id == 1).first()
    if row is None:
        row = ReceiptSettings(id=1, **{name: "" for name in _FIELDS})
        db.add(row)
    for name in _FIELDS:
        value = getattr(body, name)
        if value is not None:
            setattr(row, name, value)
    db.commit()
    db.refresh(row)
    return _response(row)
