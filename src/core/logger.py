"""Logging configuration."""

import logging
import platform
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

from .config import Config


def setup_logger(name="AWG Kumulus"):
    """Set up application logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        # Ensure logs directory exists
        Config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        log_file = Config.LOGS_DIR / f"awg_kumulus_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception as e:
        # If file logging fails, log to console only
        logger.warning(f"Failed to setup file logging: {e}")
    
    return logger

