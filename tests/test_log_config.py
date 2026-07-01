"""Tests for logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

from dav2mkv.log_config import setup_logging


def _reset_dav2mkv_logger() -> None:
    logger = logging.getLogger("dav2mkv")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.WARNING)


def test_setup_logging_console_only() -> None:
    _reset_dav2mkv_logger()

    logger = setup_logging("DEBUG")
    assert logger.name == "dav2mkv"
    assert logger.level == logging.DEBUG
    assert any(
        isinstance(handler, logging.StreamHandler) for handler in logger.handlers
    )


def test_setup_logging_with_file(tmp_path: Path) -> None:
    _reset_dav2mkv_logger()
    log_file = tmp_path / "logs" / "conversion.log"
    logger = setup_logging("INFO", str(log_file))

    logger.info("test message")
    assert log_file.exists()
    assert "test message" in log_file.read_text(encoding="utf-8")


def test_setup_logging_returns_existing_logger(tmp_path: Path) -> None:
    _reset_dav2mkv_logger()
    first = setup_logging("INFO")
    second = setup_logging("DEBUG", str(tmp_path / "ignored.log"))
    assert first is second
    assert not (tmp_path / "ignored.log").exists()


def test_setup_logging_file_handler_failure(
    mocker: MagicMock,
    tmp_path: Path,
) -> None:
    _reset_dav2mkv_logger()
    mocker.patch("dav2mkv.log_config.os.makedirs", side_effect=OSError("denied"))

    logger = setup_logging("INFO", str(tmp_path / "logs" / "conversion.log"))
    logger.warning("still works")

    assert any(
        isinstance(handler, logging.StreamHandler) for handler in logger.handlers
    )
