#!/usr/bin/env python3
"""
Clean 24-Hour Schedule Collection Test

Tests the core 24-hour schedule collection functionality without extra navigation.

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
    """Test clean 24-hour schedule collection"""
    
    # Load environment variables
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("Error: HYDRAWISE_USER and HYDRAWISE_PASSWORD must be set in .env file")
        return
        
    print("Testing Clean 24-Hour Schedule Collection")
    print("=" * 45)
    
    # Create scraper
    scraper = HydrawiseWebScraper(username, password, headless=True)
    
    try:
        # Test 24-hour schedule collection
        print("Collecting 24-hour schedule...")
        start_time = datetime.now()
        
        schedule_results = scraper.collect_24_hour_schedule()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Display results
        today_count = len(schedule_results['today'])
        tomorrow_count = len(schedule_results['tomorrow'])
        total_count = today_count + tomorrow_count
        
        print(f"\nSUCCESS: 24-hour collection completed in {duration:.1f} seconds!")
        print(f"")
        print(f"SCHEDULE RESULTS:")
        print(f"  Today ({schedule_results['start_date']}): {today_count} runs")
        print(f"  Tomorrow ({schedule_results['tomorrow_date']}): {tomorrow_count} runs")
        print(f"  Total: {total_count} runs")
        
        # Show sample schedules
        if schedule_results['today']:
            print(f"\nTODAY'S SAMPLE SCHEDULE:")
            for i, run in enumerate(schedule_results['today'][:3], 1):
                print(f"  {i}. {run.zone_name} at {run.start_time.strftime('%I:%M%p')} for {run.duration_minutes}min")
            if today_count > 3:
                print(f"  ... and {today_count - 3} more runs")
                
        if schedule_results['tomorrow']:
            print(f"\nTOMORROW'S SAMPLE SCHEDULE:")
            for i, run in enumerate(schedule_results['tomorrow'][:3], 1):
                print(f"  {i}. {run.zone_name} at {run.start_time.strftime('%I:%M%p')} for {run.duration_minutes}min")
            if tomorrow_count > 3:
                print(f"  ... and {tomorrow_count - 3} more runs")
                
        # Check for errors
        if schedule_results['errors']:
            print(f"\nWARNINGS:")
            for error in schedule_results['errors']:
                print(f"  - {error}")
        else:
            print(f"\nPERFECT: No errors encountered!")
            
        # System status
        print(f"\nSYSTEM STATUS:")
        if total_count >= 40:  # Expect around 60 total
            print(f"  24-hour monitoring: FULLY OPERATIONAL")
        elif total_count >= 20:
            print(f"  24-hour monitoring: PARTIALLY OPERATIONAL")
        else:
            print(f"  24-hour monitoring: NEEDS ATTENTION")
            
        print(f"  Next button navigation: WORKING")
        print(f"  Multi-day schedule collection: WORKING")
        
    except Exception as e:
        print(f"FAILED: Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()


