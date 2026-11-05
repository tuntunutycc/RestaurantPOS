"""Send ESC/POS payloads to a Windows installed printer queue (RAW)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import win32print  # type: ignore
except Exception:  # pragma: no cover - non-Windows / missing pywin32
    win32print = None  # type: ignore


def windows_printing_available() -> bool:
    return win32print is not None


def list_windows_printers() -> list[str]:
    """Return installed local/connection printer queue names (sorted, unique)."""
    if win32print is None:
        return []
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    try:
        rows: list[Any] = win32print.EnumPrinters(flags)
    except Exception as exc:
        logger.error("Failed to enumerate Windows printers: %s", exc)
        return []
    names: set[str] = set()
    for row in rows or []:
        # EnumPrinters returns tuples; name is typically index 2.
        try:
            name = str(row[2]).strip()
        except Exception:
            continue
        if name:
            names.add(name)
    return sorted(names)


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
