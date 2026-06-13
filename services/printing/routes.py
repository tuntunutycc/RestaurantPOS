"""Resolve category printer routes to canonical route names."""

from __future__ import annotations

import logging

from services.printing.config import DEFAULT_PRINTER_ROUTE, KNOWN_PRINTER_ROUTES

logger = logging.getLogger(__name__)


def resolve_printer_route(printer_route: str | None) -> str:
    """Normalize category printer_route; default and unknown values -> food."""
    normalized = (printer_route or "").strip().lower()
    if not normalized:
        return DEFAULT_PRINTER_ROUTE
    if normalized in KNOWN_PRINTER_ROUTES:
        return normalized
    logger.warning(
        "Unknown category printer_route %r; falling back to %s",
        printer_route,
        DEFAULT_PRINTER_ROUTE,
    )
    return DEFAULT_PRINTER_ROUTE
