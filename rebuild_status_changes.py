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

import sys
import os
from datetime import date, datetime

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from irrigation_tracking_system import IrrigationTrackingSystem, create_default_tracking_system
from database.universal_database_manager import get_universal_database_manager

def get_problematic_dates():
    """Get the dates that have status change records (these are the ones we need to rebuild)"""
    
    db_manager = get_universal_database_manager()
    
    results = db_manager.adapter.execute_query("""
        SELECT DISTINCT change_detected_date, COUNT(*) as record_count
        FROM scheduled_run_status_changes 
        GROUP BY change_detected_date
        ORDER BY change_detected_date
    """)
    
    dates = []
    for row in results:
        change_date = row['change_detected_date']
        count = row['record_count']
        # Convert string date to date object if needed
        if isinstance(change_date, str):
            change_date = date.fromisoformat(change_date)
        dates.append((change_date, count))
    
    return dates

def delete_status_changes_for_date(target_date: date):
    """Delete all status change records for a specific date"""
    
    db_manager = get_universal_database_manager()
    
    deleted_count = db_manager.adapter.execute_delete("""
        DELETE FROM scheduled_run_status_changes 
        WHERE change_detected_date = %s
    """, (target_date.isoformat(),))
    
    return deleted_count

def rebuild_status_changes_for_date(target_date: date):
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
    
    print("=" * 80)
    print("REBUILD STATUS CHANGES FROM SCHEDULE DATA")
    print("=" * 80)
    print()
    
    # Get problematic dates
    print("🔍 Analyzing existing status change records...")
    problematic_dates = get_problematic_dates()
    
    if not problematic_dates:
        print("ℹ️  No existing status change records found")
        print("🔄 Will analyze all scheduled runs to detect status changes...")
        
        # Get all dates that have scheduled runs
        db_manager = get_universal_database_manager()
        results = db_manager.adapter.execute_query("""
            SELECT DISTINCT schedule_date, COUNT(*) as run_count
            FROM scheduled_runs 
            GROUP BY schedule_date
            ORDER BY schedule_date
        """)
        
        dates_with_runs = []
        for row in results:
            schedule_date = row['schedule_date']
            count = row['run_count']
            # Convert string date to date object if needed
            if isinstance(schedule_date, str):
                schedule_date = date.fromisoformat(schedule_date)
            dates_with_runs.append((schedule_date, count))
        
        if not dates_with_runs:
            print("❌ No scheduled runs found to analyze")
            return
            
        print(f"Found {len(dates_with_runs)} dates with scheduled runs to analyze")
        problematic_dates = dates_with_runs
    
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
    
    # Delete ALL existing status change records at once to avoid conflicts
    print("🗑️  Deleting ALL existing status change records...")
    db_manager = get_universal_database_manager()
    total_deleted = db_manager.adapter.execute_delete("DELETE FROM scheduled_run_status_changes")
    print(f"  Deleted {total_deleted} old records")
    print()
    
    total_new_changes = 0
    
    for problem_date, old_count in problematic_dates:
        print(f"Processing {problem_date}...")
        
        # Rebuild using fixed logic (no need to delete since we already cleared everything)
        try:
            runs_processed, changes_detected = rebuild_status_changes_for_date(problem_date)
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
    db_manager = get_universal_database_manager()
    results = db_manager.adapter.execute_query("""
        SELECT COUNT(*) as count FROM scheduled_run_status_changes 
        WHERE current_run_date < previous_run_date
    """)
    backwards_count = results[0]['count'] if results else 0
    
    if backwards_count == 0:
        print("🎉 SUCCESS: No backwards date records remain!")
    else:
        print(f"⚠️  WARNING: {backwards_count} backwards date records still exist")

if __name__ == "__main__":
    main()