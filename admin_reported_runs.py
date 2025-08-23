#!/usr/bin/env python3
"""
Admin CLI for Reported Runs Collection

Provides command-line interface for manual control of reported runs collection:
- Daily collection (previous day + current day)
- Periodic collection (current day deltas)
- Admin override collection (any date)
- Status monitoring

Author: AI Assistant
Date: 2025-08-23
"""

import argparse
import sys
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reported_runs_manager import ReportedRunsManager, CollectionMode

def print_banner():
    """Print the admin banner"""
    print("=" * 70)
    print("🚰 HYDRAWISE REPORTED RUNS ADMIN")
    print("=" * 70)

def print_result(result, title: str):
    """Print collection result in a nice format"""
    print(f"\n📊 {title}")
    print("-" * 50)
    print(f"Mode: {result.mode.value}")
    print(f"Success: {'✅ Yes' if result.success else '❌ No'}")
    print(f"Collection Date: {result.collection_date}")
    print(f"Runs Collected: {result.runs_collected}")
    print(f"Runs Stored: {result.runs_stored}")
    print(f"Duration: {(result.end_time - result.start_time).total_seconds():.1f} seconds")
    
    if result.details:
        print(f"Details: {result.details}")
    
    if result.errors:
        print(f"❌ Errors:")
        for error in result.errors:
            print(f"   - {error}")

def cmd_daily(args):
    """Execute daily collection"""
    print_banner()
    print("🌅 DAILY COLLECTION - Previous Day + Current Day")
    
    manager = ReportedRunsManager(headless=not args.visible)
    result = manager.collect_daily(force=args.force)
    
    print_result(result, "Daily Collection Results")
    
    return 0 if result.success else 1

def cmd_periodic(args):
    """Execute periodic collection"""
    print_banner()
    print("🔄 PERIODIC COLLECTION - Current Day Delta Updates")
    
    manager = ReportedRunsManager(headless=not args.visible)
    result = manager.collect_periodic(min_interval_minutes=args.interval)
    
    print_result(result, "Periodic Collection Results")
    
    return 0 if result.success else 1

def cmd_admin(args):
    """Execute admin override collection"""
    print_banner()
    print(f"👤 ADMIN COLLECTION - Manual Override for {args.date}")
    
    # Parse target date
    try:
        if args.date == "yesterday":
            target_date = date.today() - timedelta(days=1)
        elif args.date == "today":
            target_date = date.today()
        else:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    except ValueError:
        print(f"❌ Invalid date format: {args.date}")
        print("   Use YYYY-MM-DD format, 'today', or 'yesterday'")
        return 1
    
    manager = ReportedRunsManager(headless=not args.visible)
    result = manager.collect_admin(target_date, limit_zones=args.limit)
    
    print_result(result, f"Admin Collection Results for {target_date}")
    
    return 0 if result.success else 1

def cmd_status(args):
    """Show collection status"""
    print_banner()
    print("📊 COLLECTION STATUS")
    
    try:
        manager = ReportedRunsManager()
        status = manager.get_collection_status()
        
        print(f"\n🕐 Current Time: {status['current_time']}")
        
        print(f"\n🌅 Daily Collection:")
        daily = status['daily_collection']
        print(f"   Last Run: {daily['last_run'] or 'Never'}")
        print(f"   Completed Today: {'✅ Yes' if daily['completed_today'] else '❌ No'}")
        print(f"   Next Recommended: {daily['next_recommended']}")
        
        print(f"\n🔄 Periodic Collection:")
        periodic = status['periodic_collection']
        print(f"   Last Run: {periodic['last_run'] or 'Never'}")
        print(f"   Completed Today: {'✅ Yes' if periodic['completed_today'] else '❌ No'}")
        print(f"   Next Recommended: {periodic['next_recommended'] or 'Available now'}")
        
        print(f"\n🗄️  Database Status:")
        db_info = status['database_info']
        print(f"   Total Scheduled Runs: {db_info.get('scheduled_runs_count', 0)}")
        print(f"   Total Actual Runs: {db_info.get('actual_runs_count', 0)}")
        print(f"   Database Path: {db_info.get('database_path', 'Unknown')}")
        print(f"   Cloud Sync: {'✅ Enabled' if db_info.get('cloud_sync_enabled') else '❌ Disabled'}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to get status: {e}")
        return 1

def cmd_test(args):
    """Test the system with a small collection"""
    print_banner()
    print("🧪 TEST MODE - Small Collection Sample")
    
    try:
        manager = ReportedRunsManager(headless=not args.visible)
        
        # Test with yesterday, limit to 3 zones
        yesterday = date.today() - timedelta(days=1)
        result = manager.collect_admin(yesterday, limit_zones=3)
        
        print_result(result, f"Test Collection Results for {yesterday} (3 zones)")
        
        if result.success:
            print("\n🎉 Test completed successfully!")
            print("   The system is working and ready for normal operations.")
        else:
            print("\n⚠️  Test completed with errors.")
            print("   Check the error messages above for troubleshooting.")
        
        return 0 if result.success else 1
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1

def main():
    """Main CLI entry point"""
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Admin CLI for Hydrawise Reported Runs Collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show current status
  python admin_reported_runs.py status
  
  # Run daily collection (previous day + current day)
  python admin_reported_runs.py daily
  
  # Run periodic collection (current day deltas)
  python admin_reported_runs.py periodic
  
  # Admin collection for specific date
  python admin_reported_runs.py admin yesterday
  python admin_reported_runs.py admin 2025-08-22
  
  # Test the system
  python admin_reported_runs.py test
        """
    )
    
    # Global options
    parser.add_argument('--visible', action='store_true', 
                       help='Show browser window (default: headless)')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Daily collection
    daily_parser = subparsers.add_parser('daily', help='Run daily collection (previous day + current day)')
    daily_parser.add_argument('--force', action='store_true',
                             help='Force collection even if already done today')
    daily_parser.set_defaults(func=cmd_daily)
    
    # Periodic collection
    periodic_parser = subparsers.add_parser('periodic', help='Run periodic collection (current day deltas)')
    periodic_parser.add_argument('--interval', type=int, default=30,
                                help='Minimum interval in minutes between collections (default: 30)')
    periodic_parser.set_defaults(func=cmd_periodic)
    
    # Admin collection
    admin_parser = subparsers.add_parser('admin', help='Run admin collection for specific date')
    admin_parser.add_argument('date', help='Date to collect (YYYY-MM-DD, "today", or "yesterday")')
    admin_parser.add_argument('--limit', type=int,
                             help='Limit number of zones to process (for testing)')
    admin_parser.set_defaults(func=cmd_admin)
    
    # Status
    status_parser = subparsers.add_parser('status', help='Show collection status')
    status_parser.set_defaults(func=cmd_status)
    
    # Test
    test_parser = subparsers.add_parser('test', help='Test the system with small collection')
    test_parser.set_defaults(func=cmd_test)
    
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
