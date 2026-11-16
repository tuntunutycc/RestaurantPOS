"""Send ESC/POS payloads to a Windows installed printer queue (RAW)."""

from __future__ import annotations

import logging
from typing import Any

from services.printing.print_log import ensure_print_file_logging

logger = logging.getLogger(__name__)

try:
    import win32print  # type: ignore
except Exception:  # pragma: no cover - non-Windows / missing pywin32
    win32print = None  # type: ignore


def windows_printing_available() -> bool:
    return win32print is not None


def _printer_name_from_row(row: Any, level: int) -> str | None:
    """Extract queue name from EnumPrinters row (tuple or dict, levels 1/2/4/5)."""
    if isinstance(row, dict):
        for key in ("pPrinterName", "PrinterName", "name"):
            val = row.get(key)
            if val:
                name = str(val).strip()
                return name or None
        return None
    if not isinstance(row, (list, tuple)) or not row:
        return None
    # Level 1: (flags:int, description, name, comment) — name at index 2
    if level == 1 or (isinstance(row[0], int) and len(row) >= 3):
        try:
            name = str(row[2]).strip()
            return name or None
        except Exception:
            return None
    # Level 4/5 (and many Level 2 tuple layouts): name at index 0
    try:
        name = str(row[0]).strip()
        return name or None
    except Exception:
        return None


def list_windows_printers() -> list[str]:
    """Return all installed Windows print queue names (USB, Bluetooth, network, etc.).

    Enumerates LOCAL and CONNECTIONS separately (and combined), across common
    info levels — a single LOCAL|CONNECTIONS call often misses USB queues on
    Windows 10/11.
    """
    ensure_print_file_logging()
    if win32print is None:
        logger.warning(
            "Windows printer list unavailable: pywin32 not installed or not on Windows"
        )
        return []

    flag_candidates: list[int] = []
    for attr in ("PRINTER_ENUM_LOCAL", "PRINTER_ENUM_CONNECTIONS", "PRINTER_ENUM_NETWORK"):
        if hasattr(win32print, attr):
            flag_candidates.append(int(getattr(win32print, attr)))
    # Combined LOCAL|CONNECTIONS (legacy single-call path)
    local = int(getattr(win32print, "PRINTER_ENUM_LOCAL", 0) or 0)
    connections = int(getattr(win32print, "PRINTER_ENUM_CONNECTIONS", 0) or 0)
    if local and connections:
        flag_candidates.append(local | connections)

    levels = (4, 1, 2, 5)
    names: set[str] = set()
    for flags in flag_candidates:
        if not flags:
            continue
        for level in levels:
            try:
                rows: list[Any] = win32print.EnumPrinters(flags, None, level)
            except Exception as exc:
                logger.debug(
                    "EnumPrinters flags=%s level=%s failed: %s", flags, level, exc
                )
                continue
            for row in rows or []:
                name = _printer_name_from_row(row, level)
                if name:
                    names.add(name)

    found = sorted(names)
    logger.info("Windows printer queues found=%s names=%s", len(found), found)
    return found


def _format_windows_print_error(printer_name: str, exc: BaseException) -> str:
    """Map common spooler failures to an actionable message."""
    raw = str(exc) or exc.__class__.__name__
    lowered = raw.lower()
    if "access is denied" in lowered or "access denied" in lowered:
        hint = "permission denied — run the POS service with rights to use this printer"
    elif "busy" in lowered or "being used" in lowered:
        hint = "printer is busy or locked by another job"
    elif "offline" in lowered or "not available" in lowered:
        hint = "printer appears offline or disconnected (check USB/Bluetooth)"
    elif "cannot find" in lowered or "unknown printer" in lowered or "invalid printer" in lowered:
        hint = "queue name not found — re-select the Windows printer in Admin"
    else:
        hint = "check cable, power, driver, and that the queue is Online"
    return f"Windows print failed for '{printer_name}': {raw} ({hint})"


def send_raw_to_windows_printer(printer_name: str, payload: bytes) -> None:
    """Write raw ESC/POS bytes to a Windows print queue using datatype RAW."""
    ensure_print_file_logging()
    if win32print is None:
        raise RuntimeError(
            "Windows printer backend requires pywin32 on a Windows host "
            "(pip install -r requirements-windows.txt)"
        )
    name = (printer_name or "").strip()
    if not name:
        raise RuntimeError("windows_printer_name is required for Windows receipt printing")
    if not payload:
        raise RuntimeError("Empty print payload")

    logger.info(
        "Windows RAW print starting queue=%s payload_bytes=%s",
        name,
        len(payload),
    )
    try:
        handle = win32print.OpenPrinter(name)
    except Exception as exc:
        raise RuntimeError(_format_windows_print_error(name, exc)) from exc

    doc_started = False
    try:
        try:
            win32print.StartDocPrinter(handle, 1, ("POS Receipt", None, "RAW"))
            doc_started = True
            win32print.StartPagePrinter(handle)
            written = win32print.WritePrinter(handle, payload)
            if written is not None and int(written) < len(payload):
                raise RuntimeError(
                    f"Windows printer wrote {written} of {len(payload)} bytes to '{name}'"
                )
            win32print.EndPagePrinter(handle)
            logger.info(
                "Windows RAW print finished queue=%s written=%s",
                name,
                written if written is not None else len(payload),
            )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(_format_windows_print_error(name, exc)) from exc
        finally:
            if doc_started:
                try:
                    win32print.EndDocPrinter(handle)
                except Exception as exc:
                    logger.warning(
                        "EndDocPrinter failed for '%s': %s", name, exc
                    )
    finally:
        try:
            win32print.ClosePrinter(handle)
        except Exception as exc:
            logger.warning("ClosePrinter failed for '%s': %s", name, exc)
