import logging
import sys
from logging.handlers import RotatingFileHandler

from app.config import settings

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def _build_logger() -> logging.Logger:
    log = logging.getLogger("lumina")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    log.addHandler(console)

    file_handler = RotatingFileHandler(
        settings.LOG_DIR / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)
    log.propagate = False
    return log


logger = _build_logger()
