#!/usr/bin/env python3
"""
Test script to collect today's schedule and write it to the database

This script demonstrates how to:
1. Collect schedule data from the web scraper
2. Write it to the database using the new DB interface
3. Read it back to verify storage

Author: AI Assistant
Date: 2025-08-23
"""

import os
import sys
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Add parent directory to path to import our modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from hydrawise_web_scraper_refactored import HydrawiseWebScraper
from database.db_interface import HydrawiseDB

def main():
    """Collect today's schedule and write to database"""
    print("[SYMBOL] Collecting Today's Schedule and Writing to Database")
    print("=" * 60)
    
    try:
        # Load credentials from .env file
        load_dotenv()
        username = os.getenv('HYDRAWISE_USER')
        password = os.getenv('HYDRAWISE_PASSWORD')
        
        if not username or not password:
            raise Exception("Please set HYDRAWISE_USER and HYDRAWISE_PASSWORD in .env file")
        
        # Initialize database interface
        print("[SYMBOL] Initializing database interface...")
        db = HydrawiseDB()
        
        # Show current database info
        print("\n[SYMBOL] Current Database Info:")
        info = db.get_database_info()
        print(f"   Scheduled runs: {info.get('scheduled_runs_count', 0)}")
        print(f"   Actual runs: {info.get('actual_runs_count', 0)}")
        print(f"   Cloud sync: {'Enabled' if info.get('cloud_sync_enabled') else 'Disabled'}")
        
        # Initialize scraper
        print(f"\n[SYMBOL] Collecting schedule data from Hydrawise (first 5 zones only for speed)...")
        scraper = HydrawiseWebScraper(username, password, headless=False)
        
        # Collect 24-hour schedule data (limit to first 5 zones for speed)
        results = scraper.collect_24_hour_schedule(limit_zones=5)
        
        # Note: Browser cleanup is handled by collect_24_hour_schedule() method
        
        # Check if collection was successful
        today_runs = results.get('today', [])
        tomorrow_runs = results.get('tomorrow', [])
        total_runs = len(today_runs) + len(tomorrow_runs)
        
        print(f"[SYMBOL] Collection completed (limited to first 5 zones):")
        print(f"   Today: {len(today_runs)} runs")
        print(f"   Tomorrow: {len(tomorrow_runs)} runs")
        print(f"   Total: {total_runs} runs")
        print(f"   Rain sensor: {results.get('sensor_status', 'Unknown')}")
        
        if total_runs == 0:
            print("[SYMBOL][SYMBOL]  No schedule data collected - nothing to write to database")
            return
        
        # Write today's schedule to database
        if today_runs:
            print(f"\n[SYMBOL] Writing today's schedule to database...")
            today_stored = db.write_scheduled_runs(today_runs, date.today())
            print(f"[SYMBOL] Stored {today_stored} scheduled runs for today")
        
        # Write tomorrow's schedule to database
        if tomorrow_runs:
            print(f"\n[SYMBOL] Writing tomorrow's schedule to database...")
            tomorrow_date = date.today() + timedelta(days=1)
            tomorrow_stored = db.write_scheduled_runs(tomorrow_runs, tomorrow_date)
            print(f"[SYMBOL] Stored {tomorrow_stored} scheduled runs for tomorrow")
        
        # Verify storage by reading back
        print(f"\n[SYMBOL] Verifying database storage...")
        
        # Read today's data
        stored_today = db.read_scheduled_runs(date.today())
        print(f"[SYMBOL] Database contains {len(stored_today)} runs for today")
        
        if stored_today:
            print("   Sample runs for today:")
            for i, run in enumerate(stored_today[:3], 1):  # Show first 3
                zone_name = run['zone_name'][:30] + "..." if len(run['zone_name']) > 30 else run['zone_name']
                start_time = datetime.fromisoformat(run['scheduled_start_time']).strftime('%I:%M %p')
                duration = run['scheduled_duration_minutes']
                rain_status = "[SYMBOL][SYMBOL]" if run['is_rain_cancelled'] else "[SYMBOL][SYMBOL]"
                
                print(f"      {i}. {zone_name:<35} {start_time:<10} {duration:>2}min {rain_status}")
            
            if len(stored_today) > 3:
                print(f"      ... and {len(stored_today) - 3} more runs")
        
        # Read tomorrow's data if we stored any
        if tomorrow_runs:
            tomorrow_date = date.today() + timedelta(days=1)
            stored_tomorrow = db.read_scheduled_runs(tomorrow_date)
            print(f"[SYMBOL] Database contains {len(stored_tomorrow)} runs for tomorrow")
        
        # Show updated database info
        print(f"\n[SYMBOL] Updated Database Info:")
        new_info = db.get_database_info()
        print(f"   Total scheduled runs: {new_info.get('scheduled_runs_count', 0)}")
        print(f"   Date range: {new_info.get('scheduled_date_range')}")
        
        print(f"\n[SYMBOL] SUCCESS! Schedule data collection and storage completed!")
        print(f"[SYMBOL] Your irrigation schedule is now stored in the database")
        
        # Show week summary
        print(f"\n[SYMBOL] Weekly Schedule Summary:")
        summary = db.read_schedule_summary(days=7)
        for day_data in summary.get('scheduled_by_date', []):
            day_date = day_data['date']
            scheduled_count = day_data['scheduled_count']
            rain_cancelled = day_data['rain_cancelled_count']
            total_minutes = day_data['total_scheduled_minutes']
            
            rain_info = f" ({rain_cancelled} rain cancelled)" if rain_cancelled > 0 else ""
            print(f"   {day_date}: {scheduled_count} runs, {total_minutes} min{rain_info}")
        
    except Exception as e:
        print(f"\n[SYMBOL] Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup browser if it's still running (additional safety)
        try:
            if 'scraper' in locals() and hasattr(scraper, 'driver') and scraper.driver:
                print("[SYMBOL] Cleaning up browser...")
                scraper.stop_browser()
        except Exception as cleanup_error:
            print(f"[SYMBOL][SYMBOL]  Browser cleanup warning: {cleanup_error}")

if __name__ == "__main__":
    main()
