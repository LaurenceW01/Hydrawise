#!/usr/bin/env python3
"""
Add system_config table for storing system-wide configuration values

This table is needed for the daily usage analytics report system
to track progressive day window expansion.

Author: AI Assistant
Date: 2025-09-15
"""

import os
import sys
import logging

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager
# Removed universal_logging import - using basic logging instead

logger = logging.getLogger(__name__)

def add_system_config_table():
    """Add system_config table if it doesn't exist"""
    try:
        db_manager = get_universal_database_manager()
        
        # Check if table already exists
        if db_manager.adapter.table_exists('system_config'):
            logger.info("system_config table already exists")
            return True
        
        logger.info("Creating system_config table...")
        
        # Create system_config table
        create_sql = """
        CREATE TABLE IF NOT EXISTS system_config (
            id SERIAL PRIMARY KEY,
            config_key TEXT NOT NULL UNIQUE,
            config_value TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        # Adjust for SQLite vs PostgreSQL
        if db_manager.config.db_type == 'sqlite':
            create_sql = create_sql.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
        
        db_manager.adapter.execute_script(create_sql)
        
        logger.info("system_config table created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating system_config table: {e}")
        return False

def main():
    """Main function"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Adding system_config table...")
    
    success = add_system_config_table()
    
    if success:
        logger.info("Migration completed successfully")
        return 0
    else:
        logger.error("Migration failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
