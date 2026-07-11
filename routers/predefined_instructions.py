"""CRUD API for predefined special-instruction quick tags."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import PredefinedInstruction, User
from rbac import ADMIN_PANEL_ROLES, POS_ORDER_ROLES
from schemas import PredefinedInstructionCreate, PredefinedInstructionResponse
from services.predefined_instructions import seed_predefined_instructions

router = APIRouter(prefix="/api", tags=["predefined-instructions"])


@router.get("/predefined-instructions", response_model=list[PredefinedInstructionResponse])
def list_predefined_instructions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(POS_ORDER_ROLES)),
):
    """List all quick instruction tags for waiter UI."""
    seed_predefined_instructions(db)
    rows = db.query(PredefinedInstruction).order_by(PredefinedInstruction.id.asc()).all()
    return rows


@router.post("/predefined-instructions", response_model=PredefinedInstructionResponse)
def create_predefined_instruction(
    body: PredefinedInstructionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Add a new quick instruction tag. Admin only."""
    row = PredefinedInstruction(text=body.text)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Instruction tag already exists")
    db.refresh(row)
    return row


@router.delete("/predefined-instructions/{instruction_id}")
def delete_predefined_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_PANEL_ROLES)),
):
    """Remove a quick instruction tag. Admin only."""
    row = db.query(PredefinedInstruction).filter(PredefinedInstruction.id == instruction_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Instruction tag not found")
    db.delete(row)
    db.commit()
    return {"ok": True, "id": instruction_id}
