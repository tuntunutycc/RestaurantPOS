"""Cleaning and limits for the admin-editable receipt text (spec: feature-receipt-text).

Pure functions, no database. The printer does not wrap lines, so every printed
line is limited to ``MAX_LINE_CHARS`` characters (Unicode characters, not bytes).
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_LINE_CHARS = 32
MAX_MULTI_LINES = 3  # address and footer note


def clean_receipt_text(
    value: str | None,
    *,
    field_name: str,
    max_lines: int = 1,
) -> str:
    """Return the cleaned text (lines joined by ``\\n``) or raise ``ValueError``.

    - control characters (except the line break) are removed;
    - every line is trimmed and blank lines are dropped;
    - a single-line field (``max_lines == 1``) with a line break is refused;
    - more than ``max_lines`` lines, or a line over 32 characters, is refused.
    """
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or (ord(ch) >= 32 and ord(ch) != 127))
    if max_lines == 1 and "\n" in text.strip():
        raise ValueError(f"{field_name} must be a single line")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > max_lines:
        raise ValueError(f"{field_name} can have at most {max_lines} lines")
    for line in lines:
        if len(line) > MAX_LINE_CHARS:
            raise ValueError(
                f"{field_name}: each line can have at most {MAX_LINE_CHARS} characters "
                f"(got {len(line)}: '{line}')"
            )
    return "\n".join(lines)


def split_lines(value: str | None) -> list[str]:
    return [line for line in (value or "").split("\n") if line.strip()]


@dataclass(frozen=True)
class ReceiptTexts:
    """Texts printed on the cashier receipt. Blank = use the built-in default."""

    shop_name: str = ""
    address_lines: tuple[str, ...] = field(default_factory=tuple)
    phone: str = ""
    thank_you: str = ""
    footer_lines: tuple[str, ...] = field(default_factory=tuple)
