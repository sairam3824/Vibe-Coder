"""Structured logging helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from apps.api.config import get_settings


def configure_logging() -> None:
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, message: str, **context: Any) -> None:
    payload = {"message": message, **context}
    logger.info(json.dumps(payload, default=str))

