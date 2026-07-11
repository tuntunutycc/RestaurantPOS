"""Seed and helpers for predefined instruction quick tags."""

from sqlalchemy.orm import Session

from models import PredefinedInstruction

DEFAULT_PREDEFINED_INSTRUCTIONS = (
    "အချိုမှုန့်ရှောင်",
    "အစပ်လျှော့",
    "နံနံပင်ရှောင်",
)


def seed_predefined_instructions(db: Session) -> None:
    """Insert default Myanmar quick tags when the table is empty."""
    existing = db.query(PredefinedInstruction.id).limit(1).first()
    if existing is not None:
        return
    for text in DEFAULT_PREDEFINED_INSTRUCTIONS:
        db.add(PredefinedInstruction(text=text))
    db.commit()
