#!/usr/bin/env python3
"""
Test Enhanced Event Detection System

Tests the new run-specific event detection functionality with real database data
before integrating into automated_collector.

Author: AI Assistant
Date: 2025-09-23
"""

import os
import sys
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from water_usage_event_detector import WaterUsageEventDetector, add_event_detection_for_runs_to_collection
from database.universal_database_manager import get_universal_database_manager
from utils.timezone_utils import get_houston_now

def test_database_schema():
    """Test that the enhanced events table schema is properly migrated"""
    print("=" * 60)
    print("TESTING DATABASE SCHEMA")
    print("=" * 60)
    
    db_manager = get_universal_database_manager()
    
    # Check if events table exists and has new columns
    try:
        test_query = """
            SELECT event_time, estimated_gallons, actual_flow_rate, 
                   expected_flow_rate, last_updated
            FROM events 
            LIMIT 1
        """
        result = db_manager.adapter.execute_query(test_query)
        print("✅ Events table has enhanced columns")
        return True
    except Exception as e:
        print(f"❌ Events table schema issue: {e}")
        return False

def get_recent_actual_runs(days_back: int = 3, limit: int = 5) -> List[Dict[str, Any]]:
    """Get some recent actual runs for testing"""
    print(f"\nGetting recent actual runs (last {days_back} days, limit {limit})...")
    
    db_manager = get_universal_database_manager()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)
    
    query = """
        SELECT 
            ar.id, ar.zone_id, ar.zone_name, ar.run_date, ar.actual_start_time,
            ar.actual_gallons, ar.actual_duration_minutes, ar.usage_flag,
            ar.usage_type, ar.usage, ar.scraped_at,
            z.average_flow_rate
        FROM actual_runs ar
        JOIN zones z ON ar.zone_id = z.zone_id
        WHERE ar.run_date BETWEEN %s AND %s
        AND ar.actual_gallons IS NOT NULL
        AND ar.actual_duration_minutes > 0
        ORDER BY ar.actual_start_time DESC
        LIMIT %s
    """
    
    try:
        runs = db_manager.adapter.execute_query(query, (start_date, end_date, limit))
        print(f"Found {len(runs)} recent runs")
        
        for run in runs:
            flow_rate = float(run['actual_gallons']) / float(run['actual_duration_minutes']) if run['actual_duration_minutes'] else 0
            print(f"  - Zone {run['zone_id']} ({run['zone_name']}): {run['actual_gallons']}g in {run['actual_duration_minutes']}min = {flow_rate:.2f} GPM, flag: {run['usage_flag']}")
        
        return runs
    except Exception as e:
        print(f"❌ Error getting recent runs: {e}")
        return []

def create_run_identifiers(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create run identifiers from actual run data"""
    identifiers = []
    for run in runs:
        identifiers.append({
            'zone_id': run['zone_id'],
            'actual_start_time': run['actual_start_time']
        })
    return identifiers

def test_enhanced_event_detection():
    """Test the enhanced event detection system"""
    print("=" * 60)
    print("TESTING ENHANCED EVENT DETECTION")
    print("=" * 60)
    
    # Initialize event detector
    try:
        detector = WaterUsageEventDetector()
        print("✅ Event detector initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize event detector: {e}")
        return False
    
    # Get some recent runs to test with
    recent_runs = get_recent_actual_runs(days_back=7, limit=10)
    if not recent_runs:
        print("❌ No recent runs found for testing")
        return False
    
    # Create run identifiers
    run_identifiers = create_run_identifiers(recent_runs)
    print(f"\nCreated {len(run_identifiers)} run identifiers for testing")
    
    # Test the new run-specific event detection
    print("\nTesting run-specific event detection...")
    try:
        results = detector.detect_and_record_events_for_runs(run_identifiers)
        
        print(f"Event detection results:")
        print(f"  - Success: {results['success']}")
        print(f"  - Runs analyzed: {results.get('runs_analyzed', 0)}")
        print(f"  - Events recorded: {results.get('events_recorded', 0)}")
        print(f"  - Events updated: {results.get('events_updated', 0)}")
        print(f"  - Usage anomalies: {results.get('usage_anomalies', 0)}")
        print(f"  - Irrigation failures: {results.get('irrigation_failures', 0)}")
        print(f"  - Usage flag events: {results.get('usage_flag_events', 0)}")
        
        if results.get('errors'):
            print(f"  - Errors: {results['errors']}")
        
        if results['success']:
            print("✅ Run-specific event detection completed successfully")
        else:
            print(f"❌ Event detection failed: {results.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Event detection error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_integration_function():
    """Test the new integration function"""
    print("=" * 60)
    print("TESTING INTEGRATION FUNCTION")
    print("=" * 60)
    
    # Initialize event detector
    detector = WaterUsageEventDetector()
    
    # Get some recent runs
    recent_runs = get_recent_actual_runs(days_back=3, limit=5)
    if not recent_runs:
        print("❌ No recent runs found for integration testing")
        return False
    
    run_identifiers = create_run_identifiers(recent_runs)
    
    # Test the integration function
    print(f"Testing integration function with {len(run_identifiers)} run identifiers...")
    try:
        success = add_event_detection_for_runs_to_collection(
            integration=detector,
            external_logger=None,
            run_identifiers=run_identifiers
        )
        
        if success:
            print("✅ Integration function completed successfully")
        else:
            print("❌ Integration function failed")
            return False
            
    except Exception as e:
        print(f"❌ Integration function error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def show_recent_events():
    """Show recently created events to verify the results"""
    print("=" * 60)
    print("RECENT EVENTS IN DATABASE")
    print("=" * 60)
    
    db_manager = get_universal_database_manager()
    
    # Get recent events
    query = """
        SELECT 
            failure_id, zone_name, failure_type, severity, description,
            event_time, actual_gallons, estimated_gallons, 
            actual_flow_rate, expected_flow_rate, detected_at
        FROM events 
        WHERE detected_at >= %s
        ORDER BY detected_at DESC
        LIMIT 10
    """
    
    # Look for events from the last hour
    cutoff_time = get_houston_now() - timedelta(hours=1)
    
    try:
        events = db_manager.adapter.execute_query(query, (cutoff_time,))
        
        if events:
            print(f"Found {len(events)} recent events:")
            for event in events:
                print(f"\n  Event: {event['failure_id']}")
                print(f"    Zone: {event['zone_name']}")
                print(f"    Type: {event['failure_type']} ({event['severity']})")
                print(f"    Description: {event['description']}")
                if event['event_time']:
                    print(f"    Event Time: {event['event_time']}")
                if event['actual_gallons'] is not None:
                    print(f"    Actual Gallons: {event['actual_gallons']}")
                if event['estimated_gallons'] is not None:
                    print(f"    Estimated Gallons: {event['estimated_gallons']}")
                if event['actual_flow_rate'] is not None:
                    print(f"    Actual Flow Rate: {event['actual_flow_rate']:.2f} GPM")
                if event['expected_flow_rate'] is not None:
                    print(f"    Expected Flow Rate: {event['expected_flow_rate']:.2f} GPM")
                print(f"    Detected: {event['detected_at']}")
        else:
            print("No recent events found (this might be normal if no anomalies were detected)")
            
    except Exception as e:
        print(f"❌ Error retrieving recent events: {e}")

def main():
    """Main test function"""
    print("ENHANCED EVENT DETECTION SYSTEM TEST")
    print("=" * 60)
    print(f"Test started at: {get_houston_now()}")
    print("")
    
    # Test 1: Database schema
    if not test_database_schema():
        print("\n❌ Database schema test failed - stopping tests")
        return 1
    
    # Test 2: Enhanced event detection
    if not test_enhanced_event_detection():
        print("\n❌ Enhanced event detection test failed")
        return 1
    
    # Test 3: Integration function
    if not test_integration_function():
        print("\n❌ Integration function test failed")
        return 1
    
    # Show results
    show_recent_events()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("Enhanced event detection system is ready for integration.")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

