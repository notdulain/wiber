"""
Logging configuration for Wiber distributed messaging system.

This module sets up structured logging with appropriate levels and formatting
for debugging distributed systems components.
"""

import logging
import sys
from typing import Optional

import structlog
from colorama import Fore, Style, init

# Initialize colorama for Windows compatibility
init(autoreset=True)


def setup_logging(
    level: str = "INFO",
    node_id: Optional[str] = None,
    component: Optional[str] = None,
) -> structlog.BoundLogger:
    """
    Set up structured logging for the distributed system.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        node_id: Node identifier for context
        component: Component name for context
        
    Returns:
        Configured structured logger
    """
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, level.upper()),
        stream=sys.stdout,
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            # Add timestamp
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="ISO"),
            # Add context information
            structlog.processors.add_log_level,
            # Colorize output for better readability
            _colorize_log_level,
            # Final formatting
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Create logger with context
    logger = structlog.get_logger()
    
    # Add node and component context if provided
    if node_id:
        logger = logger.bind(node_id=node_id)
    if component:
        logger = logger.bind(component=component)
        
    return logger


def _colorize_log_level(logger, method_name, event_dict):
    """
    Add color coding to log levels for better visual distinction.
    
    This is especially useful when debugging distributed systems with
    multiple nodes and components.
    """
    level_colors = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED + Style.BRIGHT,
    }
    
    level = event_dict.get("level", "")
    if level in level_colors:
        event_dict["level"] = f"{level_colors[level]}{level}{Style.RESET_ALL}"
    
    return event_dict


# Convenience function for getting a logger
def get_logger(name: str, node_id: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a logger instance for a specific component.
    
    Args:
        name: Logger name (usually module name)
        node_id: Node identifier for context
        
    Returns:
        Configured logger instance
    """
    logger = structlog.get_logger(name)
    if node_id:
        logger = logger.bind(node_id=node_id)
    return logger
