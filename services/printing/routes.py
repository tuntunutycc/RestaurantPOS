"""Resolve category printer routes to canonical route names and printer roles."""

from __future__ import annotations

import logging

from services.printing.config import (
    BAR_PRINTER_ROLE,
    CATEGORY_PRINTER_ROUTES,
    CATEGORY_ROUTE_TO_ROLE,
    DEFAULT_PRINTER_ROUTE,
    KITCHEN_PRINTER_ROLE,
)

logger = logging.getLogger(__name__)


def resolve_printer_route(printer_route: str | None) -> str:
    """Normalize category printer_route; default and unknown values -> food."""
    normalized = (printer_route or "").strip().lower()
    if not normalized:
        return DEFAULT_PRINTER_ROUTE
    if normalized in CATEGORY_PRINTER_ROUTES:
        return normalized
    logger.warning(
        "Unknown category printer_route %r; falling back to %s",
        printer_route,
        DEFAULT_PRINTER_ROUTE,
    )
    return DEFAULT_PRINTER_ROUTE


def category_route_to_printer_role(category_route: str | None) -> str:
    """
    Map menu category route to Printer.role (decision 2A).
    food → kitchen; drinks → bar.
    """
    route = resolve_printer_route(category_route)
    return CATEGORY_ROUTE_TO_ROLE.get(route, KITCHEN_PRINTER_ROLE)


def role_fallback_chain(role: str) -> list[str]:
    """Ordered roles to try when resolving a LAN endpoint."""
    normalized = (role or "").strip().lower()
    if normalized == BAR_PRINTER_ROLE:
        return [BAR_PRINTER_ROLE, KITCHEN_PRINTER_ROLE]
    if normalized == KITCHEN_PRINTER_ROLE:
        return [KITCHEN_PRINTER_ROLE]
    if normalized == "cashier":
        return ["cashier"]
    return [normalized, KITCHEN_PRINTER_ROLE]
