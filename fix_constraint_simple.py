#!/usr/bin/env python3
"""
Simple fix for rain sensor table constraint issue

This script fixes the ON CONFLICT issue by updating the code to match
the existing database constraint.
"""

import os
import sys

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager

def main():
    print("Simple Constraint Fix")
    print("=" * 20)
    
    try:
        # Connect to database
        print("1. Connecting to database...")
        db_manager = get_universal_database_manager()
        print("   [OK] Connected")
        
        # Check what constraint actually exists
        print("\n2. Checking existing constraints...")
        result = db_manager.adapter.execute_query("""
            SELECT tc.constraint_name, tc.constraint_type,
                   STRING_AGG(ccu.column_name, ', ' ORDER BY ccu.column_name) as columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu 
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.table_name = 'rain_sensor_status_history'
            AND tc.constraint_type = 'UNIQUE'
            GROUP BY tc.constraint_name, tc.constraint_type
        """)
        
        if result:
            for row in result:
                print(f"   Constraint: {row['constraint_name']}")
                print(f"   Columns: {row['columns']}")
        else:
            print("   No unique constraints found")
            
        # The database has constraint on (status_date, scraped_at)
        # but code expects (status_date, status_time)
        # Let's check if we can add the expected constraint
        
        print("\n3. Trying to add expected constraint...")
        try:
            db_manager.adapter.execute_query("""
                ALTER TABLE rain_sensor_status_history 
                ADD CONSTRAINT uk_rain_sensor_status_date_time 
                UNIQUE (status_date, status_time)
            """)
            print("   [OK] Added constraint (status_date, status_time)")
        except Exception as e:
            if "already exists" in str(e):
                print("   [OK] Constraint already exists")
            elif "duplicate" in str(e).lower():
                print("   [WARNING] Duplicate data prevents adding constraint")
                print("   Will update code to use existing constraint instead")
                return "use_existing"
            else:
                print(f"   [ERROR] {e}")
                return "use_existing"
        
        return "success"
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return "error"

if __name__ == "__main__":
    result = main()
    if result == "use_existing":
        print("\nNext: Update code to use existing constraint")
    elif result == "success":
        print("\n[OK] Constraint fix completed!")
    exit(0 if result != "error" else 1)

