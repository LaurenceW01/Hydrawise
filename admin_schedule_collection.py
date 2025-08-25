#!/usr/bin/env python3
"""
Admin CLI for Schedule Collection

Provides command-line interface for collecting scheduled irrigation runs:
- Collect all scheduled runs (default)
- Collect limited number of zones for testing
- Clear existing data before collection
- Support for different dates

Author: AI Assistant
Date: 2025-08-23
"""

import argparse
import sys
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import sqlite3

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hydrawise_web_scraper_refactored import HydrawiseWebScraper
from database.intelligent_data_storage import IntelligentDataStorage

def print_banner():
    """Print the admin banner"""
    print("=" * 70)
    print("📅 HYDRAWISE SCHEDULE COLLECTION ADMIN")
    print("=" * 70)

def cmd_collect(args):
    """Execute schedule collection"""
    print_banner()
    
    # Parse target date
    try:
        if args.date == "today":
            target_date = date.today()
        elif args.date == "tomorrow":
            target_date = date.today() + timedelta(days=1)
        elif args.date == "yesterday":
            target_date = date.today() - timedelta(days=1)
        else:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    except ValueError:
        print(f"❌ Invalid date format: {args.date}")
        print("   Use YYYY-MM-DD format, 'today', 'tomorrow', or 'yesterday'")
        return 1
    
    limit_text = f"first {args.limit} zones" if args.limit else "ALL zones"
    print(f"🔄 COLLECTING SCHEDULED RUNS - {target_date}")
    print(f"📊 Collection scope: {limit_text}")
    print()
    
    # Load credentials
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("❌ Missing credentials in .env file")
        print("   Required: HYDRAWISE_USER and HYDRAWISE_PASSWORD")
        return 1
    
    try:
        # Initialize database
        storage = IntelligentDataStorage("database/irrigation_data.db")
        
        # Clear existing data if requested
        if args.clear:
            print("🗑️  Clearing existing scheduled runs for this date...")
            with sqlite3.connect(storage.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM scheduled_runs WHERE schedule_date = ?', (target_date,))
                deleted_count = cursor.rowcount
                conn.commit()
                print(f"   Cleared {deleted_count} existing records")
        
        # Check existing data
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM scheduled_runs WHERE schedule_date = ?', (target_date,))
            existing_count = cursor.fetchone()[0]
            if existing_count > 0:
                print(f"⚠️  Found {existing_count} existing scheduled runs for {target_date}")
                if not args.clear:
                    print("   Use --clear to remove existing data before collection")
        
        # Initialize scraper
        print("🌐 Starting browser and logging in...")
        scraper = HydrawiseWebScraper(username, password, headless=args.headless)
        
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Login failed - check credentials")
        
        print("📊 Navigating to reports...")
        scraper.navigate_to_reports()
        
        # Use new shared navigation system to navigate to specific date
        print(f"📋 Navigating to {target_date} for schedule collection...")
        from shared_navigation_helper import create_navigation_helper
        nav_helper = create_navigation_helper(scraper)
        
        if not nav_helper.navigate_to_date(target_date, "schedule"):
            raise Exception(f"Failed to navigate to {target_date}")
        
        # Collect scheduled runs from the navigated date
        print(f"📋 Collecting scheduled runs for {target_date}...")
        target_datetime = datetime.combine(target_date, datetime.min.time())
        # Skip schedule tab click since we already navigated there
        scheduled_runs = scraper.extract_scheduled_runs(target_datetime, limit_zones=args.limit, skip_schedule_click=True)
        
        scraper.stop_browser()
        
        print(f"✅ Collected {len(scheduled_runs)} scheduled runs")
        
        if not scheduled_runs:
            print("⚠️  No scheduled runs found")
            print("   This could mean:")
            print("   • No irrigation scheduled for this date")
            print("   • All runs cancelled due to rain")
            print("   • Date is too far in the future")
            return 0
        
        # Store in database
        print("💾 Storing runs in database...")
        storage_result = storage.store_scheduled_runs_enhanced(scheduled_runs, target_date)
        
        # Display detailed storage results
        if isinstance(storage_result, dict):
            new_runs = storage_result['new']
            updated_runs = storage_result['updated'] 
            unchanged_runs = storage_result['unchanged']
            total_processed = storage_result['total']
            
            print(f"✅ Successfully processed {total_processed} scheduled runs:")
            print(f"   🆕 {new_runs} new runs added to database")
            print(f"   🔄 {updated_runs} existing runs updated")
            print(f"   ✓  {unchanged_runs} runs unchanged (already current)")
            print(f"   💾 Total database changes: {new_runs + updated_runs}")
        else:
            # Fallback for old format
            print(f"✅ Stored {storage_result} runs successfully")
        
        # Display summary
        print()
        print("📊 COLLECTION SUMMARY:")
        print(f"   Date: {target_date}")
        print(f"   Runs collected: {len(scheduled_runs)}")
        if isinstance(storage_result, dict):
            print(f"   New runs stored: {storage_result['new']}")
            print(f"   Runs unchanged: {storage_result['unchanged']}")
        else:
            print(f"   Runs stored: {storage_result}")
        if args.limit:
            print(f"   Zone limit: {args.limit}")
        else:
            print(f"   Zone limit: None (all zones)")
        
        # Show brief schedule
        print()
        print("📋 COLLECTED SCHEDULE:")
        print("-" * 60)
        for i, run in enumerate(scheduled_runs[:10], 1):  # Show first 10
            start_time = run.start_time.strftime('%I:%M %p')
            duration = run.duration_minutes
            print(f"   {i:2}. {run.zone_name[:35]:<35} {start_time} ({duration}min)")
        
        if len(scheduled_runs) > 10:
            print(f"   ... and {len(scheduled_runs) - 10} more runs")
        
        return 0
        
    except Exception as e:
        print(f"❌ Collection failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup browser
        try:
            if 'scraper' in locals():
                scraper.stop_browser()
        except:
            pass
        
        return 1

def cmd_status(args):
    """Show current database status"""
    print_banner()
    print("📊 DATABASE STATUS")
    print()
    
    try:
        storage = IntelligentDataStorage("database/irrigation_data.db")
        
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.cursor()
            
            # Get scheduled runs by date
            cursor.execute("""
                SELECT schedule_date, COUNT(*) as count
                FROM scheduled_runs 
                GROUP BY schedule_date 
                ORDER BY schedule_date DESC
                LIMIT 7
            """)
            
            schedule_counts = cursor.fetchall()
            
            if schedule_counts:
                print("📅 SCHEDULED RUNS BY DATE:")
                print("   " + "-" * 30)
                for schedule_date, count in schedule_counts:
                    date_obj = datetime.strptime(schedule_date, '%Y-%m-%d').date()
                    date_str = date_obj.strftime('%a %m/%d')
                    if date_obj == date.today():
                        date_str += " (Today)"
                    elif date_obj == date.today() + timedelta(days=1):
                        date_str += " (Tomorrow)"
                    print(f"   {date_str:<15} {count:>3} runs")
            else:
                print("❌ No scheduled runs found in database")
            
            # Get total counts
            cursor.execute("SELECT COUNT(*) FROM scheduled_runs")
            total_scheduled = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM actual_runs")
            total_actual = cursor.fetchone()[0]
            
            print()
            print("📊 TOTAL DATABASE CONTENTS:")
            print(f"   Scheduled runs: {total_scheduled}")
            print(f"   Actual runs: {total_actual}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        return 1

def cmd_clear(args):
    """Clear scheduled runs for specific date"""
    print_banner()
    
    # Parse target date
    try:
        if args.date == "today":
            target_date = date.today()
        elif args.date == "tomorrow":
            target_date = date.today() + timedelta(days=1)
        else:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    except ValueError:
        print(f"❌ Invalid date format: {args.date}")
        print("   Use YYYY-MM-DD format, 'today', or 'tomorrow'")
        return 1
    
    print(f"🗑️  CLEARING SCHEDULED RUNS - {target_date}")
    print()
    
    try:
        storage = IntelligentDataStorage("database/irrigation_data.db")
        
        # Check what exists
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM scheduled_runs WHERE schedule_date = ?', (target_date,))
            existing_count = cursor.fetchone()[0]
            
            if existing_count == 0:
                print(f"ℹ️  No scheduled runs found for {target_date}")
                return 0
            
            print(f"📊 Found {existing_count} scheduled runs for {target_date}")
            
            if not args.force:
                response = input("⚠️  Are you sure you want to delete these runs? (y/N): ")
                if response.lower() not in ['y', 'yes']:
                    print("❌ Operation cancelled")
                    return 0
            
            # Delete runs
            cursor.execute('DELETE FROM scheduled_runs WHERE schedule_date = ?', (target_date,))
            deleted_count = cursor.rowcount
            conn.commit()
            
            print(f"✅ Deleted {deleted_count} scheduled runs for {target_date}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Clear operation failed: {e}")
        return 1

def cmd_collect_range(args):
    """Execute schedule collection for a date range"""
    print_banner()
    
    # Parse date range
    try:
        if args.start_date == "today":
            start_date = date.today()
        elif args.start_date == "tomorrow":
            start_date = date.today() + timedelta(days=1)
        elif args.start_date == "yesterday":
            start_date = date.today() - timedelta(days=1)
        else:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            
        if args.end_date == "today":
            end_date = date.today()
        elif args.end_date == "tomorrow":
            end_date = date.today() + timedelta(days=1)
        elif args.end_date == "yesterday":
            end_date = date.today() - timedelta(days=1)
        else:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
            
    except ValueError:
        print(f"❌ Invalid date format")
        print("   Use YYYY-MM-DD format, 'today', 'tomorrow', or 'yesterday'")
        return 1
    
    if start_date > end_date:
        start_date, end_date = end_date, start_date
        print(f"ℹ️  Swapped dates: collecting from {start_date} to {end_date}")
    
    date_count = (end_date - start_date).days + 1
    limit_text = f"first {args.limit} zones" if args.limit else "ALL zones"
    print(f"🔄 COLLECTING SCHEDULED RUNS - DATE RANGE")
    print(f"📅 Date range: {start_date} to {end_date} ({date_count} days)")
    print(f"📊 Collection scope: {limit_text}")
    print()
    
    # Load credentials
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or password:
        print("❌ Missing credentials in .env file")
        print("   Required: HYDRAWISE_USER and HYDRAWISE_PASSWORD")
        return 1
    
    try:
        # Initialize database
        storage = IntelligentDataStorage("database/irrigation_data.db")
        
        # Clear existing data if requested
        if args.clear:
            print("🗑️  Clearing existing scheduled runs for date range...")
            with sqlite3.connect(storage.db_path) as conn:
                cursor = conn.cursor()
                current_date = start_date
                total_deleted = 0
                while current_date <= end_date:
                    cursor.execute('DELETE FROM scheduled_runs WHERE schedule_date = ?', (current_date,))
                    total_deleted += cursor.rowcount
                    current_date += timedelta(days=1)
                conn.commit()
                print(f"   Cleared {total_deleted} existing records from {date_count} days")
        
        # Initialize scraper
        print("🌐 Starting browser and logging in...")
        scraper = HydrawiseWebScraper(username, password, headless=args.headless)
        
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Login failed - check credentials")
        
        print("📊 Navigating to reports...")
        scraper.navigate_to_reports()
        
        # Use shared navigation system to collect date range
        print(f"📋 Navigating through date range for schedule collection...")
        from shared_navigation_helper import create_navigation_helper
        nav_helper = create_navigation_helper(scraper)
        
        all_scheduled_runs = []
        collected_dates = []
        
        # Navigate through each date in the range
        current_date = start_date
        first_navigation = True
        
        while current_date <= end_date:
            print(f"\n📅 Collecting schedules for {current_date}...")
            
            if first_navigation:
                # Navigate to first date
                if not nav_helper.navigate_to_date(current_date, "schedule"):
                    print(f"❌ Failed to navigate to {current_date}")
                    current_date += timedelta(days=1)
                    continue
                first_navigation = False
            else:
                # Use Next button for subsequent dates
                if not nav_helper.click_next_button():
                    print(f"❌ Failed to navigate to {current_date}")
                    current_date += timedelta(days=1)
                    continue
            
            # Collect scheduled runs for current date
            target_datetime = datetime.combine(current_date, datetime.min.time())
            scheduled_runs = scraper.extract_scheduled_runs(target_datetime, limit_zones=args.limit, skip_schedule_click=True)
            
            if scheduled_runs:
                print(f"✅ Collected {len(scheduled_runs)} runs for {current_date}")
                all_scheduled_runs.extend(scheduled_runs)
                collected_dates.append(current_date)
                
                # Store runs for this date
                storage_result = storage.store_scheduled_runs_enhanced(scheduled_runs, current_date)
                if isinstance(storage_result, dict):
                    new_runs = storage_result['new']
                    unchanged_runs = storage_result['unchanged']
                    print(f"💾 Stored {new_runs} new runs, {unchanged_runs} unchanged for {current_date}")
                else:
                    print(f"💾 Stored {storage_result} runs for {current_date}")
            else:
                print(f"⚠️  No scheduled runs found for {current_date}")
            
            current_date += timedelta(days=1)
        
        scraper.stop_browser()
        
        # Display summary
        print()
        print("📊 COLLECTION SUMMARY:")
        print(f"   Date range: {start_date} to {end_date}")
        print(f"   Days processed: {date_count}")
        print(f"   Days with data: {len(collected_dates)}")
        print(f"   Total runs collected: {len(all_scheduled_runs)}")
        if args.limit:
            print(f"   Zone limit per day: {args.limit}")
        else:
            print(f"   Zone limit: None (all zones)")
        
        if collected_dates:
            print(f"   Successful dates: {', '.join(str(d) for d in collected_dates[:5])}")
            if len(collected_dates) > 5:
                print(f"                     ... and {len(collected_dates) - 5} more")
        
        return 0 if collected_dates else 1
        
    except Exception as e:
        print(f"❌ Range collection failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup browser
        try:
            if 'scraper' in locals():
                scraper.stop_browser()
        except:
            pass
        
        return 1

def main():
    """Main CLI entry point"""
    # Load environment variables
    load_dotenv()
    
    # Parse arguments first to check for log file
    import sys
    
    # Quick parse to get log file argument
    temp_parser = argparse.ArgumentParser(add_help=False)
    temp_parser.add_argument('--log-file', type=str)
    temp_args, _ = temp_parser.parse_known_args()
    
    # Setup logging to file if specified
    if temp_args.log_file:
        import logging
        from datetime import datetime
        
        # Generate timestamped filename with program name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        program_name = 'schedule_collection'
        
        # If user provided a simple filename, add timestamp and program name
        if '/' not in temp_args.log_file and '\\' not in temp_args.log_file:
            # Simple filename - enhance it
            base_name = temp_args.log_file.replace('.log', '')
            enhanced_filename = f"{program_name}_{base_name}_{timestamp}.log"
        else:
            # Full path provided - use as is but ensure it's in logs if no directory
            enhanced_filename = temp_args.log_file
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(enhanced_filename)
        if not log_dir:  # If no directory specified, use logs folder
            log_dir = 'logs'
            enhanced_filename = os.path.join(log_dir, os.path.basename(enhanced_filename))
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Update the log file path
        temp_args.log_file = enhanced_filename
        
        # Setup stdout redirection to capture all print() output
        class TeeOutput:
            def __init__(self, file1, file2):
                self.file1 = file1
                self.file2 = file2

            def write(self, data):
                self.file1.write(data)
                self.file2.write(data)
                self.file1.flush()
                self.file2.flush()

            def flush(self):
                self.file1.flush()
                self.file2.flush()
        
        # Open log file and setup tee output (with UTF-8 encoding for Unicode support)
        log_file_handle = open(temp_args.log_file, 'w', encoding='utf-8')
        sys.stdout = TeeOutput(sys.stdout, log_file_handle)
        
        print(f"📋 Logging output to: {temp_args.log_file}")
        print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 50)
    
    parser = argparse.ArgumentParser(
        description="Admin CLI for Hydrawise Schedule Collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # BASIC COLLECTION:
  # Collect all scheduled runs for today (browser visible by default)
  python admin_schedule_collection.py collect today
  
  # Collect yesterday's schedule 
  python admin_schedule_collection.py collect yesterday
  
  # Collect specific date
  python admin_schedule_collection.py collect 2025-08-20
  
  # TESTING AND LIMITS:
  # Collect first 5 zones only (for testing)
  python admin_schedule_collection.py collect today --limit 5
  
  # Run in headless mode (no browser window)
  python admin_schedule_collection.py collect today --headless
  
  # OVERWRITING EXISTING DATA:
  # Delete existing data for today, then collect fresh data
  python admin_schedule_collection.py collect today --clear
  
  # DATE RANGES:
  # Collect schedules for multiple days
  python admin_schedule_collection.py collect-range yesterday today
  
  # Collect week of schedules (with testing limit)
  python admin_schedule_collection.py collect-range 2025-08-20 2025-08-26 --limit 3
  
  # DATABASE MANAGEMENT:
  # Check what's in the database
  python admin_schedule_collection.py status
  
  # Delete scheduled runs for a specific date (asks for confirmation)
  python admin_schedule_collection.py clear today
  
  # Delete scheduled runs immediately (no confirmation)
  python admin_schedule_collection.py clear today --force

OPTION EXPLANATIONS:
  --limit N     : Only collect first N zones (useful for testing)
  --clear       : Delete existing data before collecting (in collect commands)
  --force       : Skip confirmation prompts (in clear command)
  --headless    : Hide browser window during collection
  
COMMAND TYPES:
  collect       : Collect schedule data for one date
  collect-range : Collect schedule data for multiple dates
  clear         : Delete existing schedule data from database
  status        : Show what data is currently in database
        """
    )
    
    # Global options
    parser.add_argument('--headless', action='store_true',
                       help='Run browser in headless mode (default: visible)')
    parser.add_argument('--log-file', type=str,
                       help='Save all output to log file (e.g., --log-file test_run.log becomes schedule_collection_test_run_20250825_143022.log)')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Collect command
    collect_parser = subparsers.add_parser('collect', help='Collect scheduled runs')
    collect_parser.add_argument('date', help='Date to collect (YYYY-MM-DD, "today", "tomorrow", or "yesterday")')
    collect_parser.add_argument('--limit', type=int,
                               help='Limit collection to first N zones for testing (default: all zones)')
    collect_parser.add_argument('--clear', action='store_true',
                               help='Delete existing scheduled runs for this date before collecting new data')
    collect_parser.set_defaults(func=cmd_collect)
    
    # Collect range command
    collect_range_parser = subparsers.add_parser('collect-range', help='Collect scheduled runs for date range')
    collect_range_parser.add_argument('start_date', help='Start date (YYYY-MM-DD, "today", "tomorrow", or "yesterday")')
    collect_range_parser.add_argument('end_date', help='End date (YYYY-MM-DD, "today", "tomorrow", or "yesterday")')
    collect_range_parser.add_argument('--limit', type=int,
                                    help='Limit collection to first N zones per day for testing (default: all zones)')
    collect_range_parser.add_argument('--clear', action='store_true',
                                    help='Delete existing scheduled runs for entire date range before collecting new data')
    collect_range_parser.set_defaults(func=cmd_collect_range)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show database status')
    status_parser.set_defaults(func=cmd_status)
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear scheduled runs for date')
    clear_parser.add_argument('date', help='Date to clear (YYYY-MM-DD, "today", or "tomorrow")')
    clear_parser.add_argument('--force', action='store_true',
                             help='Skip "Are you sure?" confirmation prompt and delete immediately')
    clear_parser.set_defaults(func=cmd_clear)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n\n⏹️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
