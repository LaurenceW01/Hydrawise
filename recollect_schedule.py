#!/usr/bin/env python3
"""
Admin Schedule Collection

Collect scheduled runs with configurable zone limits
- Default: collect ALL scheduled runs
- Optional: limit to specific number of zones for testing
"""

import os
import sys
import argparse
from datetime import datetime, date
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hydrawise_web_scraper_refactored import HydrawiseWebScraper
from database.universal_database_manager import get_universal_database_manager

def recollect_schedule(limit_zones: int = None):
    """Re-collect and store scheduled runs
    
    Args:
        limit_zones: Optional limit on number of zones to collect (None = all zones)
    """
    
    print("Re-collecting first 10 scheduled runs for proper ordering...")
    
    # Load credentials
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("Missing credentials")
        return False
        
    try:
        # Clear today's data first
        storage = get_universal_database_manager()
        deleted_count = storage.delete_scheduled_runs_for_date(date.today())
        print(f"Cleared {deleted_count} existing scheduled runs for today")
        
        # Re-collect data
        scraper = HydrawiseWebScraper(username, password, headless=True)
        
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Login failed")
            
        scraper.navigate_to_reports()
        
        # Get exactly 10 runs
        scheduled_runs = scraper.extract_scheduled_runs(datetime.now(), limit_zones=10)
        scraper.stop_browser()
        
        print(f"Collected {len(scheduled_runs)} runs")
        
        # Store with universal database manager
        stored_count = storage.insert_scheduled_runs(scheduled_runs, date.today())
        print(f"Stored {stored_count} runs successfully")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        try:
            if 'scraper' in locals():
                scraper.stop_browser()
        except:
            pass
        return False

if __name__ == "__main__":
    recollect_schedule()
