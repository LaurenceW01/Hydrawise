#!/usr/bin/env python3
"""
Check what scheduled runs are stored in the database

This script shows you exactly where your 5 scheduled runs are stored.
"""

import os
import sys
import sqlite3
from datetime import date, datetime, timedelta

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from utils.timezone_utils import to_houston_time, get_display_timestamp
from database.db_interface import HydrawiseDB

def main():
    """Check what's stored in the database"""
    print("[ANALYSIS] Checking Stored Schedule Data in Database")
    print("=" * 50)
    
    try:
        # Initialize database interface
        db = HydrawiseDB()
        
        # Get database location and info
        info = db.get_database_info()
        print(f"[SYMBOL] Database Location: {info.get('database_path')}")
        print(f"[RESULTS] Total Scheduled Runs: {info.get('scheduled_runs_count', 0)}")
        print(f"[RESULTS] Total Actual Runs: {info.get('actual_runs_count', 0)}")
        print(f"[SYMBOL][SYMBOL]  Cloud Sync: {'Enabled' if info.get('cloud_sync_enabled') else 'Disabled'}")
        
        # Check today's data
        today = date.today()
        print(f"\n[DATE] Checking scheduled runs for TODAY ({today}):")
        
        today_runs = db.read_scheduled_runs(today)
        print(f"   Found {len(today_runs)} scheduled runs for today")
        
        if today_runs:
            print("\n   [LOG] Today's Scheduled Runs:")
            print("   " + "-" * 80)
            print(f"   {'Zone Name':<35} {'Start Time':<10} {'Duration':<8} {'Status':<15}")
            print("   " + "-" * 80)
            
            for i, run in enumerate(today_runs, 1):
                zone_name = run['zone_name'][:32] + "..." if len(run['zone_name']) > 35 else run['zone_name']
                start_time = datetime.fromisoformat(run['scheduled_start_time']).strftime('%I:%M %p')
                duration = f"{run['scheduled_duration_minutes']}min"
                status = "[SYMBOL][SYMBOL] Rain" if run['is_rain_cancelled'] else "[SYMBOL][SYMBOL] Normal"
                
                print(f"   {zone_name:<35} {start_time:<10} {duration:<8} {status:<15}")
        
        # Check tomorrow's data
        tomorrow = date.today() + timedelta(days=1)
        print(f"\n[DATE] Checking scheduled runs for TOMORROW ({tomorrow}):")
        
        tomorrow_runs = db.read_scheduled_runs(tomorrow)
        print(f"   Found {len(tomorrow_runs)} scheduled runs for tomorrow")
        
        if tomorrow_runs:
            print("\n   [LOG] Tomorrow's Scheduled Runs:")
            print("   " + "-" * 80)
            print(f"   {'Zone Name':<35} {'Start Time':<10} {'Duration':<8} {'Status':<15}")
            print("   " + "-" * 80)
            
            for i, run in enumerate(tomorrow_runs, 1):
                zone_name = run['zone_name'][:32] + "..." if len(run['zone_name']) > 35 else run['zone_name']
                start_time = datetime.fromisoformat(run['scheduled_start_time']).strftime('%I:%M %p')
                duration = f"{run['scheduled_duration_minutes']}min"
                status = "[SYMBOL][SYMBOL] Rain" if run['is_rain_cancelled'] else "[SYMBOL][SYMBOL] Normal"
                
                print(f"   {zone_name:<35} {start_time:<10} {duration:<8} {status:<15}")
        
        # Check raw database table directly
        print(f"\n[DATABASE]  Raw Database Table Contents:")
        print("   (showing all scheduled_runs records)")
        
        try:
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT schedule_date, zone_name, scheduled_start_time, 
                           scheduled_duration_minutes, is_rain_cancelled, created_at
                    FROM scheduled_runs 
                    ORDER BY schedule_date, scheduled_start_time
                """)
                
                all_runs = cursor.fetchall()
                
                if all_runs:
                    print(f"   [LOG] Total records in scheduled_runs table: {len(all_runs)}")
                    print("   " + "-" * 90)
                    print(f"   {'Date':<12} {'Zone Name':<25} {'Start Time':<15} {'Duration':<8} {'Rain':<5} {'Created':<15}")
                    print("   " + "-" * 90)
                    
                    for run in all_runs:
                        schedule_date = run[0]
                        zone_name = run[1][:22] + "..." if len(run[1]) > 25 else run[1]
                        start_time = datetime.fromisoformat(run[2]).strftime('%I:%M %p')
                        duration = f"{run[3]}min"
                        rain_cancelled = "Yes" if run[4] else "No"
                        # Convert created timestamp to Houston time for display
                        created_dt = datetime.fromisoformat(run[5])
                        created_houston = to_houston_time(created_dt)
                        created = created_houston.strftime('%m/%d %I:%M %p CT')
                        
                        print(f"   {schedule_date:<12} {zone_name:<25} {start_time:<15} {duration:<8} {rain_cancelled:<5} {created:<15}")
                else:
                    print("   [ERROR] No records found in scheduled_runs table")
                    
        except Exception as e:
            print(f"   [ERROR] Error reading raw table: {e}")
        
        # Summary
        total_stored = len(today_runs) + len(tomorrow_runs)
        print(f"\n[RESULTS] SUMMARY:")
        print(f"   Today's runs stored: {len(today_runs)}")
        print(f"   Tomorrow's runs stored: {len(tomorrow_runs)}")
        print(f"   Total runs accessible: {total_stored}")
        
        if total_stored > 0:
            print(f"\n[OK] SUCCESS: Your scheduled runs are stored in the 'scheduled_runs' table!")
            print(f"[SYMBOL] Table location: {db.db_path} -> scheduled_runs table")
        else:
            print(f"\n[WARNING]  No scheduled runs found. The data may not have been written successfully.")
            
    except Exception as e:
        print(f"\n[ERROR] Error checking database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
