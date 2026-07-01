"""Logging configuration for the DAV video converter."""

import logging
import os
import sys
import threading

_log_lock = threading.Lock()

_LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def setup_logging(
    log_level: str = "INFO", log_file: str | None = None
) -> logging.Logger:
    """
    Set up comprehensive logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path

    Returns:
        Configured logger instance
    """
    with _log_lock:
        logger = logging.getLogger("dav2mkv")

        if logger.handlers:
            return logger

        level = _LOG_LEVELS.get(log_level.upper(), logging.INFO)
        logger.setLevel(level)

        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] "
            "- %(funcName)s() - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        simple_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

        if log_file:
            try:
                log_dir = os.path.dirname(log_file)
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)
                file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(detailed_formatter)
                logger.addHandler(file_handler)
                logger.info("Logging to file: %s", log_file)
            except OSError as exc:
                logger.warning("Failed to setup file logging: %s", exc)

    return logger
