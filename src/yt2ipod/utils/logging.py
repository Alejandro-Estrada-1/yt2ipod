"""Structured logging for yt2ipod.

Wraps Python stdlib logging with a configured logger.
The TUI receives events, not log output — this logger is for
debugging, file logging, and plain CLI output.
"""

from __future__ import annotations

import logging
import sys

_logger: logging.Logger | None = None


def get_logger(name: str = "yt2ipod") -> logging.Logger:
    """Get the yt2ipod logger.

    Creates and configures the logger on first call.
    Subsequent calls return the same logger instance.

    Args:
        name: Logger name (default: "yt2ipod").

    Returns:
        Configured logger instance.
    """
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Console handler (stderr, so it doesn't interfere with --json output)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _logger = logger
    return logger


def set_debug(enabled: bool = True) -> None:
    """Enable or disable debug-level console output.

    Args:
        enabled: If True, show DEBUG messages on console.
    """
    logger = get_logger()
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(logging.DEBUG if enabled else logging.INFO)
            if enabled:
                handler.setFormatter(logging.Formatter(
                    fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
                    datefmt="%H:%M:%S",
                ))


def reset_logger() -> None:
    """Reset the logger (for testing)."""
    global _logger
    if _logger is not None:
        _logger.handlers.clear()
        _logger = None
