import json
import logging
from typing import Any

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    payload = {
        "event": event,
        "env": get_settings().env,
        **fields,
    }
    logger.log(level, json.dumps(payload, default=str, sort_keys=True))
