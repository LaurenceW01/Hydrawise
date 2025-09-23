#!/usr/bin/env python3
"""
Fix Events Table Constraints and Indexes

This script manually renames any remaining failure_events constraints 
and indexes to use the events table name.

Author: AI Assistant
Date: 2025-01-27
"""

import sys
import os
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager
from database.db_config import is_postgresql

def get_failure_events_constraints_and_indexes() -> List[Dict[str, str]]:
    """Get all constraints and indexes that still reference failure_events"""
    db_manager = get_universal_database_manager()
    
    if is_postgresql():
        # Query for constraints
        constraint_query = """
        SELECT 
            conname as name,
            'constraint' as type,
            contype as constraint_type
        FROM pg_constraint 
        WHERE conname LIKE '%failure_events%'
        
        UNION ALL
        
        SELECT 
            indexname as name,
            'index' as type,
            'index' as constraint_type
        FROM pg_indexes 
        WHERE indexname LIKE '%failure_events%'
        AND schemaname = 'public'
        """
        
        results = db_manager.adapter.execute_query(constraint_query)
        return results if results else []
    else:
        # SQLite - check sqlite_master
        sqlite_query = """
        SELECT 
            name,
            type,
            sql
        FROM sqlite_master 
        WHERE name LIKE '%failure_events%'
        AND type IN ('index', 'trigger')
        """
        
        results = db_manager.adapter.execute_query(sqlite_query)
        return results if results else []

def rename_constraints_and_indexes():
    """Rename all failure_events constraints and indexes to events"""
    print("Checking for failure_events constraints and indexes...")
    
    db_manager = get_universal_database_manager()
    items = get_failure_events_constraints_and_indexes()
    
    if not items:
        print("✓ No failure_events constraints or indexes found")
        return True
    
    print(f"Found {len(items)} items to rename:")
    for item in items:
        print(f"  - {item['name']} ({item['type']})")
    
    success_count = 0
    error_count = 0
    
    for item in items:
        old_name = item['name']
        new_name = old_name.replace('failure_events', 'events')
        item_type = item['type']
        
        try:
            if item_type == 'constraint':
                # Rename constraint
                sql = f"ALTER TABLE events RENAME CONSTRAINT {old_name} TO {new_name}"
            elif item_type == 'index':
                # Rename index
                sql = f"ALTER INDEX {old_name} RENAME TO {new_name}"
            else:
                print(f"⚠️  Unknown item type '{item_type}' for {old_name}")
                continue
            
            print(f"Renaming {old_name} to {new_name}...")
            db_manager.adapter.execute_update(sql)
            print(f"✓ Successfully renamed {old_name}")
            success_count += 1
            
        except Exception as e:
            print(f"❌ Failed to rename {old_name}: {e}")
            error_count += 1
    
    print(f"\nResults: {success_count} successful, {error_count} errors")
    return error_count == 0

def verify_events_table():
    """Verify the events table exists and has correct structure"""
    print("\nVerifying events table...")
    
    db_manager = get_universal_database_manager()
    
    try:
        # Check table exists
        if is_postgresql():
            exists_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'events'
            )
            """
        else:
            exists_query = "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        
        result = db_manager.adapter.execute_query(exists_query)
        table_exists = bool(result and (
            result[0].get('exists', False) if is_postgresql() 
            else len(result) > 0
        ))
        
        if not table_exists:
            print("❌ Events table does not exist")
            return False
        
        print("✓ Events table exists")
        
        # Count records
        count_result = db_manager.adapter.execute_query("SELECT COUNT(*) as count FROM events")
        record_count = count_result[0]['count'] if count_result else 0
        print(f"✓ Events table has {record_count} records")
        
        # Check for old failure_events table
        if is_postgresql():
            old_exists_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'failure_events'
            )
            """
        else:
            old_exists_query = "SELECT name FROM sqlite_master WHERE type='table' AND name='failure_events'"
        
        old_result = db_manager.adapter.execute_query(old_exists_query)
        old_table_exists = bool(old_result and (
            old_result[0].get('exists', False) if is_postgresql() 
            else len(old_result) > 0
        ))
        
        if old_table_exists:
            print("⚠️  Warning: failure_events table still exists")
        else:
            print("✓ failure_events table has been removed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verifying events table: {e}")
        return False

def main():
    """Main function"""
    print("Events Table Constraint and Index Fixer")
    print("=" * 50)
    
    try:
        # Step 1: Verify events table
        if not verify_events_table():
            print("❌ Events table verification failed")
            return 1
        
        # Step 2: Rename constraints and indexes
        if not rename_constraints_and_indexes():
            print("⚠️  Some constraints/indexes could not be renamed")
            print("This might be normal if they were already renamed or don't exist")
        
        # Step 3: Final verification
        remaining_items = get_failure_events_constraints_and_indexes()
        if remaining_items:
            print(f"\n⚠️  {len(remaining_items)} items still reference failure_events:")
            for item in remaining_items:
                print(f"  - {item['name']} ({item['type']})")
            print("These may need manual intervention")
        else:
            print("\n✅ All constraints and indexes have been updated!")
        
        print("\n🎉 Events table migration verification completed")
        return 0
        
    except Exception as e:
        print(f"❌ Script failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())

