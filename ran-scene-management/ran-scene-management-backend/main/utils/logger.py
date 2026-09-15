"""Project-wide logger factory.

Logs go to both stdout (so docker logs catches them) and a daily file under
``logs/``. LOG_LEVEL is read from env (default INFO).
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from main.utils.env_loader import get_str

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_configured: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    if name in _configured:
        return _configured[name]

    level_name = get_str("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        _configured[name] = logger
        return logger

    formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = TimedRotatingFileHandler(
        _LOG_DIR / "ransim-cu.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _configured[name] = logger
    return logger
