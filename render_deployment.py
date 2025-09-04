#!/usr/bin/env python3
"""
Render.com Deployment Entry Point for Hydrawise Automated Collection

This script serves as the main entry point for the Hydrawise automated collection
system when deployed on render.com. It configures the environment for cloud
deployment and starts the automated collector.

Features:
- Configures PostgreSQL database connection
- Sets up stdout logging for render.com
- Handles environment variable configuration
- Provides health check endpoint for render.com monitoring
- Graceful shutdown handling

Author: AI Assistant
Date: 2025-01-27
"""

import os
import sys
import signal
import time
import threading
from datetime import datetime
from typing import Optional

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import universal systems
from utils.universal_logging import setup_universal_logging, log_environment_info
from database.universal_database_manager import get_universal_database_manager
from database.db_config import validate_database_config

# Import the automated collector
from automated_collector import AutomatedCollector, ScheduleConfig

# Global variables for graceful shutdown
collector_instance: Optional[AutomatedCollector] = None
shutdown_event = threading.Event()

def setup_render_environment():
    """
    Setup environment variables and configuration for render.com deployment
    """
    # Set default environment variables for render.com
    render_defaults = {
        'DATABASE_TYPE': 'postgresql',  # render.com provides PostgreSQL
        'LOGGING_MODE': 'stdout',       # render.com captures stdout
        'ENABLE_FILE_LOGGING': 'false', # No persistent file system
        'ENABLE_CONSOLE_LOGGING': 'true',
        'LOG_LEVEL': 'INFO',
        'HEADLESS_MODE': 'true',        # Always run browsers in headless mode
        'TZ': 'America/Chicago',        # Houston timezone [[memory:7198787]]
    }
    
    # Set defaults only if not already set
    for key, value in render_defaults.items():
        if key not in os.environ:
            os.environ[key] = value

def validate_render_environment(logger) -> bool:
    """
    Validate that all required environment variables are set for render.com
    
    Args:
        logger: Logger instance for output
        
    Returns:
        True if environment is valid, False otherwise
    """
    required_vars = [
        'DATABASE_URL',  # Provided by render.com PostgreSQL service
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Make sure you have added a PostgreSQL database service in render.com")
        return False
    
    # Validate database connection
    if not validate_database_config():
        logger.error("Database configuration validation failed")
        return False
    
    logger.info("Render.com environment validation passed")
    return True

def create_render_schedule_config() -> ScheduleConfig:
    """
    Create schedule configuration optimized for render.com deployment
    
    Returns:
        ScheduleConfig configured for cloud deployment
    """
    # Get configuration from environment variables with render.com optimized defaults
    config = ScheduleConfig(
        # Collection timing [[memory:7198787]]
        daily_collection_time=datetime.strptime(
            os.getenv('DAILY_COLLECTION_TIME', '06:00'), '%H:%M'
        ).time(),
        hourly_interval_minutes=int(os.getenv('HOURLY_INTERVAL_MINUTES', '60')),
        
        # Active hours (Houston time)
        active_start_time=datetime.strptime(
            os.getenv('ACTIVE_START_TIME', '06:00'), '%H:%M'
        ).time(),
        active_end_time=datetime.strptime(
            os.getenv('ACTIVE_END_TIME', '20:00'), '%H:%M'
        ).time(),
        
        # Collection options
        enabled=os.getenv('COLLECTION_ENABLED', 'true').lower() == 'true',
        collect_schedules=os.getenv('COLLECT_SCHEDULES', 'true').lower() == 'true',
        collect_reported_runs=os.getenv('COLLECT_REPORTED_RUNS', 'true').lower() == 'true',
        collect_yesterday_on_startup=os.getenv('COLLECT_YESTERDAY_ON_STARTUP', 'true').lower() == 'true',
        smart_startup_check=os.getenv('SMART_STARTUP_CHECK', 'true').lower() == 'true',
        
        # Always headless on render.com
        headless_mode=True
    )
    
    return config

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger = logging.getLogger('render_deployment')
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    
    shutdown_event.set()
    
    if collector_instance:
        logger.info("Stopping automated collector...")
        collector_instance.stop()
    
    logger.info("Graceful shutdown completed")
    sys.exit(0)

def health_check_server():
    """
    Simple health check server for render.com monitoring
    Runs in a separate thread to provide health status
    """
    import socket
    import json
    import logging
    from datetime import datetime
    
    logger = logging.getLogger('health_check')
    port = int(os.getenv('PORT', 8080))  # render.com provides PORT env var
    
    try:
        # Create simple HTTP server for health checks
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', port))
        server_socket.listen(1)
        server_socket.settimeout(1.0)  # Non-blocking with timeout
        
        logger.info(f"Health check server listening on port {port}")
        
        while not shutdown_event.is_set():
            try:
                client_socket, address = server_socket.accept()
                
                # Simple HTTP response with health status
                health_status = {
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat(),
                    'collector_running': collector_instance.running if collector_instance else False,
                    'database_type': os.getenv('DATABASE_TYPE', 'unknown')
                }
                
                response_body = json.dumps(health_status)
                response = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(response_body)}\r\n"
                    f"\r\n"
                    f"{response_body}"
                )
                
                client_socket.send(response.encode())
                client_socket.close()
                
            except socket.timeout:
                continue  # Check shutdown_event
            except Exception as e:
                logger.warning(f"Health check request failed: {e}")
        
        server_socket.close()
        logger.info("Health check server stopped")
        
    except Exception as e:
        logger.error(f"Health check server failed to start: {e}")

def main():
    """
    Main entry point for render.com deployment
    """
    global collector_instance
    
    # Set Chrome binary path for Selenium (render.com specific)
    chrome_path = "/opt/render/project/.render/chrome/opt/google/chrome/chrome"
    os.environ['CHROME_BIN'] = chrome_path
    
    # Setup render.com environment
    setup_render_environment()
    
    # Setup universal logging for render.com
    logger, log_file = setup_universal_logging('render_deployment', 'render_deployment')
    
    # Log environment information
    logger.info("=== HYDRAWISE AUTOMATED COLLECTOR - RENDER.COM DEPLOYMENT ===")
    log_environment_info(logger)
    
    # Validate environment
    if not validate_render_environment(logger):
        logger.error("Environment validation failed, exiting")
        sys.exit(1)
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Test database connection
        logger.info("Testing database connection...")
        with get_universal_database_manager() as db:
            zones = db.get_zones()
            logger.info(f"Database connection successful - {len(zones)} zones configured")
        
        # Create schedule configuration
        schedule_config = create_render_schedule_config()
        logger.info(f"Schedule configuration created - Collection enabled: {schedule_config.enabled}")
        
        # Start health check server in separate thread
        health_thread = threading.Thread(target=health_check_server, daemon=True)
        health_thread.start()
        logger.info("Health check server started")
        
        # Create and start automated collector
        logger.info("Starting automated collector...")
        collector_instance = AutomatedCollector(schedule_config)
        collector_instance.start()
        
        logger.info("Automated collector started successfully")
        logger.info("Service is now running - monitoring for shutdown signals...")
        
        # Keep the main thread alive
        while not shutdown_event.is_set():
            time.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        if collector_instance:
            logger.info("Stopping collector...")
            collector_instance.stop()
        
        logger.info("Render.com deployment shutdown complete")

if __name__ == "__main__":
    main()
