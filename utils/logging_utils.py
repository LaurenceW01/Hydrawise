#!/usr/bin/env python3
"""
Logging utilities for Hydrawise applications

Provides standardized logging setup for consistent log formatting and file management
across all Hydrawise automation scripts.

Author: AI Assistant
Date: 2025-08-27
"""

import os
import logging
from datetime import datetime
from typing import Optional


def setup_instance_logging(logger_name: str, base_filename: str = "automated_collector") -> tuple[logging.Logger, str]:
    """
    Setup logging with file handler using consistent naming convention for class instances
    
    Args:
        logger_name: Name for the logger (typically __name__)
        base_filename: Base name for the log file (without extension)
        
    Returns:
        Tuple of (logger, log_filename)
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'logs/{base_filename}_{timestamp}.log'
    
    # Get logger
    logger = logging.getLogger(logger_name)
    
    # Create file handler with UTF-8 encoding
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    logger.info(f"LOG: Logging to: {log_filename}")
    
    return logger, log_filename


def setup_main_logging(log_level: str = 'INFO', 
                      log_filename: Optional[str] = None,
                      enable_console: bool = True) -> None:
    """
    Setup main application logging with both file and console handlers
    
    Args:
        log_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        log_filename: Specific log filename (defaults to logs/automated_collector.log)
        enable_console: Whether to enable console output
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Default log filename
    if log_filename is None:
        log_filename = 'logs/automated_collector.log'
    
    # Create handlers
    handlers = []
    
    # File handler
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(getattr(logging, log_level))
    handlers.append(file_handler)
    
    # Console handler (optional)
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))
        handlers.append(console_handler)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Apply formatter to all handlers
    for handler in handlers:
        handler.setFormatter(formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        handlers=handlers,
        force=True  # Override any existing configuration
    )


def get_timestamped_filename(base_name: str, extension: str = '.log') -> str:
    """
    Generate a timestamped filename
    
    Args:
        base_name: Base name for the file
        extension: File extension (default: .log)
        
    Returns:
        Timestamped filename
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f'{base_name}_{timestamp}{extension}'


