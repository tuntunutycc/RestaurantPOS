"""Printer diagnostic file logger writes under logs/printing/print.log."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from pathlib import Path

from services.printing.print_log import ensure_print_file_logging, get_print_log_path
from services.printing.service import _dispatch_payload
from services.printing.settings import load_printer_config


def test_ensure_print_file_logging_creates_log_path(tmp_path, monkeypatch):
    log_dir = tmp_path / "printing"
    log_file = log_dir / "print.log"
    monkeypatch.setattr("services.printing.print_log.PRINT_LOG_DIR", log_dir)
    monkeypatch.setattr("services.printing.print_log.PRINT_LOG_FILE", log_file)
    monkeypatch.setattr("services.printing.print_log._configured", False)

    path = ensure_print_file_logging()
    assert path == log_file
    assert log_dir.is_dir()
    assert get_print_log_path() == log_file

    ensure_print_file_logging()
    parent = logging.getLogger("services.printing")
    file_handlers = [
        h
        for h in parent.handlers
        if isinstance(h, logging.FileHandler)
        and Path(h.baseFilename) == log_file.resolve()
    ]
    assert len(file_handlers) == 1


def test_dispatch_writes_print_log_file(db_session, monkeypatch, tmp_path):
    log_dir = tmp_path / "printing"
    log_file = log_dir / "print.log"
    monkeypatch.setattr("services.printing.print_log.PRINT_LOG_DIR", log_dir)
    monkeypatch.setattr("services.printing.print_log.PRINT_LOG_FILE", log_file)
    monkeypatch.setattr("services.printing.print_log._configured", False)

    written: list[tuple] = []

    def _fake_file_ticket(*args, **kwargs) -> None:
        written.append(args)

    monkeypatch.setattr(
        "services.printing.service.send_file_ticket",
        _fake_file_ticket,
    )
    monkeypatch.setattr(
        "services.printing.service.send_file_ticket_image",
        lambda *args, **kwargs: written.append(args),
    )

    base = load_printer_config(db_session)
    forced = replace(base, backend="file", render_mode="text")
    monkeypatch.setattr(
        "services.printing.service.load_printer_config",
        lambda db: forced,
    )

    asyncio.run(
        _dispatch_payload(
            route="cashier",
            ticket_text="Test Ticket\nGrand Total: 1.00\n",
            db=db_session,
        )
    )

    assert written, "file backend should have been called"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Print dispatch" in content
    assert "log_file=" in content
    assert "Print diagnostics" in content
