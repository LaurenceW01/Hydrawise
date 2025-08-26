#!/usr/bin/env python3
"""
Check what actual/reported runs are stored in the database

This script shows you exactly where your reported runs are stored.
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
    """Check what actual/reported runs are stored in the database"""
    print("[ANALYSIS] Checking Stored Actual/Reported Runs in Database")
    print("=" * 60)
    
    try:
        # Initialize database interface
        db = HydrawiseDB()
        
        # Get database location and info
        info = db.get_database_info()
        print(f"[SYMBOL] Database Location: {info.get('database_path')}")
        print(f"[RESULTS] Total Scheduled Runs: {info.get('scheduled_runs_count', 0)}")
        print(f"[RESULTS] Total Actual Runs: {info.get('actual_runs_count', 0)}")
        print(f"[SYMBOL][SYMBOL]  Cloud Sync: {'Enabled' if info.get('cloud_sync_enabled') else 'Disabled'}")
        
        # Check today's actual runs
        today = date.today()
        print(f"\n[DATE] Checking actual runs for TODAY ({today}):")
        
        today_runs = db.read_actual_runs(today)
        print(f"   Found {len(today_runs)} actual runs for today")
        
        if today_runs:
            print("\n   [LOG] Today's Actual Runs:")
            print("   " + "-" * 90)
            print(f"   {'Zone Name':<35} {'Start Time':<12} {'Duration':<8} {'Gallons':<10} {'Status':<15}")
            print("   " + "-" * 90)
            
            for i, run in enumerate(today_runs, 1):
                zone_name = run['zone_name'][:32] + "..." if len(run['zone_name']) > 35 else run['zone_name']
                start_time = datetime.fromisoformat(run['actual_start_time']).strftime('%I:%M %p')
                duration = f"{run['actual_duration_minutes']}min"
                gallons = f"{run['actual_gallons']:.2f}" if run['actual_gallons'] else "N/A"
                status = run['status'][:12] + "..." if len(run['status']) > 15 else run['status']
                
                print(f"   {zone_name:<35} {start_time:<12} {duration:<8} {gallons:<10} {status:<15}")
        
        # Check yesterday's actual runs
        yesterday = today - timedelta(days=1)
        print(f"\n[DATE] Checking actual runs for YESTERDAY ({yesterday}):")
        
        yesterday_runs = db.read_actual_runs(yesterday)
        print(f"   Found {len(yesterday_runs)} actual runs for yesterday")
        
        if yesterday_runs:
            print("\n   [LOG] Yesterday's Actual Runs:")
            print("   " + "-" * 90)
            print(f"   {'Zone Name':<35} {'Start Time':<12} {'Duration':<8} {'Gallons':<10} {'Status':<15}")
            print("   " + "-" * 90)
            
            for i, run in enumerate(yesterday_runs, 1):
                zone_name = run['zone_name'][:32] + "..." if len(run['zone_name']) > 35 else run['zone_name']
                start_time = datetime.fromisoformat(run['actual_start_time']).strftime('%I:%M %p')
                duration = f"{run['actual_duration_minutes']}min"
                gallons = f"{run['actual_gallons']:.2f}" if run['actual_gallons'] else "N/A"
                status = run['status'][:12] + "..." if len(run['status']) > 15 else run['status']
                
                print(f"   {zone_name:<35} {start_time:<12} {duration:<8} {gallons:<10} {status:<15}")
        
        # Check raw database table directly
        print(f"\n[DATABASE]  Raw Actual Runs Table Contents:")
        print("   (showing all actual_runs records from last 3 days)")
        
        try:
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                
                # Get runs from last 3 days
                three_days_ago = today - timedelta(days=2)
                
                cursor.execute("""
                    SELECT run_date, zone_name, actual_start_time, 
                           actual_duration_minutes, actual_gallons, status, created_at
                    FROM actual_runs 
                    WHERE run_date >= ?
                    ORDER BY run_date DESC, actual_start_time
                """, (three_days_ago,))
                
                all_runs = cursor.fetchall()
                
                if all_runs:
                    print(f"   [LOG] Total records in actual_runs table (last 3 days): {len(all_runs)}")
                    print("   " + "-" * 110)
                    print(f"   {'Date':<12} {'Zone Name':<25} {'Start Time':<12} {'Duration':<8} {'Gallons':<8} {'Status':<15} {'Created (CT)':<15}")
                    print("   " + "-" * 110)
                    
                    for run in all_runs:
                        run_date = run[0]
                        zone_name = run[1][:22] + "..." if len(run[1]) > 25 else run[1]
                        start_time = datetime.fromisoformat(run[2]).strftime('%I:%M %p')
                        duration = f"{run[3]}min"
                        gallons = f"{run[4]:.2f}" if run[4] else "N/A"
                        status = run[5][:12] + "..." if len(run[5]) > 15 else run[5]
                        # Convert created timestamp to Houston time for display
                        created_dt = datetime.fromisoformat(run[6])
                        created_houston = to_houston_time(created_dt)
                        created = created_houston.strftime('%m/%d %I:%M %p')
                        
                        print(f"   {run_date:<12} {zone_name:<25} {start_time:<12} {duration:<8} {gallons:<8} {status:<15} {created:<15}")
                else:
                    print("   [ERROR] No actual runs found in database")
                    
        except Exception as e:
            print(f"   [ERROR] Error reading raw table: {e}")
        
        # Summary
        total_today = len(today_runs)
        total_yesterday = len(yesterday_runs)
        print(f"\n[RESULTS] SUMMARY:")
        print(f"   Today's actual runs: {total_today}")
        print(f"   Yesterday's actual runs: {total_yesterday}")
        print(f"   Total recent runs accessible: {total_today + total_yesterday}")
        
        if total_today > 0:
            print(f"\n[OK] SUCCESS: Your actual/reported runs are stored in the 'actual_runs' table!")
            print(f"[SYMBOL] Table location: {db.db_path} -> actual_runs table")
        else:
            print(f"\n[WARNING]  No actual runs found for today. Data may not have been written successfully.")
            
    except Exception as e:
        print(f"\n[ERROR] Error checking database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
