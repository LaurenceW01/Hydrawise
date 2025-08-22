#!/usr/bin/env python3
"""
Test script for previous day reported data collection
Shows actual irrigation runs from the previous day with duration, water usage, and status.
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path to import our modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from hydrawise_web_scraper_refactored import HydrawiseWebScraper

def format_reported_data(reported_runs, logger, reference_date):
    """Format reported data into readable table and log it"""
    
    # Create readable output
    output_lines = []
    output_lines.append("="*80)
    output_lines.append("📅 HYDRAWISE PREVIOUS DAY REPORTED RUNS")
    output_lines.append(f"🔍 Reference Date: {reference_date.strftime('%Y-%m-%d')}")
    output_lines.append(f"📊 Collecting: Previous day's actual irrigation data")
    output_lines.append("="*80)
    output_lines.append("")
    
    if reported_runs:
        output_lines.append("🚿 PREVIOUS DAY'S ACTUAL IRRIGATION RUNS:")
        output_lines.append("-" * 140)
        output_lines.append(f"{'Zone Name':<35} {'Start Time':<12} {'Duration':<10} {'Water Usage':<15} {'Status':<20} {'Notes':<40}")
        output_lines.append("-" * 140)
        
        total_duration = 0
        total_water = 0
        failures = 0
        
        for run in reported_runs:
            zone_name = run.zone_name if hasattr(run, 'zone_name') else 'Unknown Zone'
            start_time_str = run.start_time.strftime('%I:%M %p') if hasattr(run, 'start_time') else 'Unknown'
            duration_str = f"{run.duration_minutes} min" if hasattr(run, 'duration_minutes') else 'Unknown'
            water_str = f"{run.actual_gallons:.2f} gal" if hasattr(run, 'actual_gallons') and run.actual_gallons else 'N/A'
            status_str = run.status if hasattr(run, 'status') else 'Unknown'
            notes_str = (run.notes if hasattr(run, 'notes') and run.notes else 'No notes')[:37] + "..."
            
            # Truncate long zone names
            display_zone = zone_name[:34] + "..." if len(zone_name) > 34 else zone_name
            
            # Check for failures
            if hasattr(run, 'failure_reason') and run.failure_reason:
                failures += 1
                status_str = f"❌ {status_str}"
            elif 'normal' in status_str.lower():
                status_str = f"✅ {status_str}"
            
            output_lines.append(f"{display_zone:<35} {start_time_str:<12} {duration_str:<10} {water_str:<15} {status_str:<20} {notes_str:<40}")
            
            # Track totals
            if hasattr(run, 'duration_minutes') and run.duration_minutes:
                total_duration += run.duration_minutes
            if hasattr(run, 'actual_gallons') and run.actual_gallons:
                total_water += run.actual_gallons
        
        output_lines.append("-" * 140)
        output_lines.append(f"📊 SUMMARY:")
        output_lines.append(f"   Total Runs: {len(reported_runs)}")
        output_lines.append(f"   Total Duration: {total_duration} minutes ({total_duration/60:.1f} hours)")
        output_lines.append(f"   Total Water Usage: {total_water:.2f} gallons")
        output_lines.append(f"   Failures/Issues: {failures}")
        
        if failures > 0:
            output_lines.append("")
            output_lines.append("⚠️  FAILURE ANALYSIS:")
            for run in reported_runs:
                if hasattr(run, 'failure_reason') and run.failure_reason:
                    output_lines.append(f"   • {run.zone_name}: {run.failure_reason}")
    else:
        output_lines.append("❌ No reported runs found for previous day")
        output_lines.append("   This could mean:")
        output_lines.append("   • No irrigation occurred on previous day")
        output_lines.append("   • Navigation to previous day failed")
        output_lines.append("   • Page structure has changed")
    
    output_lines.append("")
    output_lines.append("="*80)
    
    # Log all the formatted output
    for line in output_lines:
        logger.info(line)

def main():
    """Run the previous day reported data test"""
    
    # Setup logging to capture to file with minimal console output
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Ensure logs directory exists
    logs_dir = os.path.join(parent_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    log_filename = os.path.join(logs_dir, f"previous_day_reported_{timestamp}.log")
    
    # Create a dedicated logger ONLY for our readable output
    logger = logging.getLogger('previous_day_reported')
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers to prevent interference
    logger.handlers.clear()
    
    # File handler ONLY for our readable output
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(message)s')  # Simple format for readable output
    file_handler.setFormatter(file_formatter)
    
    # Only add file handler - no console handler to avoid mixing outputs
    logger.addHandler(file_handler)
    
    # Prevent propagation to root logger to avoid capturing system logs
    logger.propagate = False
    
    print("🔄 Starting previous day reported data collection...")
    print("📝 Results will be saved to:", log_filename)
    print()
    
    try:
        # Load credentials from .env file
        load_dotenv()
        username = os.getenv('HYDRAWISE_USER')
        password = os.getenv('HYDRAWISE_PASSWORD')
        
        if not username or not password:
            raise Exception("Please set HYDRAWISE_USER and HYDRAWISE_PASSWORD in .env file")
        
        # Initialize scraper with visible browser for debugging
        scraper = HydrawiseWebScraper(username, password, headless=False)
        
        # Use current date as reference
        reference_date = datetime.now()
        print(f"🔄 Collecting previous day's reported runs (reference: {reference_date.strftime('%Y-%m-%d')})...")
        
        # Start browser and login
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Failed to login")
            
        # Navigate to reports
        scraper.navigate_to_reports()
        
        # Extract previous day's reported runs
        reported_runs = scraper.extract_previous_day_reported_runs(reference_date)
        
        # Debug: Let's see what we actually got
        print(f"DEBUG: Extracted {len(reported_runs)} reported run objects")
        for i, run in enumerate(reported_runs[:3]):  # Show first 3
            print(f"  {i+1}: {type(run)} - {run}")
            if hasattr(run, 'zone_name'):
                print(f"       zone_name: '{run.zone_name}'")
            if hasattr(run, 'start_time'):
                print(f"       start_time: {run.start_time}")
            if hasattr(run, 'duration_minutes'):
                print(f"       duration: {run.duration_minutes} min")
            if hasattr(run, 'actual_gallons'):
                print(f"       water: {run.actual_gallons} gal")
                
        # Display in readable format and save to log
        format_reported_data(reported_runs, logger, reference_date)
        
        # Cleanup browser
        scraper.stop_browser()
        
        logger.info("✅ Previous day reported data collection completed successfully")
        print("✅ Previous day reported data saved to log file:", log_filename)
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        print(f"\n❌ Error: {e}")
        print("📝 Check the log file for detailed error information:", log_filename)

if __name__ == "__main__":
    main()
