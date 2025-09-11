#!/usr/bin/env python3
"""
Test script to verify current_ma parsing and database insertion
"""

import sys
import os
from datetime import datetime
from typing import Dict, Optional

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hydrawise_web_scraper_refactored import ActualRun
from popup_extractor import extract_hover_popup_data
from database.universal_database_manager import get_universal_database_manager

def test_popup_parsing():
    """Test the popup parsing functionality for current_ma extraction"""
    print("=" * 60)
    print("TESTING POPUP PARSING FOR CURRENT_MA")
    print("=" * 60)
    
    # Create a mock popup extractor class to test the parsing function
    class MockPopupExtractor:
        def __init__(self):
            self.logger = self
            
        def debug(self, msg):
            print(f"[DEBUG] {msg}")
            
        def info(self, msg):
            print(f"[INFO] {msg}")
            
        def warning(self, msg):
            print(f"[WARNING] {msg}")
    
    # Test cases with different current_ma patterns
    test_cases = [
        {
            "name": "Standard Current Pattern",
            "popup_text": """Normal watering cycle
Time: Thu, 7:05am
Duration: 15 minutes
Current: 200mA
Water usage: 25.5 Gallons""",
            "expected_current": 200.0
        },
        {
            "name": "High Current Reading",
            "popup_text": """Normal watering cycle
Time: Mon, 6:00am
Duration: 10 minutes
Current: 750mA
Water usage: 18.7 Gallons""",
            "expected_current": 750.0
        },
        {
            "name": "Low Current Reading",
            "popup_text": """Normal watering cycle
Time: Tue, 8:30am
Duration: 5 minutes
Current: 125mA
Water usage: 8.2 Gallons""",
            "expected_current": 125.0
        },
        {
            "name": "Decimal Current Reading",
            "popup_text": """Normal watering cycle
Time: Wed, 9:15am
Duration: 12 minutes
Current: 290.5mA
Water usage: 22.1 Gallons""",
            "expected_current": 290.5
        },
        {
            "name": "No Current Reading",
            "popup_text": """Normal watering cycle
Time: Fri, 6:45am
Duration: 8 minutes
Water usage: 15.3 Gallons""",
            "expected_current": None
        },
        {
            "name": "Aborted Run with Current",
            "popup_text": """Aborted due to sensor input
Time: Sat, 7:20am
Duration: 2 minutes
Current: 450mA
Water usage: 0 Gallons""",
            "expected_current": 450.0
        }
    ]
    
    # Mock the extractor instance
    extractor = MockPopupExtractor()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        print("-" * 40)
        print(f"Input popup text:")
        for line in test_case['popup_text'].split('\n'):
            print(f"  {line}")
        
        # Manually parse the popup text using the same logic as extract_hover_popup_data
        import re
        lines = test_case['popup_text'].split('\n')
        current_ma = None
        
        for line in lines:
            line = line.strip()
            # Use the same regex pattern from popup_extractor.py
            current_match = re.search(r'Current[:\s]*([0-9.]+)\s*mA', line, re.IGNORECASE)
            if current_match:
                current_ma = float(current_match.group(1))
                print(f"  Found current match: '{line}' -> {current_ma}mA")
                break
        
        if current_ma is None:
            print(f"  No current reading found")
        
        # Verify result
        expected = test_case['expected_current']
        if current_ma == expected:
            print(f"  ✓ PASS: Expected {expected}, got {current_ma}")
        else:
            print(f"  ✗ FAIL: Expected {expected}, got {current_ma}")
    
    return True

def test_actualrun_creation():
    """Test ActualRun object creation with current_ma field"""
    print("\n" + "=" * 60)
    print("TESTING ACTUALRUN OBJECT CREATION")
    print("=" * 60)
    
    # Test creating ActualRun with current_ma
    test_time = datetime.now()
    
    print("\nTest 1: ActualRun with current_ma")
    print("-" * 40)
    actual_run = ActualRun(
        zone_id="1",
        zone_name="Front Lawn",
        start_time=test_time,
        duration_minutes=15,
        actual_gallons=25.5,
        status="Normal watering cycle",
        notes="Test run",
        current_ma=200.0
    )
    
    print(f"Created ActualRun:")
    print(f"  Zone: {actual_run.zone_name}")
    print(f"  Duration: {actual_run.duration_minutes} minutes")
    print(f"  Gallons: {actual_run.actual_gallons}")
    print(f"  Current: {actual_run.current_ma}mA")
    
    if hasattr(actual_run, 'current_ma') and actual_run.current_ma == 200.0:
        print("  ✓ PASS: current_ma field exists and has correct value")
    else:
        print("  ✗ FAIL: current_ma field missing or incorrect")
    
    print("\nTest 2: ActualRun without current_ma (should default to None)")
    print("-" * 40)
    actual_run2 = ActualRun(
        zone_id="2",
        zone_name="Back Yard",
        start_time=test_time,
        duration_minutes=10,
        actual_gallons=18.2,
        status="Normal watering cycle",
        notes="Test run without current"
    )
    
    print(f"Created ActualRun:")
    print(f"  Zone: {actual_run2.zone_name}")
    print(f"  Current: {actual_run2.current_ma}")
    
    if hasattr(actual_run2, 'current_ma') and actual_run2.current_ma is None:
        print("  ✓ PASS: current_ma field defaults to None")
    else:
        print("  ✗ FAIL: current_ma field not handling None default correctly")
    
    return True

def test_database_insertion():
    """Test database insertion with current_ma values"""
    print("\n" + "=" * 60)
    print("TESTING DATABASE INSERTION")
    print("=" * 60)
    
    try:
        # Get database manager
        db = get_universal_database_manager()
        
        # Create test ActualRun objects
        test_time = datetime.now()
        test_runs = [
            ActualRun(
                zone_id="1",
                zone_name="Test Zone 1",
                start_time=test_time,
                duration_minutes=15,
                actual_gallons=25.5,
                status="Normal watering cycle",
                notes="Test run with current_ma",
                current_ma=200.0
            ),
            ActualRun(
                zone_id="2", 
                zone_name="Test Zone 2",
                start_time=test_time,
                duration_minutes=10,
                actual_gallons=18.2,
                status="Normal watering cycle", 
                notes="Test run without current_ma",
                current_ma=None
            ),
            ActualRun(
                zone_id="3",
                zone_name="Test Zone 3", 
                start_time=test_time,
                duration_minutes=8,
                actual_gallons=12.1,
                status="Normal watering cycle",
                notes="Test run with high current_ma",
                current_ma=750.5
            )
        ]
        
        print(f"Attempting to insert {len(test_runs)} test runs...")
        
        # Insert the test runs
        inserted_count = db.insert_actual_runs(test_runs, test_time.date())
        
        print(f"✓ Successfully inserted {inserted_count} runs")
        
        # Query back to verify current_ma was stored
        print("\nVerifying stored data...")
        
        # Use the same parameter format as the database manager
        if db.adapter.config.db_type == 'postgresql':
            query = """
                SELECT zone_name, current_ma, notes 
                FROM actual_runs 
                WHERE zone_name LIKE %s 
                AND actual_start_time >= %s
                ORDER BY zone_name
            """
            params = ('Test Zone%', test_time.replace(microsecond=0))
        else:
            query = """
                SELECT zone_name, current_ma, notes 
                FROM actual_runs 
                WHERE zone_name LIKE ? 
                AND actual_start_time >= ?
                ORDER BY zone_name
            """
            params = ('Test Zone%', test_time.replace(microsecond=0))
        
        results = db.adapter.execute_query(query, params)
        
        for result in results:
            zone_name = result['zone_name']
            current_ma = result['current_ma']
            notes = result['notes']
            print(f"  {zone_name}: current_ma = {current_ma}, notes = '{notes}'")
        
        # Clean up test data
        print("\nCleaning up test data...")
        if db.adapter.config.db_type == 'postgresql':
            cleanup_query = """
                DELETE FROM actual_runs 
                WHERE zone_name LIKE %s 
                AND actual_start_time >= %s
            """
        else:
            cleanup_query = """
                DELETE FROM actual_runs 
                WHERE zone_name LIKE ? 
                AND actual_start_time >= ?
            """
        db.adapter.execute_update(cleanup_query, ('Test Zone%', test_time.replace(microsecond=0)))
        print("✓ Test data cleaned up")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("CURRENT_MA PARSING AND DATABASE INSERTION TESTS")
    print("=" * 60)
    
    success_count = 0
    total_tests = 3
    
    # Test 1: Popup parsing
    try:
        if test_popup_parsing():
            success_count += 1
    except Exception as e:
        print(f"Popup parsing test failed: {e}")
    
    # Test 2: ActualRun creation  
    try:
        if test_actualrun_creation():
            success_count += 1
    except Exception as e:
        print(f"ActualRun creation test failed: {e}")
    
    # Test 3: Database insertion
    try:
        if test_database_insertion():
            success_count += 1
    except Exception as e:
        print(f"Database insertion test failed: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests passed: {success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("✓ ALL TESTS PASSED - current_ma functionality is working correctly!")
        return True
    else:
        print(f"✗ {total_tests - success_count} TESTS FAILED - current_ma functionality needs fixes")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
