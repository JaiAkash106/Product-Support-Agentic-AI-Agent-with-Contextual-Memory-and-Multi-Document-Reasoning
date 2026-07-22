from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from product_support_agent.config import Settings


_LOGGING_CONFIGURED = False


def _build_logging_config(settings: Settings) -> dict:
    log_file = Path(settings.logging.log_file)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": settings.logging.format,
                "datefmt": settings.logging.date_format,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.logging.level,
                "formatter": "standard",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.logging.level,
                "formatter": "standard",
                "filename": str(log_file),
                "maxBytes": settings.logging.max_bytes,
                "backupCount": settings.logging.backup_count,
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": settings.logging.level,
            "handlers": ["console", "file"],
        },
    }


def configure_logging(settings: Settings) -> None:
    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        return

    log_file = Path(settings.logging.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(_build_logging_config(settings))
    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
