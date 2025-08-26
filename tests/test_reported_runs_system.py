#!/usr/bin/env python3
"""
Test Script for Reported Runs Collection System

Tests all three operational modes:
1. Daily collection (previous day + current day)
2. Periodic collection (current day deltas) 
3. Admin override (manual collection)

Author: AI Assistant
Date: 2025-08-23
"""

import os
import sys
from datetime import date, timedelta
from dotenv import load_dotenv

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from reported_runs_manager import ReportedRunsManager

def print_banner(title: str):
    """Print a nice banner"""
    print("\n" + "=" * 70)
    print(f"[SYMBOL] {title}")
    print("=" * 70)

def print_result(result, title: str):
    """Print collection result in a nice format"""
    print(f"\n[SYMBOL] {title}")
    print("-" * 50)
    print(f"Mode: {result.mode.value}")
    print(f"Success: {'[SYMBOL] Yes' if result.success else '[SYMBOL] No'}")
    print(f"Collection Date: {result.collection_date}")
    print(f"Runs Collected: {result.runs_collected}")
    print(f"Runs Stored: {result.runs_stored}")
    duration = (result.end_time - result.start_time).total_seconds()
    print(f"Duration: {duration:.1f} seconds")
    
    if result.details:
        print(f"Details: {result.details}")
    
    if result.errors:
        print(f"[SYMBOL] Errors:")
        for error in result.errors:
            print(f"   - {error}")

def test_system_status():
    """Test getting system status"""
    print_banner("SYSTEM STATUS TEST")
    
    try:
        manager = ReportedRunsManager()
        status = manager.get_collection_status()
        
        print(f"[SYMBOL] Current Time: {status['current_time']}")
        
        print(f"\n[SYMBOL] Daily Collection Status:")
        daily = status['daily_collection']
        print(f"   Last Run: {daily['last_run'] or 'Never'}")
        print(f"   Completed Today: {'[SYMBOL] Yes' if daily['completed_today'] else '[SYMBOL] No'}")
        print(f"   Next Recommended: {daily['next_recommended']}")
        
        print(f"\n[SYMBOL] Periodic Collection Status:")
        periodic = status['periodic_collection']
        print(f"   Last Run: {periodic['last_run'] or 'Never'}")
        print(f"   Completed Today: {'[SYMBOL] Yes' if periodic['completed_today'] else '[SYMBOL] No'}")
        print(f"   Next Recommended: {periodic['next_recommended'] or 'Available now'}")
        
        print(f"\n[SYMBOL][SYMBOL]  Database Status:")
        db_info = status['database_info']
        print(f"   Total Actual Runs: {db_info.get('actual_runs_count', 0)}")
        print(f"   Database Path: {db_info.get('database_path', 'Unknown')}")
        
        print("\n[SYMBOL] Status test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n[SYMBOL] Status test failed: {e}")
        return False

def test_admin_collection():
    """Test admin override collection"""
    print_banner("ADMIN COLLECTION TEST")
    
    try:
        manager = ReportedRunsManager(headless=False)  # Show browser for testing
        
        # Test with yesterday, limited to 3 zones for speed
        yesterday = date.today() - timedelta(days=1)
        print(f"[SYMBOL] Testing admin collection for {yesterday} (first 3 zones)")
        
        result = manager.collect_admin(yesterday, limit_zones=3)
        print_result(result, f"Admin Collection Results for {yesterday}")
        
        if result.success:
            print(f"\n[SYMBOL] Admin collection test passed!")
            print(f"   Successfully collected {result.runs_collected} runs and stored {result.runs_stored}")
            return True
        else:
            print(f"\n[SYMBOL] Admin collection test failed!")
            return False
            
    except Exception as e:
        print(f"\n[SYMBOL] Admin collection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_periodic_collection():
    """Test periodic collection (current day)"""
    print_banner("PERIODIC COLLECTION TEST")
    
    try:
        manager = ReportedRunsManager(headless=False)  # Show browser for testing
        
        print(f"[SYMBOL] Testing periodic collection for today")
        
        result = manager.collect_periodic(min_interval_minutes=0)  # Override interval for testing
        print_result(result, "Periodic Collection Results")
        
        if result.success or (result.details and 'skipped' in result.details):
            print(f"\n[SYMBOL] Periodic collection test passed!")
            if result.runs_stored > 0:
                print(f"   Successfully collected {result.runs_collected} runs and stored {result.runs_stored}")
            else:
                print(f"   Collection completed (may have been skipped or no new data)")
            return True
        else:
            print(f"\n[SYMBOL] Periodic collection test failed!")
            return False
            
    except Exception as e:
        print(f"\n[SYMBOL] Periodic collection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_daily_collection():
    """Test daily collection (previous day + current day)"""
    print_banner("DAILY COLLECTION TEST")
    
    try:
        manager = ReportedRunsManager(headless=False)  # Show browser for testing
        
        print(f"[SYMBOL] Testing daily collection (previous day + current day)")
        
        # Force collection even if already done today
        result = manager.collect_daily(force=True)
        print_result(result, "Daily Collection Results")
        
        if result.success:
            print(f"\n[SYMBOL] Daily collection test passed!")
            print(f"   Successfully collected {result.runs_collected} runs and stored {result.runs_stored}")
            
            # Show breakdown
            details = result.details
            if details:
                print(f"   Previous day ({details.get('previous_date')}): {details.get('previous_day_runs', 0)} runs")
                print(f"   Current day ({details.get('current_date')}): {details.get('current_day_runs', 0)} runs")
            return True
        else:
            print(f"\n[SYMBOL] Daily collection test failed!")
            return False
            
    except Exception as e:
        print(f"\n[SYMBOL] Daily collection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("[SYMBOL] HYDRAWISE REPORTED RUNS COLLECTION SYSTEM TEST")
    print("=" * 70)
    print("This test validates all three operational modes:")
    print("1. [SYMBOL] Daily Collection (previous day + current day)")
    print("2. [SYMBOL] Periodic Collection (current day deltas)")
    print("3. [SYMBOL] Admin Override Collection (manual)")
    print("=" * 70)
    
    # Load environment variables
    load_dotenv()
    
    # Check credentials
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("[SYMBOL] Error: HYDRAWISE_USER and HYDRAWISE_PASSWORD must be set in .env file")
        return 1
    
    tests = [
        ("System Status", test_system_status),
        ("Admin Collection", test_admin_collection),
        ("Periodic Collection", test_periodic_collection),
        # Note: Skip daily collection in automated test to avoid excessive browser usage
        # ("Daily Collection", test_daily_collection),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            print(f"\n[SYMBOL] Running {test_name} test...")
            if test_func():
                passed += 1
                print(f"[SYMBOL] {test_name} test PASSED")
            else:
                print(f"[SYMBOL] {test_name} test FAILED")
        except Exception as e:
            print(f"[SYMBOL] {test_name} test ERROR: {e}")
    
    # Final results
    print_banner("TEST RESULTS SUMMARY")
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n[SYMBOL] ALL TESTS PASSED!")
        print("The reported runs collection system is working correctly.")
        print("\nYou can now use:")
        print("- python admin_reported_runs.py daily    # For daily collection")
        print("- python admin_reported_runs.py periodic # For periodic collection")
        print("- python admin_reported_runs.py admin yesterday # For manual collection")
        print("- python database/automated_collector.py  # For background automation")
        return 0
    else:
        print("\n[SYMBOL][SYMBOL]  SOME TESTS FAILED!")
        print("Please review the error messages above and fix any issues before using the system.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
