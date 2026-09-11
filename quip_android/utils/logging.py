"""
Logging utility for quip-android-aglais-node.
Provides console formatting and session log rotation in logs/.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

_LOGGER: Optional[logging.Logger] = None


def setup_logger(
    name: str = "quip_android",
    level: int = logging.INFO,
    session_id: Optional[str] = None,
    log_dir: str = "logs",
) -> logging.Logger:
    """Configure and return the root package logger."""
    global _LOGGER
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    # Console handler with clean formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler for structured session logging
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
            sid = session_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"session_{sid}.log")
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
            logger.debug("Session log initialized at %s", log_file)
        except OSError as err:
            logger.warning("Could not initialize file log in %s: %s", log_dir, err)

    _LOGGER = logger
    return logger


def get_logger(name: str = "quip_android") -> logging.Logger:
    """Retrieve existing logger or initialize default."""
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER.getChild(name) if name != "quip_android" else _LOGGER
    return setup_logger(name)
