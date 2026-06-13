"""Send ESC/POS payloads to LAN thermal printers via raw TCP."""

from __future__ import annotations

import logging
import socket

from services.printing.config import PrinterConfig, PrinterEndpoint

logger = logging.getLogger(__name__)
SOCKET_TIMEOUT_SECONDS = 5.0


def _send_tcp(endpoint: PrinterEndpoint, payload: bytes) -> None:
    with socket.create_connection(
        (endpoint.host, endpoint.port),
        timeout=SOCKET_TIMEOUT_SECONDS,
    ) as conn:
        conn.sendall(payload)


def send_network_ticket(
    config: PrinterConfig,
    route: str,
    escpos_payload: bytes,
) -> None:
    endpoint = config.routes.get(route)
    if endpoint is None:
        raise RuntimeError(
            f"No LAN endpoint configured for printer route '{route}'. "
            f"Set PRINTER_{route.upper()}_HOST and PRINTER_{route.upper()}_PORT."
        )
    try:
        _send_tcp(endpoint, escpos_payload)
    except OSError as exc:
        logger.error(
            "Kitchen print failed for route %s at %s:%s — %s",
            route,
            endpoint.host,
            endpoint.port,
            exc,
        )
        raise
