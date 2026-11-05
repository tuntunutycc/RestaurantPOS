"""Printer route constants and config dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PrinterBackendName = Literal["file", "escpos_network", "windows_printer"]
PrinterRenderModeName = Literal["text", "image"]
PrinterRoleName = Literal["cashier", "kitchen", "bar", "other"]

DEFAULT_PRINTER_ROUTE = "food"
CASHIER_PRINTER_ROUTE = "cashier"
CASHIER_PRINTER_ROLE = "cashier"
KITCHEN_PRINTER_ROLE = "kitchen"
BAR_PRINTER_ROLE = "bar"

# Category menu routing (menu categories stay drinks|food).
CATEGORY_PRINTER_ROUTES = frozenset({"drinks", "food"})
# Legacy route keys used for file output filenames / ticket labels.
KNOWN_ENDPOINT_ROUTES = frozenset({"drinks", "food", "cashier"})
# Backward-compatible alias; prefer CATEGORY_PRINTER_ROUTES for kitchen.
KNOWN_PRINTER_ROUTES = CATEGORY_PRINTER_ROUTES
PRINTER_ROLES = frozenset({"cashier", "kitchen", "bar", "other"})

# Category route → preferred Printer.role (2A).
CATEGORY_ROUTE_TO_ROLE = {
    "food": KITCHEN_PRINTER_ROLE,
    "drinks": BAR_PRINTER_ROLE,
}
# Printer.role → legacy file/route key for outputs.
ROLE_TO_LEGACY_ROUTE = {
    KITCHEN_PRINTER_ROLE: "food",
    BAR_PRINTER_ROLE: "drinks",
    CASHIER_PRINTER_ROLE: "cashier",
}


@dataclass(frozen=True)
class PrinterEndpoint:
    host: str
    port: int


@dataclass(frozen=True)
class PrinterConfig:
    backend: PrinterBackendName
    render_mode: PrinterRenderModeName
    paper_width_px: int
    output_dir: str
    routes: dict[str, PrinterEndpoint]
    font_path: str | None = None


def route_output_filename(route: str) -> str:
    return f"{route}_printer_output.txt"


def route_output_image_filename(route: str) -> str:
    return f"{route}_printer_output.png"
