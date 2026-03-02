"""Logging configuration helpers."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(name: str, log_file: str | None = None, level: int = logging.DEBUG) -> logging.Logger:
    """Configure and return a logger.

    Parameters:
        name: Logger name (units: none).
        log_file: Optional file path for debug log output (units: none).
        level: Logger base level from logging module (units: none).
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
