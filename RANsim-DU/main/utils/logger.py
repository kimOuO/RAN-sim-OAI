"""統一 logger 設定。"""
from __future__ import annotations

import logging
import sys

_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(name)
