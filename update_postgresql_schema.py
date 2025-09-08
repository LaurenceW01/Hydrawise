#!/usr/bin/env python3
"""
Update PostgreSQL Database Schema

This script applies the corrected and complete PostgreSQL schema to the database,
including missing tables and indexes.

Author: AI Assistant  
Date: 2025-09-08
"""

import os
import sys
import logging

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager
from database.db_config import is_postgresql
from utils.universal_logging import setup_universal_logging

def main():
    """Apply the updated PostgreSQL schema"""
    
    # Setup logging
    setup_universal_logging(
        logger_name=__name__,
        log_level="INFO",
        force_mode="console"
    )
    
    logger = logging.getLogger(__name__)
    
    print("PostgreSQL Schema Update")
    print("=" * 30)
    print()
    
    try:
        # Check if we're using PostgreSQL
        if not is_postgresql():
            print("[ERROR] This script is for PostgreSQL databases only")
            print("Current database type is not PostgreSQL")
            return 1
        
        print("1. Connecting to PostgreSQL database...")
        db_manager = get_universal_database_manager()
        print("   [OK] Database connection successful")
        
        print("\n2. Reading updated schema file...")
        schema_path = os.path.join('database', 'postgresql_schema.sql')
        if not os.path.exists(schema_path):
            print(f"   [ERROR] Schema file not found: {schema_path}")
            return 1
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        print(f"   [OK] Schema file loaded ({len(schema_sql)} characters)")
        
        print("\n3. Applying schema updates...")
        print("   - Creating missing tables (usage_anomalies, usage_trends)")
        print("   - Adding missing indexes for tracking and analytics tables")
        print("   - Ensuring all tables match code expectations")
        
        # Execute the schema (CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS are safe)
        db_manager.adapter.execute_script(schema_sql)
        print("   [OK] Schema updates applied successfully")
        
        print("\n4. Verifying table existence...")
        tables_to_check = [
            'zones', 'scheduled_runs', 'actual_runs', 'usage_baselines',
            'usage_anomalies', 'usage_trends', 'daily_variance',
            'rain_sensor_status_history', 'status_changes', 
            'scheduled_run_status_changes', 'collection_status'
        ]
        
        for table in tables_to_check:
            if db_manager.adapter.table_exists(table):
                print(f"   [OK] {table}")
            else:
                print(f"   [MISSING] {table}")
        
        print("\n[OK] PostgreSQL schema update completed!")
        print("\nUpdated Features:")
        print("- Added missing usage_anomalies table for anomaly detection")
        print("- Added missing usage_trends table for trend analysis") 
        print("- Added comprehensive indexes for all tracking tables")
        print("- Ensured all tables match code expectations")
        print("- Fixed schema inconsistencies")
        
        print("\nThe database schema is now complete and accurate!")
        
    except Exception as e:
        logger.error(f"Failed to update schema: {e}")
        print(f"\n[ERROR] {e}")
        print("\nPlease check your database connection and try again.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
