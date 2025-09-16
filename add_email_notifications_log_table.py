#!/usr/bin/env python3
"""
Add email_notifications_log table for tracking email notifications

This table is needed by the email notification system to log sent emails
and prevent errors during email sending.

Author: AI Assistant
Date: 2025-09-15
"""

import os
import sys
import logging

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager

logger = logging.getLogger(__name__)

def add_email_notifications_log_table():
    """Add email_notifications_log table if it doesn't exist"""
    try:
        db_manager = get_universal_database_manager()
        
        # Check if table already exists
        if db_manager.adapter.table_exists('email_notifications_log'):
            logger.info("email_notifications_log table already exists")
            return True
        
        logger.info("Creating email_notifications_log table...")
        
        # Create email_notifications_log table
        create_sql = """
        CREATE TABLE IF NOT EXISTS email_notifications_log (
            id SERIAL PRIMARY KEY,
            notification_date DATE NOT NULL,
            notification_type TEXT NOT NULL CHECK (notification_type IN (
                'sensor_change',
                'daily_summary', 
                'status_changes',
                'comprehensive_status',
                'email_test',
                'comprehensive_test',
                'daily_usage_analytics'
            )),
            trigger_event TEXT NOT NULL,
            recipients TEXT NOT NULL,
            subject TEXT NOT NULL,
            body_preview TEXT,
            affected_zones TEXT,
            sensor_status_changed BOOLEAN DEFAULT FALSE,
            runs_affected_count INTEGER DEFAULT 0,
            email_sent BOOLEAN DEFAULT FALSE,
            sent_at TIMESTAMP,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        # Adjust for SQLite vs PostgreSQL
        if db_manager.config.db_type == 'sqlite':
            create_sql = create_sql.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
        
        db_manager.adapter.execute_script(create_sql)
        
        logger.info("email_notifications_log table created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating email_notifications_log table: {e}")
        return False

def main():
    """Main function"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Adding email_notifications_log table...")
    
    success = add_email_notifications_log_table()
    
    if success:
        logger.info("Migration completed successfully")
        return 0
    else:
        logger.error("Migration failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

