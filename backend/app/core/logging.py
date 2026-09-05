from __future__ import annotations
import logging, sys, structlog
from app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(stream=sys.stdout, level=getattr(logging, settings.LOG_LEVEL, logging.INFO), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.LOG_LEVEL, logging.INFO)),
        cache_logger_on_first_use=True,
    )


log = structlog.get_logger("dunnflow")
