"""統一 logger 設定 — 鐵則 3-2-3 utils 必備。"""
import logging
import logging.handlers
from pathlib import Path

from main.utils.env_loader import get_str


_LOG_LEVEL = getattr(logging, get_str("LOG_LEVEL", "INFO").upper(), logging.INFO)
_LOG_DIR = Path(get_str("LOG_DIR", "/app/logs"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(_LOG_LEVEL)
    fmt = logging.Formatter(_FORMAT, _DATEFMT)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_file = _LOG_DIR / "ranp-sim.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=14, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
