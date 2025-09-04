#!/usr/bin/env python3
"""
Rebuild Status Changes from Schedule Data

This script rebuilds the status change records for problematic dates by:
1. Deleting existing status change records for those dates
2. Reprocessing the schedule data using the fixed status change detection logic
3. Generating correct status change records

This is more reliable than trying to fix backwards records by pattern matching.

Author: AI Assistant
Date: 2025-09-03
"""

import sqlite3
import sys
import os
from datetime import date, datetime

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from irrigation_tracking_system import IrrigationTrackingSystem, create_default_tracking_system

def get_problematic_dates(db_path: str):
    """Get the dates that have status change records (these are the ones we need to rebuild)"""
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT change_detected_date, COUNT(*) as record_count
            FROM scheduled_run_status_changes 
            ORDER BY change_detected_date
        """)
        
        dates = []
        for row in cursor.fetchall():
            change_date, count = row
            dates.append((date.fromisoformat(change_date), count))
        
        return dates

def delete_status_changes_for_date(db_path: str, target_date: date):
    """Delete all status change records for a specific date"""
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM scheduled_run_status_changes 
            WHERE change_detected_date = ?
        """, (target_date.isoformat(),))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        return deleted_count

def rebuild_status_changes_for_date(db_path: str, target_date: date):
    """Rebuild status changes for a specific date using the fixed logic"""
    
    # Create tracking system with the fixed _get_recent_scheduled_runs method
    tracking_system = create_default_tracking_system()
    
    # Process the date using the corrected logic
    runs_processed, changes_detected = tracking_system.process_scheduled_runs_with_tracking(
        target_date, f"rebuild_{target_date.isoformat()}"
    )
    
    return runs_processed, changes_detected

def main():
    """Main function to rebuild status changes"""
    
    db_path = "database/irrigation_data.db"
    
    print("=" * 80)
    print("REBUILD STATUS CHANGES FROM SCHEDULE DATA")
    print("=" * 80)
    print()
    
    # Get problematic dates
    print("🔍 Analyzing existing status change records...")
    problematic_dates = get_problematic_dates(db_path)
    
    if not problematic_dates:
        print("✅ No status change records found - nothing to rebuild")
        return
    
    print(f"Found status change records for {len(problematic_dates)} dates:")
    total_records = 0
    for problem_date, count in problematic_dates:
        print(f"  {problem_date}: {count} records")
        total_records += count
    
    print(f"\nTotal records to rebuild: {total_records}")
    print()
    
    # Confirm before proceeding
    print("This will:")
    print("1. Delete ALL existing status change records for these dates")
    print("2. Reprocess the schedule data using the FIXED status change detection")
    print("3. Generate new, correct status change records")
    print()
    
    response = input("Proceed with rebuild? (y/N): ").lower().strip()
    if response != 'y':
        print("❌ Rebuild cancelled")
        return
    
    print()
    print("🔧 Rebuilding status changes...")
    print()
    
    total_deleted = 0
    total_new_changes = 0
    
    for problem_date, old_count in problematic_dates:
        print(f"Processing {problem_date}...")
        
        # Delete existing records
        deleted_count = delete_status_changes_for_date(db_path, problem_date)
        total_deleted += deleted_count
        print(f"  Deleted {deleted_count} old records")
        
        # Rebuild using fixed logic
        try:
            runs_processed, changes_detected = rebuild_status_changes_for_date(db_path, problem_date)
            total_new_changes += changes_detected
            print(f"  Processed {runs_processed} runs, detected {changes_detected} changes")
        except Exception as e:
            print(f"  ❌ Error rebuilding {problem_date}: {e}")
            continue
        
        print()
    
    print("REBUILD RESULTS:")
    print("=" * 30)
    print(f"✅ Deleted old records: {total_deleted}")
    print(f"✅ Created new records: {total_new_changes}")
    print(f"📊 Net change: {total_new_changes - total_deleted:+d} records")
    print()
    
    if total_new_changes < total_deleted:
        print("📉 Fewer new records suggests the fix eliminated duplicate/incorrect changes")
    elif total_new_changes > total_deleted:
        print("📈 More new records suggests some legitimate changes were missing")
    else:
        print("📊 Same number of records - data structure corrected")
    
    # Verify no backwards records remain
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM scheduled_run_status_changes 
            WHERE current_run_date < previous_run_date
        """)
        backwards_count = cursor.fetchone()[0]
        
        if backwards_count == 0:
            print("🎉 SUCCESS: No backwards date records remain!")
        else:
            print(f"⚠️  WARNING: {backwards_count} backwards date records still exist")

if __name__ == "__main__":
    main()
