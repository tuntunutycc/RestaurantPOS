"""Printer route constants and config dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PrinterBackendName = Literal["file", "escpos_network"]
PrinterRenderModeName = Literal["text", "image"]
DEFAULT_PRINTER_ROUTE = "food"
KNOWN_PRINTER_ROUTES = frozenset({"drinks", "food"})


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
