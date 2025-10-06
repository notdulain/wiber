"""Structured logging configuration for the distributed messaging system."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import structlog


def setup_logging(
    level: str = "INFO",
    node_id: Optional[str] = None,
    component: Optional[str] = None,
    log_path: Optional[str | Path] = None,
) -> structlog.BoundLogger:
    """Configure structured logging and return a bound logger."""

    handlers: list[logging.Handler] = []
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))
    else:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        handlers=handlers,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()
    if node_id:
        logger = logger.bind(node_id=node_id)
    if component:
        logger = logger.bind(component=component)
    return logger


def get_logger(name: str, node_id: Optional[str] = None) -> structlog.BoundLogger:
    logger = structlog.get_logger(name)
    if node_id:
        logger = logger.bind(node_id=node_id)
    return logger
