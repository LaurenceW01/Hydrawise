#!/usr/bin/env python3
"""
Integration helper for adding tracking to existing automated collector

Provides minimal integration points to add tracking functionality
to the existing automated collector without major modifications.

Author: AI Assistant
Date: 2025-08-26
"""

import os
import sys
import logging
from datetime import date
from typing import Dict, Any, Optional

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

def _load_env_bool(key: str, default: bool = False) -> bool:
    """Load boolean value from environment variable"""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

def _load_env_int(key: str, default: int) -> int:
    """Load integer value from environment variable"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def _load_env_list(key: str, default: list = None) -> list:
    """Load comma-separated list from environment variable"""
    value = os.getenv(key, '')
    if not value.strip():
        return default or []
    return [item.strip() for item in value.split(',') if item.strip()]

def load_config_from_env() -> Dict[str, Any]:
    """
    Load tracking configuration from environment variables
    
    Loads from .env file if present, otherwise uses system environment variables
    
    Returns:
        Configuration dictionary for tracking system
    """
    # Try to load from .env file if it exists
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_file):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            logger.info("[CONFIG] Loaded configuration from .env file")
        except ImportError:
            logger.info("[CONFIG] python-dotenv not installed, using system environment variables")
        except Exception as e:
            logger.warning(f"[CONFIG] Error loading .env file: {e}, using system environment variables")
    
    # Load configuration from environment variables
    config = {
        # Core tracking settings
        "track_sensor_status": _load_env_bool("TRACK_SENSOR_STATUS", True),
        "track_status_changes": _load_env_bool("TRACK_STATUS_CHANGES", True),
        
        # Email configuration
        "email_notifications_enabled": _load_env_bool("EMAIL_NOTIFICATIONS_ENABLED", False),
        "notification_recipients": _load_env_list("EMAIL_RECIPIENTS", []),
        "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": _load_env_int("SMTP_PORT", 587),
        "smtp_username": os.getenv("SMTP_USERNAME", ""),
        "smtp_password": os.getenv("SMTP_PASSWORD", ""),
        "smtp_from_address": os.getenv("SMTP_FROM_ADDRESS", ""),
        
        # Email timing and limits
        "daily_summary_time": os.getenv("DAILY_EMAIL_TIME", "19:00"),
        "max_emails_per_day": _load_env_int("MAX_EMAILS_PER_DAY", 1),
        
        # Advanced settings
        "db_path": os.getenv("DB_PATH", "database/irrigation_data.db"),
        "headless_mode": _load_env_bool("HEADLESS_MODE", True),
        
        # Notification types
        "sensor_change_notifications": _load_env_bool("SENSOR_CHANGE_NOTIFICATIONS", True),
        "status_change_notifications": _load_env_bool("STATUS_CHANGE_NOTIFICATIONS", True),
        "daily_summary_notifications": _load_env_bool("DAILY_SUMMARY_NOTIFICATIONS", True)
    }
    
    # Validate email configuration
    if config["email_notifications_enabled"]:
        if not config["notification_recipients"]:
            logger.warning("[CONFIG] Email notifications enabled but no recipients configured")
            config["email_notifications_enabled"] = False
        elif not config["smtp_username"] or not config["smtp_password"]:
            logger.warning("[CONFIG] Email notifications enabled but SMTP credentials not configured")
            config["email_notifications_enabled"] = False
        else:
            logger.info(f"[CONFIG] Email notifications enabled for {len(config['notification_recipients'])} recipients")
    
    # Set default from_address if not provided
    if not config["smtp_from_address"] and config["smtp_username"]:
        config["smtp_from_address"] = config["smtp_username"]
    
    logger.info(f"[CONFIG] Tracking configuration loaded: sensor={config['track_sensor_status']}, status_changes={config['track_status_changes']}, email={config['email_notifications_enabled']}")
    
    return config

# Global tracking system instance
_tracking_system = None

def initialize_tracking(config_dict: Dict[str, Any] = None) -> bool:
    """
    Initialize the tracking system with configuration
    
    Args:
        config_dict: Configuration dictionary with tracking settings.
                    If None, loads from environment variables.
        
    Returns:
        True if initialization successful, False otherwise
    """
    global _tracking_system
    
    try:
        from irrigation_tracking_system import IrrigationTrackingSystem, TrackingConfig
        
        # Load config from environment variables if not provided
        if config_dict is None:
            config_dict = load_config_from_env()
        
        # Create config from dictionary
        config = TrackingConfig(**config_dict)
        
        _tracking_system = IrrigationTrackingSystem(config)
        logger.info("[TRACKING] Irrigation tracking system initialized from environment configuration")
        return True
        
    except Exception as e:
        logger.error(f"[TRACKING] Failed to initialize tracking system: {e}")
        return False

def add_tracking_to_collection(target_date: date, collection_type: str = "unknown") -> Dict[str, Any]:
    """
    Add tracking to a collection process
    
    This function should be called AFTER the standard collection process
    to add tracking capabilities.
    
    Args:
        target_date: Date being collected
        collection_type: Type of collection (startup, daily, interval)
        
    Returns:
        Dictionary with tracking results
    """
    if _tracking_system is None:
        logger.debug("[TRACKING] Tracking system not initialized, skipping tracking")
        return {"tracking_enabled": False}
    
    try:
        from irrigation_tracking_system import integrate_tracking_with_collection
        
        results = integrate_tracking_with_collection(_tracking_system, target_date, collection_type)
        
        # Log results
        if results.get("status_changes_detected", 0) > 0:
            logger.warning(f"[TRACKING] {results['status_changes_detected']} status changes detected for {target_date}")
        
        if results.get("sensor_status", {}).get("irrigation_suspended", False):
            logger.warning(f"[TRACKING] Rain sensor is stopping irrigation: {results['sensor_status']['sensor_status']}")
        
        if results.get("email_sent", False):
            logger.info(f"[TRACKING] Daily notification email sent for {target_date}")
        
        return results
        
    except Exception as e:
        logger.error(f"[TRACKING] Error in collection tracking: {e}")
        return {"tracking_enabled": True, "error": str(e)}

def get_tracking_status() -> Dict[str, Any]:
    """
    Get current tracking system status
    
    Returns:
        Dictionary with tracking system status
    """
    if _tracking_system is None:
        return {"tracking_initialized": False}
    
    try:
        status = _tracking_system.get_tracking_status()
        status["tracking_initialized"] = True
        return status
    except Exception as e:
        logger.error(f"[TRACKING] Error getting tracking status: {e}")
        return {"tracking_initialized": True, "error": str(e)}

def is_tracking_enabled() -> bool:
    """Check if tracking system is initialized and enabled"""
    return _tracking_system is not None

# Configuration helper functions

def create_email_config(recipients: list, smtp_username: str, smtp_password: str, 
                       smtp_server: str = "smtp.gmail.com", smtp_port: int = 587) -> Dict[str, Any]:
    """
    Create email configuration dictionary
    
    Args:
        recipients: List of email addresses
        smtp_username: SMTP username  
        smtp_password: SMTP password (app password recommended)
        smtp_server: SMTP server (default: gmail)
        smtp_port: SMTP port (default: 587)
        
    Returns:
        Configuration dictionary for email notifications
    """
    return {
        "email_notifications_enabled": True,
        "notification_recipients": recipients,
        "smtp_server": smtp_server,
        "smtp_port": smtp_port,
        "smtp_username": smtp_username,
        "smtp_password": smtp_password,
        "smtp_from_address": smtp_username
    }

def create_basic_config(enable_tracking: bool = True, enable_emails: bool = False) -> Dict[str, Any]:
    """
    Create basic tracking configuration
    
    Args:
        enable_tracking: Enable status change tracking
        enable_emails: Enable email notifications
        
    Returns:
        Basic configuration dictionary
    """
    return {
        "track_sensor_status": enable_tracking,
        "track_status_changes": enable_tracking,
        "email_notifications_enabled": enable_emails
    }

def create_full_config(recipients: list = None, smtp_username: str = "", smtp_password: str = "",
                      enable_all: bool = True) -> Dict[str, Any]:
    """
    Create comprehensive tracking configuration
    
    Args:
        recipients: Email recipients (empty list if None)
        smtp_username: SMTP username
        smtp_password: SMTP password
        enable_all: Enable all tracking features
        
    Returns:
        Full configuration dictionary
    """
    config = {
        "track_sensor_status": enable_all,
        "track_status_changes": enable_all,
        "email_notifications_enabled": enable_all and bool(recipients and smtp_username and smtp_password),
        "notification_recipients": recipients or [],
        "smtp_username": smtp_username,
        "smtp_password": smtp_password,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_from_address": smtp_username
    }
    
    return config
