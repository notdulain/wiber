"""
Structured logging configuration for the distributed messaging system.
"""

import logging
import sys
from typing import Optional

import structlog


def setup_logging(
    level: str = "INFO",
    node_id: Optional[str] = None,
    component: Optional[str] = None,
) -> structlog.BoundLogger:
    """Configure structured logging and return a bound logger."""

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, level.upper()),
        stream=sys.stdout,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(colors=True),
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

