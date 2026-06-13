"""Append kitchen tickets to route-specific text files."""

from __future__ import annotations

import os

from services.printing.config import PrinterConfig, route_output_filename


def send_file_ticket(config: PrinterConfig, route: str, ticket_text: str) -> None:
    filename = route_output_filename(route)
    output_path = os.path.join(config.output_dir, filename)
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(ticket_text)
        if not ticket_text.endswith("\n"):
            handle.write("\n")
