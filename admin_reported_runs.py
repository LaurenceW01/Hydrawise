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
from typing import List
import sqlite3
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
    
    manager = ReportedRunsManager(headless=args.headless)
    result = manager.collect_daily(force=args.force)
    
    print_result(result, "Daily Collection Results")
    
    return 0 if result.success else 1

def cmd_periodic(args):
    """Execute periodic collection"""
    print_banner()
    print("🔄 PERIODIC COLLECTION - Current Day Delta Updates")
    
    manager = ReportedRunsManager(headless=args.headless)
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
    
    manager = ReportedRunsManager(headless=args.headless)
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
        manager = ReportedRunsManager(headless=args.headless)
        
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

def cmd_update(args):
    """Update/refresh current day's reported runs"""
    print_banner()
    print("🔄 UPDATING CURRENT DAY'S REPORTED RUNS")
    print()
    
    try:
        manager = ReportedRunsManager(headless=args.headless)
        
        # Use admin collection for today to get fresh data
        target_date = date.today()
        print(f"📅 Updating reported runs for {target_date}")
        print("   This will collect the latest run data and update deltas")
        print()
        
        # Run collection for today with no zone limit (get all fresh data)
        result = manager.collect_admin(target_date, limit_zones=args.limit if hasattr(args, 'limit') and args.limit else None)
        
        print_result(result, "UPDATE RESULTS")
        
        if result.success:
            # Extract storage details for better reporting
            storage_details = result.details.get('storage_breakdown', {})
            
            if isinstance(storage_details, dict) and 'new' in storage_details:
                # New detailed breakdown
                new_runs = storage_details['new']
                updated_runs = storage_details['updated']
                unchanged_runs = storage_details['unchanged']
                total_processed = storage_details['total']
                
                print(f"\n✅ Successfully processed {total_processed} reported runs for today:")
                print(f"   🆕 {new_runs} new runs added to database")
                print(f"   🔄 {updated_runs} existing runs updated")
                print(f"   ✓  {unchanged_runs} runs unchanged (already current)")
                print(f"   💾 Total database changes: {new_runs + updated_runs}")
            else:
                # Fallback to old format
                print(f"\n✅ Successfully updated {result.runs_stored} reported runs for today")
                if result.runs_collected != result.runs_stored:
                    print(f"   📊 {result.runs_collected - result.runs_stored} runs were duplicates")
            
            print("   💡 Latest irrigation status is now available for analysis")
        else:
            print(f"\n❌ Update failed")
            if result.errors:
                print("   Check errors above for troubleshooting")
        
        return 0 if result.success else 1
        
    except Exception as e:
        print(f"❌ Update failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_yesterday(args):
    """Collect yesterday's reported runs"""
    print_banner()
    print("📅 COLLECTING YESTERDAY'S REPORTED RUNS")
    print()
    
    try:
        manager = ReportedRunsManager(headless=args.headless)
        
        # Target yesterday's date
        target_date = date.today() - timedelta(days=1)
        print(f"📅 Collecting reported runs for {target_date}")
        print("   This ensures we have complete data for yesterday")
        print()
        
        # Run collection for yesterday
        result = manager.collect_admin(target_date, limit_zones=args.limit if hasattr(args, 'limit') and args.limit else None)
        
        print_result(result, "YESTERDAY COLLECTION RESULTS")
        
        if result.success:
            # Extract storage details for better reporting
            storage_details = result.details.get('storage_breakdown', {})
            
            if isinstance(storage_details, dict) and 'new' in storage_details:
                # New detailed breakdown
                new_runs = storage_details['new']
                updated_runs = storage_details['updated']
                unchanged_runs = storage_details['unchanged']
                total_processed = storage_details['total']
                
                print(f"\n✅ Successfully processed {total_processed} reported runs for yesterday:")
                print(f"   🆕 {new_runs} new runs added to database")
                print(f"   🔄 {updated_runs} existing runs updated")
                print(f"   ✓  {unchanged_runs} runs unchanged (already current)")
                print(f"   💾 Total database changes: {new_runs + updated_runs}")
                
                if new_runs == 0 and updated_runs == 0:
                    print(f"   ✨ Yesterday's data was already complete!")
                else:
                    print(f"   📊 Yesterday's irrigation data is now complete for analysis")
            else:
                # Legacy simple count
                print(f"\n✅ Successfully collected yesterday's reported runs:")
                print(f"   💾 {result.runs_stored} runs stored in database")
            
            # Analyze zero gallon usage after data collection
            print_zero_gallon_analysis([target_date])
        
        return 0 if result.success else 1
        
    except Exception as e:
        print(f"❌ Yesterday collection failed: {e}")
        return 1

def cmd_today(args):
    """Collect today's reported runs (enhanced version of update)"""
    print_banner()
    print("📅 COLLECTING TODAY'S REPORTED RUNS")
    print()
    
    try:
        manager = ReportedRunsManager(headless=args.headless)
        
        # Use admin collection for today to get fresh data
        target_date = date.today()
        print(f"📅 Collecting reported runs for {target_date}")
        print("   This will collect all runs from today")
        print()
        
        # Run collection for today
        result = manager.collect_admin(target_date, limit_zones=args.limit if hasattr(args, 'limit') and args.limit else None)
        
        print_result(result, "TODAY COLLECTION RESULTS")
        
        if result.success:
            # Extract storage details for better reporting
            storage_details = result.details.get('storage_breakdown', {})
            
            if isinstance(storage_details, dict) and 'new' in storage_details:
                # New detailed breakdown
                new_runs = storage_details['new']
                updated_runs = storage_details['updated']
                unchanged_runs = storage_details['unchanged']
                total_processed = storage_details['total']
                
                print(f"\n✅ Successfully processed {total_processed} reported runs for today:")
                print(f"   🆕 {new_runs} new runs added to database")
                print(f"   🔄 {updated_runs} existing runs updated")
                print(f"   ✓  {unchanged_runs} runs unchanged (already current)")
                print(f"   💾 Total database changes: {new_runs + updated_runs}")
            else:
                # Legacy simple count
                print(f"\n✅ Successfully collected today's reported runs:")
                print(f"   💾 {result.runs_stored} runs stored in database")
                
            print(f"   💡 Latest irrigation status is now available for analysis")
            
            # Analyze zero gallon usage after data collection
            print_zero_gallon_analysis([target_date])
        
        return 0 if result.success else 1
        
    except Exception as e:
        print(f"❌ Today collection failed: {e}")
        return 1

def cmd_catchup(args):
    """Collect both yesterday and today's runs for complete coverage"""
    print_banner()
    print("🔄 CATCH-UP COLLECTION (YESTERDAY + TODAY)")
    print()
    
    print("This will collect both yesterday and today's runs to ensure complete coverage.")
    print()
    
    try:
        manager = ReportedRunsManager(headless=args.headless)
        
        # Collect yesterday first
        yesterday = date.today() - timedelta(days=1)
        print(f"📅 Step 1: Collecting yesterday's runs ({yesterday})...")
        
        result_yesterday = manager.collect_admin(yesterday, limit_zones=args.limit if hasattr(args, 'limit') and args.limit else None)
        
        print_result(result_yesterday, "YESTERDAY RESULTS")
        
        # Collect today
        today = date.today()
        print(f"\n📅 Step 2: Collecting today's runs ({today})...")
        
        result_today = manager.collect_admin(today, limit_zones=args.limit if hasattr(args, 'limit') and args.limit else None)
        
        print_result(result_today, "TODAY RESULTS")
        
        # Summary
        total_success = result_yesterday.success and result_today.success
        
        if total_success:
            # Calculate totals
            yesterday_details = result_yesterday.details.get('storage_breakdown', {})
            today_details = result_today.details.get('storage_breakdown', {})
            
            if isinstance(yesterday_details, dict) and isinstance(today_details, dict):
                total_new = yesterday_details.get('new', 0) + today_details.get('new', 0)
                total_updated = yesterday_details.get('updated', 0) + today_details.get('updated', 0)
                total_unchanged = yesterday_details.get('unchanged', 0) + today_details.get('unchanged', 0)
                total_processed = yesterday_details.get('total', 0) + today_details.get('total', 0)
                
                print(f"\n🎉 CATCH-UP COMPLETE!")
                print(f"   📊 Total runs processed: {total_processed}")
                print(f"   🆕 New runs added: {total_new}")
                print(f"   🔄 Runs updated: {total_updated}")
                print(f"   ✓  Runs unchanged: {total_unchanged}")
                print(f"   💾 Total database changes: {total_new + total_updated}")
                print(f"   ✨ Irrigation data is now up-to-date for analysis!")
                
                # Analyze zero gallon usage after data collection
                print_zero_gallon_analysis([yesterday, today])
        
        return 0 if total_success else 1
        
    except Exception as e:
        print(f"❌ Catch-up collection failed: {e}")
        return 1

def print_zero_gallon_analysis(analysis_dates: List[date]):
    """Analyze and report zones with 0 gallon water usage for specified dates"""
    print(f"\n🚨 ZERO GALLON USAGE ANALYSIS")
    print("=" * 60)
    
    try:
        # Import database manager for queries
        from database.database_manager import DatabaseManager
        
        db_manager = DatabaseManager()
        
        # Query zero gallon runs for the specified dates
        date_conditions = " OR ".join([f"run_date = '{d}'" for d in analysis_dates])
        
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all zero gallon runs with duration > 0 (actual irrigation attempts)
            cursor.execute(f"""
                SELECT 
                    run_date,
                    zone_name,
                    actual_duration_minutes,
                    status,
                    failure_reason,
                    abort_reason,
                    raw_popup_text
                FROM actual_runs 
                WHERE (actual_gallons = 0 OR actual_gallons IS NULL)
                  AND actual_duration_minutes > 0
                  AND ({date_conditions})
                ORDER BY run_date DESC, zone_name
            """)
            
            zero_gallon_runs = cursor.fetchall()
            
            if not zero_gallon_runs:
                print("✅ No zones reported 0 gallons during irrigation attempts")
                return
            
            # Organize data for analysis
            zones_by_date = {}
            zone_patterns = {}
            
            for run_date, zone_name, duration, status, failure_reason, abort_reason, popup_text in zero_gallon_runs:
                if run_date not in zones_by_date:
                    zones_by_date[run_date] = []
                zones_by_date[run_date].append({
                    'zone_name': zone_name,
                    'duration': duration,
                    'status': status,
                    'failure_reason': failure_reason,
                    'abort_reason': abort_reason,
                    'popup_text': popup_text
                })
                
                # Track patterns per zone
                if zone_name not in zone_patterns:
                    zone_patterns[zone_name] = {'count': 0, 'dates': [], 'reasons': []}
                zone_patterns[zone_name]['count'] += 1
                zone_patterns[zone_name]['dates'].append(run_date)
                
                # Determine likely reason for zero gallons
                reason = determine_zero_gallon_reason(status, failure_reason, abort_reason, popup_text)
                if reason not in zone_patterns[zone_name]['reasons']:
                    zone_patterns[zone_name]['reasons'].append(reason)
            
            # Print daily summary
            total_zones_affected = 0
            for run_date in sorted(zones_by_date.keys(), reverse=True):
                zones = zones_by_date[run_date]
                print(f"📅 {run_date}: {len(zones)} zones reported 0 gallons")
                total_zones_affected += len(zones)
                
                for zone in zones:
                    reason = determine_zero_gallon_reason(
                        zone['status'], zone['failure_reason'], 
                        zone['abort_reason'], zone['popup_text']
                    )
                    print(f"   • {zone['zone_name']} ({zone['duration']} min) - {reason}")
            
            print(f"\n📊 SUMMARY:")
            print(f"   Total affected zones: {total_zones_affected}")
            print(f"   Unique zones: {len(zone_patterns)}")
            
            # Pattern analysis
            print(f"\n🔍 PATTERN ANALYSIS:")
            
            # Zones with multiple zero-gallon occurrences
            repeat_offenders = {zone: data for zone, data in zone_patterns.items() if data['count'] > 1}
            if repeat_offenders:
                print(f"   🔄 Zones with repeated issues ({len(repeat_offenders)}):")
                for zone, data in repeat_offenders.items():
                    dates_str = ", ".join(data['dates'])
                    reasons_str = ", ".join(set(data['reasons']))
                    print(f"      • {zone}: {data['count']} times ({dates_str}) - {reasons_str}")
            
            # Common failure reasons
            all_reasons = []
            for data in zone_patterns.values():
                all_reasons.extend(data['reasons'])
            
            reason_counts = {}
            for reason in all_reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            
            print(f"   📋 Common causes:")
            for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"      • {reason}: {count} occurrences")
            
            # Recommendations
            print(f"\n💡 RECOMMENDATIONS:")
            if any('sensor' in reason.lower() for reason in reason_counts.keys()):
                print("   • Check flow sensors on affected zones")
            if any('abort' in reason.lower() for reason in reason_counts.keys()):
                print("   • Investigate causes of irrigation aborts")
            if any('valve' in reason.lower() for reason in reason_counts.keys()):
                print("   • Inspect valves on problem zones")
            if repeat_offenders:
                print(f"   • Priority inspection needed for: {', '.join(repeat_offenders.keys())}")
            
    except Exception as e:
        print(f"❌ Zero gallon analysis failed: {e}")
        import traceback
        traceback.print_exc()

def determine_zero_gallon_reason(status, failure_reason, abort_reason, popup_text):
    """Determine likely reason for zero gallon usage based on run data"""
    # Check for explicit reasons first
    if abort_reason:
        if 'sensor' in abort_reason.lower():
            return "Flow sensor issue"
        elif 'rain' in abort_reason.lower():
            return "Rain sensor abort"
        else:
            return f"Aborted: {abort_reason}"
    
    if failure_reason:
        if 'sensor' in failure_reason.lower():
            return "Sensor failure"
        else:
            return f"Failure: {failure_reason}"
    
    # Check status for clues
    if status and status != 'Normal watering cycle':
        if 'abort' in status.lower():
            return "Run aborted"
        elif 'sensor' in status.lower():
            return "Sensor issue"
        else:
            return f"Status: {status}"
    
    # Check popup text for additional clues
    if popup_text:
        popup_lower = popup_text.lower()
        if 'flow meter' in popup_lower or 'flow sensor' in popup_lower:
            return "Flow meter/sensor issue"
        elif 'valve' in popup_lower:
            return "Valve malfunction"
        elif 'rain' in popup_lower:
            return "Rain sensor"
        elif 'abort' in popup_lower:
            return "System abort"
    
    return "Unknown cause"

def cmd_zero_gallons(args):
    """Analyze zero gallon water usage for specified date range"""
    print_banner()
    print("🚨 ZERO GALLON WATER USAGE ANALYSIS")
    print()
    
    try:
        # Parse date range
        if args.days:
            # Use days back from today
            end_date = date.today()
            start_date = end_date - timedelta(days=args.days)
            analysis_dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        elif args.date:
            # Specific date
            if args.date == "yesterday":
                analysis_dates = [date.today() - timedelta(days=1)]
            elif args.date == "today":
                analysis_dates = [date.today()]
            else:
                target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
                analysis_dates = [target_date]
        else:
            # Default to yesterday
            analysis_dates = [date.today() - timedelta(days=1)]
        
        print(f"📅 Analyzing zero gallon usage for: {len(analysis_dates)} date(s)")
        if len(analysis_dates) == 1:
            print(f"   Date: {analysis_dates[0]}")
        else:
            print(f"   Range: {analysis_dates[0]} to {analysis_dates[-1]}")
        
        # Run the analysis
        print_zero_gallon_analysis(analysis_dates)
        
        return 0
        
    except ValueError:
        print(f"❌ Invalid date format. Use YYYY-MM-DD, 'today', or 'yesterday'")
        return 1
    except Exception as e:
        print(f"❌ Zero gallon analysis failed: {e}")
        import traceback
        traceback.print_exc()
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
  
  # Collect yesterday's runs (recommended daily task)
  python admin_reported_runs.py yesterday
  
  # Collect today's runs
  python admin_reported_runs.py today
  
  # Catch-up collection (yesterday + today)
  python admin_reported_runs.py catchup
  
  # Update current day's reported runs (refresh latest data)
  python admin_reported_runs.py update
  
  # Run daily collection (previous day + current day)
  python admin_reported_runs.py daily
  
  # Run periodic collection (current day deltas)
  python admin_reported_runs.py periodic
  
  # Admin collection for specific date (browser visible by default)
  python admin_reported_runs.py admin yesterday
  python admin_reported_runs.py admin 2025-08-22
  
  # Run in headless mode (no browser window)
  python admin_reported_runs.py update --headless
  
  # Test the system
  python admin_reported_runs.py test
  
  # Analyze zero gallon usage for yesterday
  python admin_reported_runs.py zero-gallons
  
  # Analyze zero gallon usage for specific date
  python admin_reported_runs.py zero-gallons --date 2025-08-22
  
  # Analyze zero gallon usage for last 7 days
  python admin_reported_runs.py zero-gallons --days 7
        """
    )
    
    # Global options
    parser.add_argument('--headless', action='store_true', 
                       help='Run browser in headless mode (default: visible)')
    
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
    
    # Update current day
    update_parser = subparsers.add_parser('update', help='Update/refresh current day reported runs')
    update_parser.add_argument('--limit', type=int,
                              help='Limit number of zones to process (for testing)')
    update_parser.set_defaults(func=cmd_update)
    
    # Yesterday collection
    yesterday_parser = subparsers.add_parser('yesterday', help='Collect yesterday\'s reported runs')
    yesterday_parser.add_argument('--limit', type=int,
                                 help='Limit number of zones to process (for testing)')
    yesterday_parser.set_defaults(func=cmd_yesterday)
    
    # Today collection
    today_parser = subparsers.add_parser('today', help='Collect today\'s reported runs')
    today_parser.add_argument('--limit', type=int,
                             help='Limit number of zones to process (for testing)')
    today_parser.set_defaults(func=cmd_today)
    
    # Catch-up collection (yesterday + today)
    catchup_parser = subparsers.add_parser('catchup', help='Collect both yesterday and today\'s runs for complete coverage')
    catchup_parser.add_argument('--limit', type=int,
                               help='Limit number of zones to process (for testing)')
    catchup_parser.set_defaults(func=cmd_catchup)
    
    # Status
    status_parser = subparsers.add_parser('status', help='Show collection status')
    status_parser.set_defaults(func=cmd_status)
    
    # Test
    test_parser = subparsers.add_parser('test', help='Test the system with small collection')
    test_parser.set_defaults(func=cmd_test)
    
    # Zero gallon analysis
    zero_parser = subparsers.add_parser('zero-gallons', help='Analyze zones with 0 gallon water usage')
    zero_parser.add_argument('--date', help='Date to analyze (YYYY-MM-DD, "today", or "yesterday")')
    zero_parser.add_argument('--days', type=int, help='Number of days back to analyze from today')
    zero_parser.set_defaults(func=cmd_zero_gallons)
    
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
