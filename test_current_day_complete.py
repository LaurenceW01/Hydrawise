#!/usr/bin/env python3
"""
Test Current Day Complete Data Collection

Tests that we can successfully collect both today's schedule and today's actual runs
using the proven working methods.

Author: AI Assistant
Date: 2025-08-21
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Import our scraper
from hydrawise_web_scraper import HydrawiseWebScraper

def main():
    """Test current day complete data collection"""
    
    # Load environment variables
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("Error: HYDRAWISE_USER and HYDRAWISE_PASSWORD must be set in .env file")
        return
        
    print("Testing Current Day Complete Data Collection")
    print("=" * 55)
    
    # Create scraper
    scraper = HydrawiseWebScraper(username, password, headless=True)
    
    try:
        # Start browser and login
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Failed to login to Hydrawise portal")
            
        scraper.navigate_to_reports()
        
        # Test 1: Today's scheduled runs (this worked!)
        print("\n🗓️  TESTING TODAY'S SCHEDULED RUNS...")
        today = datetime.now()
        scheduled_runs = scraper.extract_scheduled_runs(today)
        
        print(f"✅ Scheduled runs collected: {len(scheduled_runs)}")
        if scheduled_runs:
            print(f"   Sample: {scheduled_runs[0].zone_name} at {scheduled_runs[0].start_time.strftime('%I:%M%p')} for {scheduled_runs[0].duration_minutes}min")
            if len(scheduled_runs) > 1:
                print(f"           {scheduled_runs[-1].zone_name} at {scheduled_runs[-1].start_time.strftime('%I:%M%p')} for {scheduled_runs[-1].duration_minutes}min")
        
        # Test 2: Today's actual runs
        print(f"\n📊 TESTING TODAY'S ACTUAL RUNS...")
        actual_runs = scraper.extract_actual_runs(today)
        
        print(f"✅ Actual runs collected: {len(actual_runs)}")
        if actual_runs:
            print(f"   Sample: {actual_runs[0].zone_name} at {actual_runs[0].start_time.strftime('%I:%M%p')} for {actual_runs[0].duration_minutes}min")
            if actual_runs[0].actual_gallons:
                print(f"           Water used: {actual_runs[0].actual_gallons:.1f} gallons")
            
            if len(actual_runs) > 1:
                print(f"           {actual_runs[-1].zone_name} at {actual_runs[-1].start_time.strftime('%I:%M%p')} for {actual_runs[-1].duration_minutes}min")
                if actual_runs[-1].actual_gallons:
                    print(f"           Water used: {actual_runs[-1].actual_gallons:.1f} gallons")
        
        # Calculate totals
        total_water = sum(run.actual_gallons or 0 for run in actual_runs)
        
        print(f"\n📈 SUMMARY:")
        print(f"   Scheduled for today: {len(scheduled_runs)} runs")
        print(f"   Completed so far: {len(actual_runs)} runs") 
        print(f"   Total water delivered: {total_water:.1f} gallons")
        
        # Check for any failures
        runs_with_water = len([r for r in actual_runs if r.actual_gallons])
        print(f"   Runs with water data: {runs_with_water}/{len(actual_runs)}")
        
        if len(scheduled_runs) > 0 and len(actual_runs) > 0:
            print(f"\n✅ SUCCESS: Both scheduled and actual data collection working!")
            print(f"   Core monitoring capability: OPERATIONAL")
        elif len(scheduled_runs) > 0:
            print(f"\n⚠️  PARTIAL: Schedule collection working, actual runs may be limited")
            print(f"   (This is normal if few zones have run today)")
        else:
            print(f"\n❌ ISSUE: Schedule collection failed")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        try:
            scraper.stop_browser()
        except:
            pass

if __name__ == "__main__":
    main()
