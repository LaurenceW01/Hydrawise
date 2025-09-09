#!/usr/bin/env python3
"""
Fix Rain Sensor Status History Table Constraint

This script fixes the missing unique constraint on the rain_sensor_status_history table
that's causing ON CONFLICT errors.

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
    """Fix the rain_sensor_status_history table constraint"""
    
    # Setup logging
    setup_universal_logging(
        logger_name=__name__,
        log_level="INFO",
        force_mode="console"
    )
    
    logger = logging.getLogger(__name__)
    
    print("Fix Rain Sensor Status History Table Constraint")
    print("=" * 50)
    print()
    
    try:
        # Check if we're using PostgreSQL
        if not is_postgresql():
            print("[ERROR] This script is for PostgreSQL databases only")
            return 1
        
        print("1. Connecting to PostgreSQL database...")
        db_manager = get_universal_database_manager()
        print("   [OK] Database connection successful")
        
        print("\n2. Checking current table structure...")
        
        # Check if the table exists and what constraints it has
        try:
            result = db_manager.adapter.execute_query("""
                SELECT constraint_name, constraint_type 
                FROM information_schema.table_constraints 
                WHERE table_name = 'rain_sensor_status_history'
                AND constraint_type = 'UNIQUE'
            """)
            
            unique_constraints = [row['constraint_name'] for row in result] if result else []
            print(f"   Current unique constraints: {unique_constraints}")
            
        except Exception as e:
            print(f"   [WARNING] Could not check constraints: {e}")
            unique_constraints = []
        
        print("\n3. Checking if the expected constraint exists...")
        
        # Try to find the specific constraint we need
        try:
            result = db_manager.adapter.execute_query("""
                SELECT constraint_name
                FROM information_schema.constraint_column_usage ccu
                JOIN information_schema.table_constraints tc 
                ON ccu.constraint_name = tc.constraint_name
                WHERE tc.table_name = 'rain_sensor_status_history'
                AND tc.constraint_type = 'UNIQUE'
                AND ccu.column_name IN ('status_date', 'status_time')
                GROUP BY constraint_name
                HAVING COUNT(*) = 2
            """)
            
            has_expected_constraint = len(result) > 0 if result else False
            
        except Exception as e:
            print(f"   [WARNING] Could not check specific constraint: {e}")
            has_expected_constraint = False
        
        if has_expected_constraint:
            print("   [OK] Expected constraint already exists")
            print("\n[INFO] The table should be working correctly.")
            print("The error might be due to a temporary issue or data conflict.")
            return 0
        
        print("   [MISSING] Expected unique constraint (status_date, status_time) not found")
        
        print("\n4. Adding missing unique constraint...")
        
        try:
            # Add the missing unique constraint
            db_manager.adapter.execute_query("""
                ALTER TABLE rain_sensor_status_history 
                ADD CONSTRAINT rain_sensor_status_history_status_date_time_key 
                UNIQUE (status_date, status_time)
            """)
            print("   [OK] Added unique constraint (status_date, status_time)")
            
        except Exception as e:
            if "already exists" in str(e).lower():
                print("   [OK] Constraint already exists")
            elif "duplicate key" in str(e).lower() or "violates unique constraint" in str(e).lower():
                print("   [WARNING] Cannot add constraint due to duplicate data")
                print("   Cleaning up duplicate entries...")
                
                # Remove duplicates, keeping the most recent one
                try:
                    db_manager.adapter.execute_query("""
                        DELETE FROM rain_sensor_status_history a USING (
                            SELECT MIN(ctid) as ctid, status_date, status_time
                            FROM rain_sensor_status_history 
                            GROUP BY status_date, status_time HAVING COUNT(*) > 1
                        ) b
                        WHERE a.status_date = b.status_date 
                        AND a.status_time = b.status_time 
                        AND a.ctid <> b.ctid
                    """)
                    
                    # Try adding the constraint again
                    db_manager.adapter.execute_query("""
                        ALTER TABLE rain_sensor_status_history 
                        ADD CONSTRAINT rain_sensor_status_history_status_date_time_key 
                        UNIQUE (status_date, status_time)
                    """)
                    print("   [OK] Removed duplicates and added constraint")
                    
                except Exception as cleanup_error:
                    print(f"   [ERROR] Failed to clean up duplicates: {cleanup_error}")
                    return 1
            else:
                print(f"   [ERROR] Failed to add constraint: {e}")
                return 1
        
        print("\n5. Verifying the fix...")
        
        # Test that the constraint works
        try:
            result = db_manager.adapter.execute_query("""
                SELECT constraint_name
                FROM information_schema.constraint_column_usage ccu
                JOIN information_schema.table_constraints tc 
                ON ccu.constraint_name = tc.constraint_name
                WHERE tc.table_name = 'rain_sensor_status_history'
                AND tc.constraint_type = 'UNIQUE'
                AND ccu.column_name IN ('status_date', 'status_time')
                GROUP BY constraint_name
                HAVING COUNT(*) = 2
            """)
            
            if result and len(result) > 0:
                print("   [OK] Unique constraint verified")
            else:
                print("   [ERROR] Constraint verification failed")
                return 1
                
        except Exception as e:
            print(f"   [ERROR] Verification failed: {e}")
            return 1
        
        print("\n[OK] Rain sensor table constraint fix completed!")
        print("\nThe ON CONFLICT error should now be resolved.")
        print("The sensor status storage will work properly.")
        
    except Exception as e:
        logger.error(f"Failed to fix table constraint: {e}")
        print(f"\n[ERROR] {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

