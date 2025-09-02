#!/usr/bin/env python3
"""
Example configuration for Hydrawise Irrigation Tracking System

This file shows how to configure email notifications and tracking settings.
Copy this file to tracking_config.py and customize for your setup.

Author: AI Assistant
Date: 2025-08-26
"""

# Email Configuration Example
EMAIL_CONFIG = {
    "email_notifications_enabled": True,
    "notification_recipients": [
        "your.email@gmail.com",
        "other.user@gmail.com"
    ],
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "your.email@gmail.com",  
    "smtp_password": "your_app_password_here",  # Use Gmail App Password, not regular password
    "smtp_from_address": "your.email@gmail.com"
}

# Tracking Configuration Example  
TRACKING_CONFIG = {
    "track_sensor_status": True,           # Monitor rain sensor changes
    "track_status_changes": True,          # Monitor popup status changes
    "email_notifications_enabled": True,   # Send email alerts
    "notification_recipients": EMAIL_CONFIG["notification_recipients"],
    **EMAIL_CONFIG
}

# Basic Configuration (No Email)
BASIC_CONFIG = {
    "track_sensor_status": True,
    "track_status_changes": True,
    "email_notifications_enabled": False
}

# Gmail App Password Setup Instructions:
"""
1. Go to your Google Account settings
2. Enable 2-Factor Authentication if not already enabled
3. Go to Security > 2-Step Verification > App passwords
4. Generate an app password for "Mail"
5. Use this 16-character password in smtp_password field above
6. DO NOT use your regular Gmail password
"""

# Test Configuration (for development)
TEST_CONFIG = {
    "track_sensor_status": False,          # Disable sensor tracking during testing
    "track_status_changes": True,          # Enable status change tracking
    "email_notifications_enabled": False   # Disable emails during testing
}


