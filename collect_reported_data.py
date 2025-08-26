#!/usr/bin/env python3
"""
Collect Previous Day Reported Runs

Collects the first 10 reported runs from the previous day and stores them
in the database with all popup data for mismatch analysis.
"""

import os
import sys
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hydrawise_web_scraper_refactored import HydrawiseWebScraper
from database.intelligent_data_storage import IntelligentDataStorage

def collect_reported_data():
    """Collect and store the first 10 reported runs from previous day"""
    
    print("[RESULTS] COLLECTING PREVIOUS DAY REPORTED RUNS")
    print("=" * 60)
    
    # Calculate previous day
    previous_day = date.today() - timedelta(days=1)
    print(f"[DATE] Target Date: {previous_day.strftime('%A, %B %d, %Y')}")
    print("[SYMBOL] Target: First 10 reported runs with popup data")
    print("=" * 60)
    
    # Load credentials
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("[ERROR] Missing credentials in .env file")
        return False
        
    try:
        # Initialize database
        storage = IntelligentDataStorage("database/irrigation_data.db")
        print("[OK] Database connection established")
        
        # Check if we already have data for this date
        import sqlite3
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM actual_runs WHERE run_date = ?', (previous_day,))
            existing_count = cursor.fetchone()[0]
            
        if existing_count > 0:
            print(f"[WARNING]  Found {existing_count} existing reported runs for {previous_day}")
            response = input("   Clear existing data and re-collect? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                with sqlite3.connect(storage.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM actual_runs WHERE run_date = ?', (previous_day,))
                    conn.commit()
                    print(f"[DELETE]  Cleared {existing_count} existing runs")
            else:
                print("[RESULTS] Keeping existing data, cancelling collection")
                return True
        
        # Initialize web scraper
        print("[WEB] Initializing web scraper...")
        scraper = HydrawiseWebScraper(username, password, headless=True)
        
        # Start browser and login
        print("[SYMBOL] Starting browser and logging in...")
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Login failed")
            
        print("[OK] Login successful")
        
        # Navigate to reports
        print("[SYMBOL][SYMBOL]  Navigating to reports page...")
        scraper.navigate_to_reports()
        
        # Collect previous day reported runs using the working method
        print(f"[LOG] Extracting previous day reported runs...")
        reference_date = datetime.now()  # Use current date as reference like the working code
        all_actual_runs = scraper.extract_previous_day_reported_runs(reference_date)
        
        # Limit to first 10 runs
        actual_runs = all_actual_runs[:10] if all_actual_runs else []
        
        if all_actual_runs and len(all_actual_runs) > 10:
            print(f"[RESULTS] Found {len(all_actual_runs)} total runs, using first 10")
        
        # Stop browser
        scraper.stop_browser()
        print("[SYMBOL] Browser closed")
        
        if not actual_runs:
            print("[ERROR] No reported runs found for the previous day")
            return False
            
        print(f"[RESULTS] Collected {len(actual_runs)} reported runs")
        
        # Display summary before storing
        print("\n[LOG] COLLECTED RUNS SUMMARY:")
        print("-" * 80)
        for i, run in enumerate(actual_runs, 1):
            duration_str = f"{run.duration_minutes} min" if run.duration_minutes else "? min"
            gallons_str = f"{run.actual_gallons:.1f}g" if run.actual_gallons else "?g"
            popup_lines = len(getattr(run, 'popup_lines', [])) if hasattr(run, 'popup_lines') else 0
            
            print(f"{i:2}. {run.zone_name:<35} {run.start_time.strftime('%I:%M %p'):<8} "
                  f"{duration_str:<8} {gallons_str:<8} {popup_lines} popup lines")
        print("-" * 80)
        
        # Store in database using enhanced method
        # Note: extract_previous_day_reported_runs collects the previous day relative to reference_date
        actual_collection_date = (reference_date - timedelta(days=1)).date()
        print(f"\n[SAVED] Storing runs in database for {actual_collection_date}...")
        stored_count = storage.store_actual_runs_enhanced(actual_runs, actual_collection_date)
        
        print(f"[OK] Successfully stored {stored_count}/{len(actual_runs)} reported runs")
        print(f"[DATE] Data stored for: {actual_collection_date}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error collecting reported data: {e}")
        import traceback
        traceback.print_exc()
        
        # Clean up browser if still running
        try:
            if 'scraper' in locals():
                scraper.stop_browser()
        except:
            pass
            
        return False

def main():
    """Run the reported data collection"""
    try:
        success = collect_reported_data()
        
        if success:
            print("\n[SUCCESS] Reported data collection completed successfully!")
            print("[INFO] Next steps:")
            print("   - Review the stored data")
            print("   - Run matching algorithm")
            print("   - Generate mismatch report")
        else:
            print("\n[SYMBOL] Reported data collection failed")
            
    except KeyboardInterrupt:
        print("\n[SYMBOL] Collection interrupted by user")
    except Exception as e:
        print(f"\n[SYMBOL] Unexpected error: {e}")

if __name__ == "__main__":
    main()
