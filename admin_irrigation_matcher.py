#!/usr/bin/env python3
"""
Admin CLI for Irrigation Analysis

Provides command-line interface for irrigation failure detection and analysis:
- Schedule vs Actual matching analysis
- Missing run detection
- Unexpected run identification
- Failure priority assessment
- Automated analysis after data collection

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

from database.irrigation_matcher import IrrigationMatcher

def print_banner():
    """Print the admin banner"""
    print("=" * 70)
    print("🔍 HYDRAWISE IRRIGATION ANALYSIS ADMIN")
    print("=" * 70)

def cmd_analyze(args):
    """Execute irrigation analysis for a specific date"""
    print_banner()
    
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
    
    print(f"🔍 IRRIGATION ANALYSIS - {target_date}")
    print()
    
    try:
        # Initialize matcher
        matcher = IrrigationMatcher(time_tolerance_minutes=args.tolerance)
        
        # Check if we have data for this date
        scheduled_runs = matcher.load_scheduled_runs(target_date)
        actual_runs = matcher.load_actual_runs(target_date)
        
        print(f"📊 Data Available:")
        print(f"   Scheduled runs: {len(scheduled_runs)}")
        print(f"   Actual runs: {len(actual_runs)}")
        print()
        
        if not scheduled_runs and not actual_runs:
            print("⚠️  No data found for this date. Run data collection first.")
            return 1
        
        # Generate analysis report
        print("🔄 Generating irrigation analysis...")
        report = matcher.generate_match_report(target_date)
        
        # Display report
        print(report)
        
        # Save report to file if requested
        if args.save:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/irrigation_analysis_{target_date}_{timestamp}.txt"
            
            # Ensure reports directory exists
            os.makedirs("reports", exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"💾 Report saved to: {filename}")
        
        # Check for high priority alerts
        matches = matcher.match_runs(target_date)
        high_priority = [m for m in matches if m.alert_priority == "HIGH"]
        medium_priority = [m for m in matches if m.alert_priority == "MEDIUM"]
        
        if high_priority:
            print(f"\n🚨 {len(high_priority)} HIGH PRIORITY issues require immediate attention!")
            return 2  # Return code indicates high priority issues
        elif medium_priority:
            print(f"\n⚠️  {len(medium_priority)} MEDIUM PRIORITY issues found.")
            return 1  # Return code indicates medium priority issues
        else:
            print(f"\n✅ No high/medium priority issues found.")
            return 0
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_auto_analyze(args):
    """Execute automatic analysis for recent dates"""
    print_banner()
    print("🔄 AUTOMATIC IRRIGATION ANALYSIS")
    print()
    
    try:
        matcher = IrrigationMatcher(time_tolerance_minutes=args.tolerance)
        
        # Analyze the last few days
        dates_to_analyze = []
        for days_back in range(args.days):
            check_date = date.today() - timedelta(days=days_back)
            dates_to_analyze.append(check_date)
        
        total_issues = 0
        high_priority_issues = 0
        
        for check_date in dates_to_analyze:
            print(f"📅 Analyzing {check_date}...")
            
            # Check if we have data
            scheduled_runs = matcher.load_scheduled_runs(check_date)
            actual_runs = matcher.load_actual_runs(check_date)
            
            if not scheduled_runs and not actual_runs:
                print(f"   ⚠️  No data found for {check_date}")
                continue
            
            # Run analysis
            matches = matcher.match_runs(check_date)
            
            # Count issues
            missing_runs = [m for m in matches if m.match_type.value == "missing_run"]
            unexpected_runs = [m for m in matches if m.match_type.value == "unexpected_run"]
            high_alerts = [m for m in matches if m.alert_priority == "HIGH"]
            medium_alerts = [m for m in matches if m.alert_priority == "MEDIUM"]
            
            if missing_runs or unexpected_runs or high_alerts or medium_alerts:
                total_issues += len(missing_runs) + len(unexpected_runs) + len(high_alerts) + len(medium_alerts)
                high_priority_issues += len(high_alerts)
                
                print(f"   🚨 Issues found:")
                if missing_runs:
                    print(f"      ❌ Missing runs: {len(missing_runs)}")
                if unexpected_runs:
                    print(f"      ❓ Unexpected runs: {len(unexpected_runs)}")
                if high_alerts:
                    print(f"      🔥 High priority: {len(high_alerts)}")
                if medium_alerts:
                    print(f"      ⚠️  Medium priority: {len(medium_alerts)}")
            else:
                print(f"   ✅ No issues found")
        
        print()
        print("📊 AUTOMATIC ANALYSIS SUMMARY:")
        print(f"   Dates analyzed: {len(dates_to_analyze)}")
        print(f"   Total issues: {total_issues}")
        print(f"   High priority issues: {high_priority_issues}")
        
        if high_priority_issues > 0:
            print(f"\n🚨 ATTENTION: {high_priority_issues} high priority irrigation issues detected!")
            print("   Run detailed analysis: python admin_irrigation_analysis.py analyze <date>")
            return 2
        elif total_issues > 0:
            print(f"\n⚠️  {total_issues} total issues found. Review recommended.")
            return 1
        else:
            print(f"\n✅ No issues detected in recent irrigation activity.")
            return 0
        
    except Exception as e:
        print(f"❌ Automatic analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_missing_runs(args):
    """Find all missing runs (scheduled but not executed)"""
    print_banner()
    print("❌ MISSING RUNS ANALYSIS")
    print()
    
    try:
        # Parse date range
        if args.start_date == "week":
            start_date = date.today() - timedelta(days=7)
        else:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        
        end_date = date.today() if not args.end_date else datetime.strptime(args.end_date, '%Y-%m-%d').date()
        
        print(f"🔍 Searching for missing runs from {start_date} to {end_date}")
        print()
        
        matcher = IrrigationMatcher(time_tolerance_minutes=args.tolerance)
        
        all_missing = []
        dates_checked = 0
        
        current_date = start_date
        while current_date <= end_date:
            # Only check past dates (can't expect future scheduled runs to have run yet)
            if current_date < date.today():
                matches = matcher.match_runs(current_date)
                missing_runs = [m for m in matches if m.match_type.value == "missing_run"]
                
                for missing in missing_runs:
                    missing.check_date = current_date  # Add date for reporting
                    all_missing.append(missing)
                
                dates_checked += 1
            
            current_date += timedelta(days=1)
        
        print(f"📊 MISSING RUNS SUMMARY:")
        print(f"   Dates checked: {dates_checked}")
        print(f"   Missing runs found: {len(all_missing)}")
        print()
        
        if all_missing:
            # Group by priority
            high_priority = [m for m in all_missing if m.alert_priority == "HIGH"]
            medium_priority = [m for m in all_missing if m.alert_priority == "MEDIUM"]
            low_priority = [m for m in all_missing if m.alert_priority == "LOW"]
            
            print("🔥 HIGH PRIORITY MISSING RUNS:")
            for missing in high_priority:
                scheduled_time = missing.scheduled_time.strftime('%m/%d %I:%M %p')
                print(f"   • {missing.zone_name} - {scheduled_time}")
            
            print("\n⚠️  MEDIUM PRIORITY MISSING RUNS:")
            for missing in medium_priority:
                scheduled_time = missing.scheduled_time.strftime('%m/%d %I:%M %p')
                print(f"   • {missing.zone_name} - {scheduled_time}")
            
            if args.show_all:
                print("\n📋 LOW PRIORITY MISSING RUNS:")
                for missing in low_priority:
                    scheduled_time = missing.scheduled_time.strftime('%m/%d %I:%M %p')
                    print(f"   • {missing.zone_name} - {scheduled_time}")
        
        return 0 if not all_missing else (2 if any(m.alert_priority == "HIGH" for m in all_missing) else 1)
        
    except Exception as e:
        print(f"❌ Missing runs analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def main():
    """Main CLI entry point"""
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Admin CLI for Hydrawise Irrigation Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze specific date
  python admin_irrigation_analysis.py analyze today
  python admin_irrigation_analysis.py analyze yesterday
  python admin_irrigation_analysis.py analyze 2025-08-22
  
  # Automatic analysis of recent days
  python admin_irrigation_analysis.py auto --days 3
  
  # Find missing runs in date range
  python admin_irrigation_analysis.py missing week
  python admin_irrigation_analysis.py missing 2025-08-20 --end-date 2025-08-23
        """
    )
    
    # Global options
    parser.add_argument('--tolerance', type=int, default=30,
                       help='Time tolerance in minutes for matching (default: 30)')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze irrigation for specific date')
    analyze_parser.add_argument('date', help='Date to analyze (YYYY-MM-DD, "today", or "yesterday")')
    analyze_parser.add_argument('--save', action='store_true',
                               help='Save report to file')
    analyze_parser.set_defaults(func=cmd_analyze)
    
    # Auto analyze command
    auto_parser = subparsers.add_parser('auto', help='Automatic analysis of recent dates')
    auto_parser.add_argument('--days', type=int, default=3,
                            help='Number of recent days to analyze (default: 3)')
    auto_parser.set_defaults(func=cmd_auto_analyze)
    
    # Missing runs command
    missing_parser = subparsers.add_parser('missing', help='Find missing runs in date range')
    missing_parser.add_argument('start_date', help='Start date (YYYY-MM-DD or "week" for last 7 days)')
    missing_parser.add_argument('--end-date', help='End date (YYYY-MM-DD, defaults to today)')
    missing_parser.add_argument('--show-all', action='store_true',
                               help='Show all priority levels (default: only high/medium)')
    missing_parser.set_defaults(func=cmd_missing_runs)
    
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
