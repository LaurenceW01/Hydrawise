#!/usr/bin/env python3
"""
Test script to display schedule data in human-readable format
Shows: Zone | Date | Start Time | Duration
"""

import sys
import os
import logging
import re
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path to import our modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from hydrawise_web_scraper_refactored import HydrawiseWebScraper

def format_schedule_data(results, logger):
    """Format schedule data into readable table and log it"""
    
    # Create readable output
    output_lines = []
    output_lines.append("="*80)
    output_lines.append("📅 HYDRAWISE IRRIGATION SCHEDULE - READABLE FORMAT")
    output_lines.append("🔧 FULL 24-HOUR SCHEDULE: Today + Tomorrow, All zones, Visible browser")
    output_lines.append("="*80)
    
    # Rain sensor status
    if results.get('rain_sensor_active'):
        output_lines.append(f"🌧️  RAIN SENSOR: {results.get('sensor_status', 'Unknown')}")
        output_lines.append("⚠️  All zones suspended due to rain sensor")
    else:
        output_lines.append(f"☀️  RAIN SENSOR: {results.get('sensor_status', 'Testing mode - full collection')}")
    
    output_lines.append("")
    
    # Today's schedule
    if results.get('today'):
        output_lines.append("📅 TODAY'S SCHEDULE:")
        output_lines.append("-" * 120)
        output_lines.append(f"{'Zone Name':<30} {'Date':<12} {'Start Time':<12} {'Duration':<10} {'Popup Text':<50}")
        output_lines.append("-" * 120)
        
        for run in results['today']:
            zone_name = run.zone_name if hasattr(run, 'zone_name') else 'Unknown Zone'
            
            # Clean up zone name if it has time prefix (like "3:30amFront Right Turf")
            clean_zone_name = zone_name
            time_pattern = r'^\d{1,2}:\d{2}[ap]m(.*)$'
            match = re.match(time_pattern, zone_name, re.IGNORECASE)
            if match:
                clean_zone_name = match.group(1).strip()
                
            date_str = run.start_time.strftime('%Y-%m-%d') if hasattr(run, 'start_time') else 'Unknown'
            time_str = run.start_time.strftime('%I:%M %p') if hasattr(run, 'start_time') else 'Unknown'
            duration_str = f"{run.duration_minutes} min" if hasattr(run, 'duration_minutes') else 'Unknown'
            popup_text = (run.notes if hasattr(run, 'notes') and run.notes else 'No popup data')[:47] + "..."
            
            output_lines.append(f"{clean_zone_name:<30} {date_str:<12} {time_str:<12} {duration_str:<10} {popup_text:<50}")
        
        output_lines.append(f"\nTotal Today: {len(results['today'])} runs")
    
    output_lines.append("")
    
    # Tomorrow's schedule  
    if results.get('tomorrow'):
        output_lines.append("📅 TOMORROW'S SCHEDULE:")
        output_lines.append("-" * 120)
        output_lines.append(f"{'Zone Name':<30} {'Date':<12} {'Start Time':<12} {'Duration':<10} {'Popup Text':<50}")
        output_lines.append("-" * 120)
        
        for run in results['tomorrow']:
            zone_name = run.zone_name if hasattr(run, 'zone_name') else 'Unknown Zone'
            
            # Clean up zone name if it has time prefix (like "3:30amFront Right Turf")
            clean_zone_name = zone_name
            time_pattern = r'^\d{1,2}:\d{2}[ap]m(.*)$'
            match = re.match(time_pattern, zone_name, re.IGNORECASE)
            if match:
                clean_zone_name = match.group(1).strip()
                
            date_str = run.start_time.strftime('%Y-%m-%d') if hasattr(run, 'start_time') else 'Unknown'
            time_str = run.start_time.strftime('%I:%M %p') if hasattr(run, 'start_time') else 'Unknown'
            duration_str = f"{run.duration_minutes} min" if hasattr(run, 'duration_minutes') else 'Unknown'
            popup_text = (run.notes if hasattr(run, 'notes') and run.notes else 'No popup data')[:47] + "..."
            
            output_lines.append(f"{clean_zone_name:<30} {date_str:<12} {time_str:<12} {duration_str:<10} {popup_text:<50}")
        
        output_lines.append(f"\nTotal Tomorrow: {len(results['tomorrow'])} runs")
    
    # Summary
    output_lines.append("")
    output_lines.append("="*80)
    output_lines.append("📊 SUMMARY:")
    output_lines.append(f"   Today: {len(results.get('today', []))} runs")
    output_lines.append(f"   Tomorrow: {len(results.get('tomorrow', []))} runs") 
    output_lines.append(f"   Total: {len(results.get('today', [])) + len(results.get('tomorrow', []))} runs")
    if results.get('errors'):
        output_lines.append(f"   Errors: {len(results['errors'])}")
        for error in results['errors']:
            output_lines.append(f"      - {error}")
    output_lines.append("="*80)
    
    # Log all the formatted output
    for line in output_lines:
        logger.info(line)

def main():
    """Run the readable schedule test"""
    
    # Setup logging to capture to file with minimal console output
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Ensure logs directory exists
    logs_dir = os.path.join(parent_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    log_filename = os.path.join(logs_dir, f"readable_schedule_{timestamp}.log")
    
    # Create a dedicated logger ONLY for our readable output
    logger = logging.getLogger('readable_output')
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
    
    print("🔄 Starting readable schedule collection...")
    print("📝 Readable schedule will be saved to:", log_filename)
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
        
        # Collect FULL 24-hour schedule data
        print("🔄 Collecting FULL 24-hour schedule data (today + tomorrow)...")
        
        # Use the full collection method from the scraper
        results = scraper.collect_24_hour_schedule()
        
        # Debug: Let's see what we actually got
        total_runs = len(results.get('today', [])) + len(results.get('tomorrow', []))
        print(f"DEBUG: Extracted {total_runs} total schedule objects")
        print(f"       Today: {len(results.get('today', []))} runs")
        print(f"       Tomorrow: {len(results.get('tomorrow', []))} runs")
        
        # Update sensor status for full mode
        if 'sensor_status' not in results:
            results['sensor_status'] = 'Testing mode - full collection'
        
        # Display in readable format and save to log
        format_schedule_data(results, logger)
        
        # Cleanup browser
        scraper.stop_browser()
        
        logger.info("✅ Readable schedule test completed successfully")
        print("✅ Schedule data saved to log file:", log_filename)
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        print(f"\n❌ Error: {e}")
        print("📝 Check the log file for detailed error information:", log_filename)

if __name__ == "__main__":
    main()