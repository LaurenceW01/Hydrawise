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
        else:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    except ValueError:
        print(f"❌ Invalid date format: {args.date}")
        print("   Use YYYY-MM-DD format, 'today', or 'tomorrow'")
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
        scraper = HydrawiseWebScraper(username, password, headless=not args.visible)
        
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Login failed - check credentials")
        
        print("📊 Navigating to reports...")
        scraper.navigate_to_reports()
        
        # Collect scheduled runs
        print(f"📋 Collecting scheduled runs for {target_date}...")
        target_datetime = datetime.combine(target_date, datetime.min.time())
        scheduled_runs = scraper.extract_scheduled_runs(target_datetime, limit_zones=args.limit)
        
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
        stored_count = storage.store_scheduled_runs_enhanced(scheduled_runs, target_date)
        print(f"✅ Stored {stored_count} runs successfully")
        
        # Display summary
        print()
        print("📊 COLLECTION SUMMARY:")
        print(f"   Date: {target_date}")
        print(f"   Runs collected: {len(scheduled_runs)}")
        print(f"   Runs stored: {stored_count}")
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

def main():
    """Main CLI entry point"""
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Admin CLI for Hydrawise Schedule Collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect all scheduled runs for today
  python admin_schedule_collection.py collect today
  
  # Collect first 5 zones for testing
  python admin_schedule_collection.py collect today --limit 5
  
  # Clear existing data and collect all runs
  python admin_schedule_collection.py collect today --clear
  
  # Collect tomorrow's schedule
  python admin_schedule_collection.py collect tomorrow
  
  # Check database status
  python admin_schedule_collection.py status
  
  # Clear scheduled runs for specific date
  python admin_schedule_collection.py clear today --force
        """
    )
    
    # Global options
    parser.add_argument('--visible', action='store_true',
                       help='Run browser in visible mode (default: headless)')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Collect command
    collect_parser = subparsers.add_parser('collect', help='Collect scheduled runs')
    collect_parser.add_argument('date', help='Date to collect (YYYY-MM-DD, "today", or "tomorrow")')
    collect_parser.add_argument('--limit', type=int,
                               help='Limit number of zones to collect (default: all)')
    collect_parser.add_argument('--clear', action='store_true',
                               help='Clear existing data before collection')
    collect_parser.set_defaults(func=cmd_collect)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show database status')
    status_parser.set_defaults(func=cmd_status)
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear scheduled runs for date')
    clear_parser.add_argument('date', help='Date to clear (YYYY-MM-DD, "today", or "tomorrow")')
    clear_parser.add_argument('--force', action='store_true',
                             help='Skip confirmation prompt')
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
