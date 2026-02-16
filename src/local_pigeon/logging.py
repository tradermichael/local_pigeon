"""
Logging Configuration for Local Pigeon

Provides structured logging with:
- File logging to data_dir/logs/
- Console logging with configurable verbosity
- Debug mode for development
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from local_pigeon.config import get_data_dir

# Module loggers
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    Usage:
        from local_pigeon.logging import get_logger
        logger = get_logger(__name__)
        logger.debug("Processing request")
        logger.info("Tool executed successfully")
        logger.error("Failed to connect", exc_info=True)
    """
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(f"local_pigeon.{name}")
    _loggers[name] = logger
    return logger


def setup_logging(
    level: str = "INFO",
    log_file: bool = True,
    console: bool = True,
    debug_mode: bool = False,
) -> None:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Whether to log to file
        console: Whether to log to console
        debug_mode: Enable verbose debug logging
    """
    if debug_mode:
        level = "DEBUG"
    
    # Root logger for local_pigeon
    root_logger = logging.getLogger("local_pigeon")
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Formatter
    if debug_mode:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
            datefmt="%H:%M:%S"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S"
        )
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_dir = get_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Daily log file
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_path = log_dir / f"pigeon_{date_str}.log"
        
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        root_logger.addHandler(file_handler)
    
    # Log startup
    root_logger.info(f"Logging initialized (level={level}, debug={debug_mode})")


def enable_debug_mode() -> None:
    """Enable debug logging for all components."""
    setup_logging(debug_mode=True)


def get_recent_logs(
    lines: int = 100,
    level_filter: Optional[str] = None,
) -> str:
    """
    Get recent log entries from today's log file.
    
    Args:
        lines: Number of lines to return
        level_filter: Optional filter by level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Recent log entries as string
    """
    log_dir = get_data_dir() / "logs"
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_path = log_dir / f"pigeon_{date_str}.log"
    
    if not log_path.exists():
        return "No log file found for today."
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        
        # Filter by level if specified
        if level_filter:
            level_filter = level_filter.upper()
            all_lines = [l for l in all_lines if f"| {level_filter}" in l]
        
        # Get last N lines
        recent = all_lines[-lines:]
        return "".join(recent)
    except Exception as e:
        return f"Error reading logs: {e}"


def list_log_files() -> list[Path]:
    """List all available log files."""
    log_dir = get_data_dir() / "logs"
    if not log_dir.exists():
        return []
    return sorted(log_dir.glob("pigeon_*.log"), reverse=True)
