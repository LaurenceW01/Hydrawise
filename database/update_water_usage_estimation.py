#!/usr/bin/env python3
"""
Water Usage Estimation Update Utility

Updates existing irrigation run data with water usage estimation logic:
- Adds average flow rates to zones table
- Adds usage_type and usage columns to actual_runs table  
- Processes existing runs to calculate usage estimation data

Author: AI Assistant
Date: 2025-01-27
"""

import argparse
import sys
import os
import logging
from datetime import datetime, date, timedelta
from typing import List

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.intelligent_data_storage import IntelligentDataStorage
from database.water_usage_estimator import WaterUsageEstimator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_banner():
    """Print the utility banner"""
    print("=" * 70)
    print("[HYDRAWISE] HYDRAWISE WATER USAGE ESTIMATION UPDATE")
    print("=" * 70)

def update_database_schema():
    """Update database schema with new water usage estimation columns"""
    print("\n[SYMBOL] UPDATING DATABASE SCHEMA")
    print("-" * 50)
    
    try:
        # Initialize storage to trigger schema migration
        storage = IntelligentDataStorage()
        print("[OK] Database schema updated with water usage estimation columns")
        return True
        
    except Exception as e:
        print(f"[ERROR] Schema update failed: {e}")
        return False

def update_existing_runs(target_date: str = None, days_back: int = None):
    """Update existing runs with water usage estimation"""
    print(f"\n[WATER] UPDATING WATER USAGE ESTIMATION")
    print("-" * 50)
    
    try:
        storage = IntelligentDataStorage()
        
        if days_back:
            # Process multiple days
            total_updated = 0
            today = date.today()
            
            for i in range(days_back):
                process_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
                print(f"[DATE] Processing {process_date}...")
                
                result = storage.update_existing_runs_usage_estimation(process_date)
                
                if result['success']:
                    updated = result['updated_runs']
                    total = result['total_runs']
                    total_updated += updated
                    
                    if updated > 0:
                        print(f"   [OK] Updated {updated}/{total} runs")
                    else:
                        print(f"   [OK]  No runs needed updates")
                else:
                    print(f"   [ERROR] Failed: {result.get('error')}")
            
            print(f"\n[SUCCESS] Total runs updated: {total_updated}")
            
        else:
            # Process single date or all data
            print(f"[DATE] Processing {'all data' if not target_date else target_date}...")
            
            result = storage.update_existing_runs_usage_estimation(target_date)
            
            if result['success']:
                updated = result['updated_runs']
                total = result['total_runs']
                
                if updated > 0:
                    print(f"[OK] Successfully updated {updated}/{total} runs")
                    print(f"   [RESULTS] Runs now have usage_type, usage_flag, and calculated usage values")
                else:
                    print(f"[OK]  No runs needed updates ({total} total runs checked)")
            else:
                print(f"[ERROR] Update failed: {result.get('error')}")
                return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update existing runs: {e}")
        return False

def show_usage_summary(start_date: str, end_date: str = None):
    """Show water usage estimation summary for date range"""
    print(f"\n[RESULTS] WATER USAGE ESTIMATION SUMMARY")
    print("-" * 50)
    
    try:
        estimator = WaterUsageEstimator('database/irrigation_data.db')
        
        if not end_date:
            end_date = start_date
        
        summary = estimator.get_usage_summary(start_date, end_date)
        
        if summary['success']:
            print(f"[DATE] Date Range: {summary['date_range']}")
            print(f"[RESULTS] Total Runs: {summary['total_runs']}")
            print(f"[WATER] Total Estimated Usage: {summary['total_estimated_usage']:.1f} gallons")
            print(f"[WATER] Total Actual Usage: {summary['total_actual_usage']:.1f} gallons")
            
            if summary['usage_stats']:
                print(f"\n[LOG] Usage Type Breakdown:")
                for usage_type, stats in summary['usage_stats'].items():
                    print(f"   {usage_type.upper()}: {stats['count']} runs, {stats['total_usage']:.1f} gal (avg: {stats['avg_usage']:.1f})")
            else:
                print("   No usage statistics available")
                
        else:
            print(f"[ERROR] Failed to get summary: {summary.get('error')}")
            
    except Exception as e:
        print(f"[ERROR] Failed to show summary: {e}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Update Hydrawise database with water usage estimation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update schema and process all existing runs
  python update_water_usage_estimation.py --update-all
  
  # Update schema only
  python update_water_usage_estimation.py --schema-only
  
  # Process specific date
  python update_water_usage_estimation.py --date 2025-01-26
  
  # Process last 7 days
  python update_water_usage_estimation.py --days 7
  
  # Show usage summary for yesterday
  python update_water_usage_estimation.py --summary --date yesterday
  
  # Show usage summary for date range
  python update_water_usage_estimation.py --summary --start-date 2025-01-20 --end-date 2025-01-26
        """
    )
    
    # Action arguments
    parser.add_argument('--schema-only', action='store_true',
                       help='Update database schema only (no data processing)')
    parser.add_argument('--update-all', action='store_true',
                       help='Update schema and process all existing runs')
    parser.add_argument('--date', type=str,
                       help='Process specific date (YYYY-MM-DD, "today", or "yesterday")')
    parser.add_argument('--days', type=int,
                       help='Process last N days')
    parser.add_argument('--summary', action='store_true',
                       help='Show water usage estimation summary')
    
    # Summary arguments
    parser.add_argument('--start-date', type=str,
                       help='Start date for summary (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                       help='End date for summary (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Parse arguments and determine action
    if not any([args.schema_only, args.update_all, args.date, args.days, args.summary]):
        parser.print_help()
        return 1
    
    print_banner()
    
    try:
        success = True
        
        # Update schema if requested
        if args.schema_only or args.update_all:
            success &= update_database_schema()
        
        # Process data if requested
        if args.update_all:
            success &= update_existing_runs()
        elif args.date:
            # Parse date
            if args.date == "today":
                target_date = date.today().strftime('%Y-%m-%d')
            elif args.date == "yesterday":
                target_date = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                # Validate date format
                datetime.strptime(args.date, '%Y-%m-%d')
                target_date = args.date
                
            success &= update_existing_runs(target_date)
        elif args.days:
            success &= update_existing_runs(days_back=args.days)
        
        # Show summary if requested
        if args.summary:
            if args.start_date:
                start_date = args.start_date
                end_date = args.end_date
            elif args.date:
                start_date = target_date if 'target_date' in locals() else args.date
                end_date = None
            else:
                # Default to yesterday
                start_date = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
                end_date = None
                
            show_usage_summary(start_date, end_date)
        
        if success:
            print(f"\n[SUCCESS] Water usage estimation update completed successfully!")
            return 0
        else:
            print(f"\n[WARNING]  Water usage estimation update completed with errors.")
            return 1
            
    except ValueError as e:
        print(f"[ERROR] Invalid date format: {e}")
        print("   Use YYYY-MM-DD format, 'today', or 'yesterday'")
        return 1
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
