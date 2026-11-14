"""Probe kitchen/LAN printer reachability without sending a full print job."""

from __future__ import annotations

import socket
from dataclasses import dataclass

from sqlalchemy.orm import Session

from services.printing.config import PrinterEndpoint
from services.printing.settings import (
    load_printer_config,
    resolve_printer_endpoint_for_role,
)
from services.printing.routes import category_route_to_printer_role

PROBE_TIMEOUT_SECONDS = 1.5
KITCHEN_ROUTES = ("food", "drinks")


@dataclass(frozen=True)
class RouteHealth:
    route: str
    online: bool
    status: str  # online | offline | skipped
    host: str | None
    port: int | None
    message: str


def probe_tcp(host: str, port: int, *, timeout_seconds: float = PROBE_TIMEOUT_SECONDS) -> tuple[bool, str]:
    host = (host or "").strip()
    if not host:
        return False, "No host configured"
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_seconds):
            return True, "Reachable"
    except OSError as exc:
        return False, str(exc) or "Unreachable"


def check_route_health(
    db: Session | None,
    route: str,
    *,
    timeout_seconds: float = PROBE_TIMEOUT_SECONDS,
) -> RouteHealth:
    config = load_printer_config(db)
    if config.backend == "file":
        return RouteHealth(
            route=route,
            online=True,
            status="skipped",
            host=None,
            port=None,
            message="File backend (dev) — print goes to local files, not LAN",
        )

    endpoint: PrinterEndpoint | None = None
    if db is not None:
        role = category_route_to_printer_role(route)
        endpoint = resolve_printer_endpoint_for_role(db, role)
    if endpoint is None:
        endpoint = config.routes.get(route)

    if endpoint is None or not (endpoint.host or "").strip():
        # Kitchen/bar must have a LAN host when not in pure file/dev mode.
        # Under windows_printer, missing host used to silently write a local file
        # (order looked OK but kitchen got no paper) — treat as offline.
        if config.backend == "windows_printer":
            return RouteHealth(
                route=route,
                online=False,
                status="offline",
                host=None,
                port=None,
                message=(
                    "No LAN host for kitchen/bar under windows_printer — "
                    "ticket would not reach the kitchen printer"
                ),
            )
        return RouteHealth(
            route=route,
            online=False,
            status="offline",
            host=None,
            port=None,
            message="No LAN host configured",
        )

    ok, detail = probe_tcp(endpoint.host, endpoint.port, timeout_seconds=timeout_seconds)
    return RouteHealth(
        route=route,
        online=ok,
        status="online" if ok else "offline",
        host=endpoint.host,
        port=endpoint.port,
        message=detail if ok else f"Unreachable: {detail}",
    )


def check_kitchen_printers_health(
    db: Session | None,
    *,
    routes: tuple[str, ...] | list[str] = KITCHEN_ROUTES,
    timeout_seconds: float = PROBE_TIMEOUT_SECONDS,
) -> list[RouteHealth]:
    return [
        check_route_health(db, route, timeout_seconds=timeout_seconds)
        for route in routes
    ]


def warning_for_offline_routes(results: list[RouteHealth]) -> str | None:
    offline = [r for r in results if r.status == "offline"]
    if not offline:
        return None
    parts = []
    for r in offline:
        target = f"{r.host}:{r.port}" if r.host else "(no host)"
        parts.append(f"{r.route} ({target})")
    return (
        "Kitchen printer offline: "
        + ", ".join(parts)
        + ". Order was saved; ticket may not have printed."
    )
