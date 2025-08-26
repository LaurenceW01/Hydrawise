#!/usr/bin/env python3
"""
Test Script: Collect Today's Schedule and Write to Database

Simple test to verify we can collect real scheduling data and store it
in the database with all popup information.
"""

import os
import sys
from datetime import datetime, date
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hydrawise_web_scraper_refactored import HydrawiseWebScraper
from database.intelligent_data_storage import IntelligentDataStorage

def test_schedule_collection_to_db():
    """Collect first 10 scheduled runs from today and store in database"""
    
    print("[SYMBOL] Testing Schedule Collection [SYMBOL] Database Storage")
    print("=" * 60)
    
    # Load credentials
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("[SYMBOL] Missing credentials in .env file")
        return False
        
    try:
        # Initialize components
        print("[SYMBOL] Initializing scraper and database...")
        scraper = HydrawiseWebScraper(username, password, headless=True)
        storage = IntelligentDataStorage("database/irrigation_data.db")
        
        # Collect today's schedule (limit to first 10 for testing)
        print("[SYMBOL] Collecting today's schedule (first 10 runs)...")
        today = datetime.now()
        
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Failed to login to Hydrawise portal")
            
        scraper.navigate_to_reports()
        
        # Get schedule data using the existing method
        scheduled_runs = scraper.extract_scheduled_runs(today, limit_zones=10)
        
        scraper.stop_browser()
        
        print(f"[SYMBOL] Collected {len(scheduled_runs)} scheduled runs")
        
        if not scheduled_runs:
            print("[SYMBOL][SYMBOL]  No scheduled runs found for today")
            return False
            
        # Display what we collected
        print("\n[SYMBOL] Collected Scheduled Runs:")
        for i, run in enumerate(scheduled_runs[:5], 1):  # Show first 5
            zone_name = run.zone_name[:30] + "..." if len(run.zone_name) > 30 else run.zone_name
            start_time = run.start_time.strftime('%I:%M %p')
            duration = run.duration_minutes
            
            # Check if popup data exists
            popup_info = ""
            if hasattr(run, 'popup_lines') and run.popup_lines:
                popup_info = f" (Popup: {len(run.popup_lines)} lines)"
            elif hasattr(run, 'raw_popup_text') and run.raw_popup_text:
                popup_info = " (Raw popup data)"
                
            print(f"   {i}. {zone_name:<35} {start_time:<10} {duration:>2}min{popup_info}")
            
        if len(scheduled_runs) > 5:
            print(f"   ... and {len(scheduled_runs) - 5} more runs")
            
        # Store in database
        print(f"\n[SYMBOL] Storing {len(scheduled_runs)} runs in database...")
        stored_count = storage.store_scheduled_runs_enhanced(scheduled_runs, today.date())
        
        print(f"[SYMBOL] Successfully stored {stored_count} scheduled runs")
        
        # Verify storage by querying back
        print("\n[SYMBOL] Verifying database storage...")
        import sqlite3
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT zone_name, scheduled_start_time, scheduled_duration_minutes,
                       is_rain_cancelled, raw_popup_text IS NOT NULL as has_popup
                FROM scheduled_runs 
                WHERE schedule_date = ?
                ORDER BY scheduled_start_time
                LIMIT 5
            """, (today.date(),))
            
            results = cursor.fetchall()
            
            print(f"[SYMBOL] Database contains {len(results)} runs (showing first 5):")
            for i, (zone_name, start_time, duration, rain_cancelled, has_popup) in enumerate(results, 1):
                zone_display = zone_name[:30] + "..." if len(zone_name) > 30 else zone_name
                time_display = datetime.fromisoformat(start_time).strftime('%I:%M %p')
                rain_status = "[SYMBOL][SYMBOL]" if rain_cancelled else "[SYMBOL][SYMBOL]"
                popup_status = "[SYMBOL]" if has_popup else "[SYMBOL]"
                
                print(f"   {i}. {zone_display:<35} {time_display:<10} {duration:>2}min {rain_status} {popup_status}")
                
        print(f"\n[SYMBOL] SUCCESS! Schedule data collection and storage working perfectly!")
        print(f"[SYMBOL] Database now contains today's irrigation schedule with popup data")
        
        return True
        
    except Exception as e:
        print(f"\n[SYMBOL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup browser if it's still running
        try:
            if 'scraper' in locals():
                scraper.stop_browser()
        except:
            pass
            
        return False

def main():
    """Run the test"""
    try:
        success = test_schedule_collection_to_db()
        
        if success:
            print("\n[SYMBOL] Test completed successfully!")
            print("[SYMBOL][SYMBOL]  Your database is ready for schedule vs actual matching")
        else:
            print("\n[SYMBOL] Test failed - check the error messages above")
            
    except KeyboardInterrupt:
        print("\n[SYMBOL] Test interrupted by user")
    except Exception as e:
        print(f"\n[SYMBOL] Unexpected error: {e}")

if __name__ == "__main__":
    main()
