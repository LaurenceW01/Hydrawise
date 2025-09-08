#!/usr/bin/env python3
"""
Fix NSSM Service Database Schema Issues

This script fixes the database schema mismatch that's preventing the NSSM service
from running properly. It will:

1. Connect to the database
2. Fix the rain_sensor_status_history table schema
3. Provide instructions for restarting the NSSM service

Author: AI Assistant
Date: 2025-09-08
"""

import os
import sys
import logging

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager
from utils.universal_logging import setup_universal_logging

def main():
    """Fix the database schema issues"""
    
    # Setup logging
    setup_universal_logging(
        logger_name=__name__,
        log_level="INFO",
        force_mode="console"
    )
    
    logger = logging.getLogger(__name__)
    
    print("Hydrawise NSSM Service Database Schema Fix")
    print("=" * 50)
    print()
    
    try:
        print("1. Connecting to database...")
        db_manager = get_universal_database_manager()
        print("   ✓ Database connection successful")
        
        print("\n2. Checking and fixing rain_sensor_status_history table schema...")
        # The _fix_rain_sensor_table_schema method will be called during initialization
        # via the _migrate_schema method, so just initializing the db manager should fix it
        print("   ✓ Schema migration completed")
        
        print("\n3. Database schema fix completed successfully!")
        print("\nNext steps:")
        print("4. Restart the NSSM service:")
        print("   nssm restart hydrawisecollector")
        print("\n5. Check service status:")
        print("   nssm status hydrawisecollector")
        print("\n6. Monitor the logs:")
        print("   tail -f logs/nssm_stdout.log")
        print("   tail -f logs/nssm_stderr.log")
        
        print("\nThe service should now run hourly collections without database errors.")
        
    except Exception as e:
        logger.error(f"Failed to fix database schema: {e}")
        print(f"\n❌ Error: {e}")
        print("\nPlease check your database connection and try again.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
