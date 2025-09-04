#!/usr/bin/env python3
"""
Universal Logging Configuration for Hydrawise
Handles logging for both local development (file-based) and render.com deployment (stdout)

Environment Variables:
- LOGGING_MODE: 'file' (default for local) or 'stdout' (for render.com)
- LOG_LEVEL: 'DEBUG', 'INFO' (default), 'WARNING', 'ERROR'
- LOG_FORMAT: 'detailed' (default) or 'simple'
- ENABLE_FILE_LOGGING: 'true' (default) or 'false' (for render.com)

Author: AI Assistant
Date: 2025-01-27
"""

import os
import sys
import logging
from datetime import datetime
from typing import Optional, Union
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_logging_config() -> dict:
    """
    Get logging configuration based on environment variables
    
    Returns:
        Dictionary with logging configuration
    """
    # Determine if we're running on render.com or locally
    is_render = os.getenv('RENDER') == 'true' or os.getenv('RENDER_SERVICE_ID') is not None
    
    # Get configuration from environment
    config = {
        'mode': os.getenv('LOGGING_MODE', 'stdout' if is_render else 'file'),
        'level': os.getenv('LOG_LEVEL', 'INFO').upper(),
        'format_type': os.getenv('LOG_FORMAT', 'detailed'),
        'enable_file_logging': os.getenv('ENABLE_FILE_LOGGING', 'false' if is_render else 'true').lower() == 'true',
        'enable_console_logging': os.getenv('ENABLE_CONSOLE_LOGGING', 'true').lower() == 'true',
        'is_render': is_render,
        'log_directory': os.getenv('LOG_DIRECTORY', 'logs')
    }
    
    return config

def get_log_formatter(format_type: str = 'detailed') -> logging.Formatter:
    """
    Get appropriate log formatter based on deployment environment
    
    Args:
        format_type: 'detailed', 'simple', or 'json'
        
    Returns:
        Configured logging formatter
    """
    if format_type == 'json':
        # JSON formatter for structured logging (useful for cloud services)
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }
                
                # Add exception info if present
                if record.exc_info:
                    log_entry['exception'] = self.formatException(record.exc_info)
                
                return json.dumps(log_entry)
        
        return JSONFormatter()
    
    elif format_type == 'simple':
        # Simple format for render.com stdout
        return logging.Formatter('%(levelname)s [%(name)s] %(message)s')
    
    else:  # detailed
        # Detailed format for local development
        return logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )

def setup_universal_logging(
    logger_name: str = None,
    base_filename: str = "hydrawise",
    log_level: str = None,
    force_mode: str = None
) -> tuple[logging.Logger, Optional[str]]:
    """
    Setup universal logging that works for both local and render.com deployment
    
    Args:
        logger_name: Name for the logger (defaults to root logger)
        base_filename: Base name for log file (when file logging is enabled)
        log_level: Override log level
        force_mode: Force specific logging mode ('file', 'stdout', 'both')
        
    Returns:
        Tuple of (logger, log_filename_or_None)
    """
    config = get_logging_config()
    
    # Override configuration if specified
    if log_level:
        config['level'] = log_level.upper()
    if force_mode:
        config['mode'] = force_mode
    
    # Get logger
    if logger_name:
        logger = logging.getLogger(logger_name)
    else:
        logger = logging.getLogger()
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Set log level
    try:
        logger.setLevel(getattr(logging, config['level']))
    except AttributeError:
        logger.setLevel(logging.INFO)
        logger.warning(f"Invalid log level '{config['level']}', using INFO")
    
    # Get appropriate formatter
    if config['is_render']:
        formatter = get_log_formatter('simple')
    else:
        formatter = get_log_formatter(config['format_type'])
    
    log_filename = None
    handlers_added = 0
    
    # Add stdout handler (always for render.com, optional for local)
    if config['mode'] in ['stdout', 'both'] or config['enable_console_logging']:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logger.level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        handlers_added += 1
        
        if config['is_render']:
            logger.info("Logging configured for render.com (stdout)")
    
    # Add file handler (for local development or when explicitly enabled)
    if config['mode'] in ['file', 'both'] or config['enable_file_logging']:
        try:
            # Create logs directory if it doesn't exist
            os.makedirs(config['log_directory'], exist_ok=True)
            
            # Generate timestamped filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_filename = os.path.join(config['log_directory'], f'{base_filename}_{timestamp}.log')
            
            # Create file handler with UTF-8 encoding
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setLevel(logger.level)
            
            # Use detailed formatter for files
            if config['is_render']:
                file_handler.setFormatter(get_log_formatter('detailed'))
            else:
                file_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            handlers_added += 1
            
            logger.info(f"File logging enabled: {log_filename}")
            
        except Exception as e:
            # If file logging fails (e.g., read-only filesystem), continue with stdout only
            logger.warning(f"File logging failed, using stdout only: {e}")
    
    # Ensure at least one handler is added
    if handlers_added == 0:
        # Fallback to stdout
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logger.level)
        console_handler.setFormatter(get_log_formatter('simple'))
        logger.addHandler(console_handler)
        logger.warning("No logging handlers configured, using stdout fallback")
    
    # Log configuration info
    logger.info(f"Universal logging initialized - Mode: {config['mode']}, Level: {config['level']}, Render: {config['is_render']}")
    
    return logger, log_filename

def setup_automated_collector_logging() -> tuple[logging.Logger, Optional[str]]:
    """
    Setup logging specifically for the automated collector
    
    Returns:
        Tuple of (logger, log_filename_or_None)
    """
    return setup_universal_logging(
        logger_name='automated_collector',
        base_filename='automated_collector'
    )

def setup_web_scraper_logging() -> tuple[logging.Logger, Optional[str]]:
    """
    Setup logging specifically for web scraper
    
    Returns:
        Tuple of (logger, log_filename_or_None)
    """
    return setup_universal_logging(
        logger_name='web_scraper',
        base_filename='web_scraper'
    )

def setup_database_logging() -> tuple[logging.Logger, Optional[str]]:
    """
    Setup logging specifically for database operations
    
    Returns:
        Tuple of (logger, log_filename_or_None)
    """
    return setup_universal_logging(
        logger_name='database',
        base_filename='database'
    )

def get_logger_for_module(module_name: str) -> logging.Logger:
    """
    Get a logger for a specific module with universal configuration
    
    Args:
        module_name: Name of the module (typically __name__)
        
    Returns:
        Configured logger
    """
    # If root logger hasn't been configured yet, set it up
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        setup_universal_logging()
    
    return logging.getLogger(module_name)

def log_environment_info(logger: logging.Logger):
    """
    Log relevant environment information for debugging
    
    Args:
        logger: Logger to use for output
    """
    config = get_logging_config()
    
    logger.info("=== ENVIRONMENT INFORMATION ===")
    logger.info(f"Render Deployment: {config['is_render']}")
    logger.info(f"Logging Mode: {config['mode']}")
    logger.info(f"Log Level: {config['level']}")
    logger.info(f"File Logging: {config['enable_file_logging']}")
    logger.info(f"Console Logging: {config['enable_console_logging']}")
    
    # Log relevant environment variables (without sensitive data)
    env_vars = ['DATABASE_TYPE', 'RENDER', 'RENDER_SERVICE_ID', 'PORT', 'PYTHON_VERSION']
    for var in env_vars:
        value = os.getenv(var, 'Not set')
        logger.info(f"ENV {var}: {value}")
    
    logger.info("=== END ENVIRONMENT INFO ===")

# Environment variable documentation
RENDER_LOGGING_DOCS = """
# Render.com Environment Variables for Logging

# Logging configuration (render.com automatically detects stdout):
LOGGING_MODE=stdout
LOG_LEVEL=INFO
ENABLE_FILE_LOGGING=false
ENABLE_CONSOLE_LOGGING=true

# Optional: Override default behavior
# LOG_FORMAT=simple
"""

LOCAL_LOGGING_DOCS = """
# Local Development Environment Variables for Logging

# File-based logging for local development:
LOGGING_MODE=file
LOG_LEVEL=INFO
ENABLE_FILE_LOGGING=true
ENABLE_CONSOLE_LOGGING=true

# Optional customizations:
# LOG_DIRECTORY=logs
# LOG_FORMAT=detailed
"""

if __name__ == "__main__":
    # Test universal logging
    print("Testing Universal Logging Configuration...")
    
    # Test different configurations
    logger, log_file = setup_universal_logging("test_logger", "test")
    
    # Log environment info
    log_environment_info(logger)
    
    # Test different log levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Test with exception
    try:
        raise ValueError("Test exception")
    except Exception as e:
        logger.exception("Exception occurred during testing")
    
    print(f"Log file: {log_file}")
    print("Universal logging test completed!")
