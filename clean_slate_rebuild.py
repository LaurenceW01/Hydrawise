#!/usr/bin/env python3
"""
Clean Slate Status Changes Rebuild

Due to massive duplication in the status changes table, this script:
1. Deletes ALL existing status change records
2. Rebuilds them cleanly using the fixed logic
3. Ensures no duplicates are created

Author: AI Assistant
Date: 2025-09-03
"""

import sqlite3
import sys
import os
from datetime import date

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from irrigation_tracking_system import IrrigationTrackingSystem, create_default_tracking_system

def clean_all_status_changes(db_path: str):
    """Delete ALL status change records to start fresh"""
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Get current count
        cursor.execute("SELECT COUNT(*) FROM scheduled_run_status_changes")
        total_records = cursor.fetchone()[0]
        
        # Delete all records
        cursor.execute("DELETE FROM scheduled_run_status_changes")
        deleted_count = cursor.rowcount
        
        conn.commit()
        
        return total_records, deleted_count

def get_dates_with_scheduled_runs(db_path: str):
    """Get all dates that have scheduled runs (these are candidates for status change detection)"""
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT schedule_date, COUNT(*) as run_count
            FROM scheduled_runs 
            GROUP BY schedule_date
            ORDER BY schedule_date ASC  -- Process in chronological order
        """)
        
        dates = []
        for row in cursor.fetchall():
            schedule_date, count = row
            dates.append((date.fromisoformat(schedule_date), count))
        
        return dates

def rebuild_status_changes_clean(db_path: str, target_date: date):
    """Rebuild status changes for a date using the fixed logic - ONCE only"""
    
    try:
        # Create tracking system with the fixed _get_recent_scheduled_runs method
        tracking_system = create_default_tracking_system()
        
        # Process the date using the corrected logic
        runs_processed, changes_detected = tracking_system.process_scheduled_runs_with_tracking(
            target_date, f"clean_rebuild_{target_date.isoformat()}"
        )
        
        return runs_processed, changes_detected, None
        
    except Exception as e:
        return 0, 0, str(e)

def main():
    """Main function for clean slate rebuild"""
    
    db_path = "database/irrigation_data.db"
    
    print("=" * 80)
    print("CLEAN SLATE STATUS CHANGES REBUILD")
    print("=" * 80)
    print()
    
    # Show current state
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scheduled_run_status_changes")
        current_records = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT zone_name || current_run_date || current_scheduled_start_time || previous_run_date || previous_scheduled_start_time) FROM scheduled_run_status_changes")
        unique_records = cursor.fetchone()[0]
        
        duplicates = current_records - unique_records
    
    print(f"Current status change records: {current_records}")
    print(f"Unique records: {unique_records}")
    print(f"Duplicate records: {duplicates}")
    print()
    
    if duplicates > 0:
        print(f"⚠️  Found {duplicates} duplicate records that need cleaning")
    
    # Get dates to process
    print("🔍 Finding dates with scheduled runs...")
    dates_to_process = get_dates_with_scheduled_runs(db_path)
    
    print(f"Found {len(dates_to_process)} dates with scheduled runs:")
    for process_date, run_count in dates_to_process:
        print(f"  {process_date}: {run_count} scheduled runs")
    
    print()
    print("This will:")
    print("1. DELETE all existing status change records")
    print("2. Rebuild status changes for recent dates using FIXED logic")
    print("3. Ensure no duplicates are created")
    print()
    
    response = input("Proceed with clean slate rebuild? (y/N): ").lower().strip()
    if response != 'y':
        print("❌ Clean slate rebuild cancelled")
        return
    
    print()
    print("🧹 Cleaning all existing status change records...")
    
    # Clean slate - delete everything
    total_before, deleted_count = clean_all_status_changes(db_path)
    print(f"✅ Deleted {deleted_count} existing records")
    
    print()
    print("🔧 Rebuilding status changes with fixed logic...")
    
    total_new_changes = 0
    total_runs_processed = 0
    errors = []
    
    for process_date, run_count in dates_to_process:
        print(f"Processing {process_date}...")
        
        runs_processed, changes_detected, error = rebuild_status_changes_clean(db_path, process_date)
        
        if error:
            print(f"  ❌ Error: {error}")
            errors.append(f"{process_date}: {error}")
        else:
            print(f"  ✅ Processed {runs_processed} runs, detected {changes_detected} changes")
            total_runs_processed += runs_processed
            total_new_changes += changes_detected
    
    print()
    print("CLEAN REBUILD RESULTS:")
    print("=" * 30)
    print(f"🗑️  Deleted old records: {deleted_count}")
    print(f"✅ Created new records: {total_new_changes}")
    print(f"📊 Net change: {total_new_changes - deleted_count:+d} records")
    print(f"🔧 Total runs processed: {total_runs_processed}")
    
    if errors:
        print(f"❌ Errors encountered: {len(errors)}")
        for error in errors:
            print(f"   {error}")
    
    # Verify clean state
    print()
    print("🔍 Verifying clean state...")
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Check for duplicates
        cursor.execute("""
            SELECT COUNT(*) - COUNT(DISTINCT zone_name || current_run_date || current_scheduled_start_time || previous_run_date || previous_scheduled_start_time)
            FROM scheduled_run_status_changes
        """)
        remaining_duplicates = cursor.fetchone()[0]
        
        # Check for backwards dates
        cursor.execute("SELECT COUNT(*) FROM scheduled_run_status_changes WHERE current_run_date < previous_run_date")
        backwards_dates = cursor.fetchone()[0]
        
        # Get final count
        cursor.execute("SELECT COUNT(*) FROM scheduled_run_status_changes")
        final_count = cursor.fetchone()[0]
    
    print(f"Final record count: {final_count}")
    print(f"Remaining duplicates: {remaining_duplicates}")
    print(f"Backwards date records: {backwards_dates}")
    
    if remaining_duplicates == 0 and backwards_dates == 0:
        print("🎉 SUCCESS: Clean rebuild completed - no duplicates or backwards records!")
    else:
        print("⚠️  WARNING: Issues remain after rebuild")

if __name__ == "__main__":
    main()
