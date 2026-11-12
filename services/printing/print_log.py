"""Dedicated file logger for printer diagnostics.

Writes to logs/printing/print.log so Windows operators can open the file
after a failed/garbled print without digging through the uvicorn console.
"""

from __future__ import annotations

import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRINT_LOG_DIR = PROJECT_ROOT / "logs" / "printing"
PRINT_LOG_FILE = PRINT_LOG_DIR / "print.log"

_configured = False


def get_print_log_path() -> Path:
    return PRINT_LOG_FILE


def ensure_print_file_logging() -> Path:
    """Attach a UTF-8 file handler under logs/printing/print.log once."""
    global _configured
    PRINT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Parent logger covers service.py, image_renderer.py, backends/*, settings.py
    parent = logging.getLogger("services.printing")
    parent.setLevel(logging.DEBUG)

    target = str(PRINT_LOG_FILE.resolve())
    already = False
    for handler in parent.handlers:
        if isinstance(handler, logging.FileHandler) and getattr(
            handler, "baseFilename", None
        ) == target:
            already = True
            break

    if not already:
        handler = logging.FileHandler(PRINT_LOG_FILE, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            )
        )
        parent.addHandler(handler)

    # Dedicated alias used by helpers that want an explicit print logger name.
    alias = logging.getLogger("pos.printing")
    alias.setLevel(logging.DEBUG)
    if not already:
        # Reuse same file handler reference so both names write one file.
        for handler in parent.handlers:
            if isinstance(handler, logging.FileHandler) and getattr(
                handler, "baseFilename", None
            ) == target:
                if handler not in alias.handlers:
                    alias.addHandler(handler)
                break

    _configured = True
    return PRINT_LOG_FILE


def get_print_logger(name: str = "pos.printing") -> logging.Logger:
    ensure_print_file_logging()
    return logging.getLogger(name)
