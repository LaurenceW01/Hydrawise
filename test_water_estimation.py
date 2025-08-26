#!/usr/bin/env python3
"""
Test Water Usage Estimation System

Tests the water usage estimation logic with the updated flow rates.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.water_usage_estimator import WaterUsageEstimator

def test_estimation():
    print("💧 TESTING WATER USAGE ESTIMATION SYSTEM")
    print("=" * 60)
    
    estimator = WaterUsageEstimator('database/irrigation_data.db')
    
    # Test cases based on your examples
    test_cases = [
        {"zone_id": 1, "duration": 4, "actual": 4.5, "description": "Zone 1 (2.5 GPM) - Normal usage"},
        {"zone_id": 1, "duration": 4, "actual": 8.1, "description": "Zone 1 (2.5 GPM) - Too high usage"},
        {"zone_id": 1, "duration": 4, "actual": 0, "description": "Zone 1 (2.5 GPM) - Zero reported"},
        {"zone_id": 1, "duration": 4, "actual": 3.0, "description": "Zone 1 (2.5 GPM) - Too low usage"},
        {"zone_id": 5, "duration": 3, "actual": 0, "description": "Zone 5 (4.2 GPM) - Zero reported"},
        {"zone_id": 16, "duration": 2, "actual": 15.0, "description": "Zone 16 (10.9 GPM) - Normal usage"},
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {case['description']}")
        print("-" * 50)
        
        zone_id = case['zone_id']
        duration = case['duration']
        actual_gallons = case['actual']
        
        # Get expected usage
        expected = estimator.calculate_expected_usage(zone_id, duration)
        
        # Determine usage type and flag
        usage_type, usage_flag, reason = estimator.determine_usage_type_and_flag(actual_gallons, expected)
        
        # Calculate final usage value
        usage_value = estimator.calculate_usage_value(usage_type, actual_gallons, expected)
        
        print(f"   Zone {zone_id} | Duration: {duration} min | Actual: {actual_gallons} gal")
        print(f"   Expected: {expected:.1f} gal")
        print(f"   Usage Type: {usage_type}")
        print(f"   Usage Flag: {usage_flag}")
        print(f"   Final Usage: {usage_value:.1f} gal")
        print(f"   Reason: {reason}")
        
        # Validate logic
        if actual_gallons == 0:
            assert usage_type == 'estimated', f"Expected 'estimated' for zero usage"
            assert usage_flag == 'zero_reported', f"Expected 'zero_reported' for zero usage"
            assert usage_value == expected, f"Expected estimated value for zero usage"
        elif expected and actual_gallons > 1.5 * expected:
            assert usage_flag == 'too_high', f"Expected 'too_high' flag"
            assert usage_type == 'actual', f"Expected 'actual' type for high usage"
        elif expected and actual_gallons < 0.5 * expected:
            assert usage_flag == 'too_low', f"Expected 'too_low' flag"
            assert usage_type == 'actual', f"Expected 'actual' type for low usage"
        else:
            assert usage_flag == 'normal', f"Expected 'normal' flag"
            assert usage_type == 'actual', f"Expected 'actual' type for normal usage"
        
        print("   ✅ Test passed")
    
    print(f"\n🎉 All {len(test_cases)} tests passed successfully!")
    print("💧 Water usage estimation system is working correctly with updated flow rates")

if __name__ == "__main__":
    test_estimation()

