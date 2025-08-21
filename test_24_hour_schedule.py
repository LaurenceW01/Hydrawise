#!/usr/bin/env python3
"""
Test 24-Hour Schedule Collection

Tests the new date navigation and 24-hour schedule collection functionality.

Author: AI Assistant
Date: 2025-08-21
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import our scraper
from hydrawise_web_scraper import HydrawiseWebScraper

def main():
    """Test 24-hour schedule collection"""
    
    # Load environment variables
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("Error: HYDRAWISE_USER and HYDRAWISE_PASSWORD must be set in .env file")
        return
        
    print("Testing 24-Hour Schedule Collection")
    print("=" * 50)
    
    # Create scraper
    scraper = HydrawiseWebScraper(username, password, headless=True)
    
    try:
        # Start browser and login
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Failed to login to Hydrawise portal")
            
        # Test 24-hour schedule collection
        print("\nTesting 24-hour schedule collection...")
        schedule_results = scraper.collect_24_hour_schedule()
        
        if schedule_results['errors']:
            print(f"❌ Errors encountered: {schedule_results['errors']}")
        else:
            print("✅ 24-hour collection successful!")
            
        # Display results
        today_count = len(schedule_results['today'])
        tomorrow_count = len(schedule_results['tomorrow'])
        
        print(f"\n📊 SCHEDULE RESULTS:")
        print(f"Collection time: {schedule_results['collection_time'].strftime('%I:%M%p')}")
        print(f"Today ({schedule_results['start_date']}): {today_count} scheduled runs")
        print(f"Tomorrow ({schedule_results['tomorrow_date']}): {tomorrow_count} scheduled runs")
        
        # Show today's schedule summary
        if schedule_results['today']:
            print(f"\n📅 TODAY'S SCHEDULE:")
            for i, run in enumerate(schedule_results['today'][:5], 1):  # Show first 5
                print(f"  {i}. {run.zone_name} at {run.start_time.strftime('%I:%M%p')} for {run.duration_minutes}min")
            if today_count > 5:
                print(f"  ... and {today_count - 5} more runs")
        else:
            print(f"\n📅 No scheduled runs for today")
            
        # Show tomorrow's schedule summary
        if schedule_results['tomorrow']:
            print(f"\n📅 TOMORROW'S SCHEDULE:")
            for i, run in enumerate(schedule_results['tomorrow'][:5], 1):  # Show first 5
                print(f"  {i}. {run.zone_name} at {run.start_time.strftime('%I:%M%p')} for {run.duration_minutes}min")
            if tomorrow_count > 5:
                print(f"  ... and {tomorrow_count - 5} more runs")
        else:
            print(f"\n📅 No scheduled runs for tomorrow")
            
        # Test date navigation separately
        print(f"\n🧭 Testing date navigation...")
        tomorrow = datetime.now() + timedelta(days=1)
        
        # Navigate to reports page
        scraper.navigate_to_reports()
        
        # Test getting current displayed date
        current_date = scraper.get_current_displayed_date()
        print(f"Current displayed date: '{current_date}'")
        
        # Test navigation to tomorrow
        print(f"Navigating to tomorrow ({tomorrow.date()})...")
        if scraper.navigate_to_date(tomorrow):
            new_date = scraper.get_current_displayed_date()
            print(f"✅ Navigation successful! Now showing: '{new_date}'")
            
            # Navigate back to today
            today = datetime.now()
            print(f"Navigating back to today ({today.date()})...")
            if scraper.navigate_to_date(today):
                back_date = scraper.get_current_displayed_date()
                print(f"✅ Navigation back successful! Now showing: '{back_date}'")
            else:
                print("❌ Failed to navigate back to today")
        else:
            print("❌ Failed to navigate to tomorrow")
            
        print(f"\n✅ Test completed successfully!")
        print(f"   Total scheduled runs collected: {today_count + tomorrow_count}")
        print(f"   Date navigation: Working")
        
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
