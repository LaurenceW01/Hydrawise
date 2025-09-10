#!/usr/bin/env python3
"""
Test Usage Flag Calculations

Demonstrates the calculations used for different usage_flag situations:
- zero_reported: when actual_gallons = 0
- too_high: when actual_gallons > 2.0x expected  
- too_low: when actual_gallons < 0.5x expected
- normal: when 0.5x <= actual_gallons <= 2.0x expected
"""

def demonstrate_usage_calculations():
    """Demonstrate usage flag calculations with example data"""
    print("=" * 80)
    print("WATER USAGE CALCULATION DEMONSTRATIONS")
    print("=" * 80)
    
    # Zone flow rate data (from config/zones.json)
    zones = {
        1: {"name": "Front Right Turf (MP)", "flow_rate": 2.5},
        4: {"name": "Front Planters & Pots", "flow_rate": 1.0},
        8: {"name": "Rear Left Beds at Fence (S)", "flow_rate": 11.3},
        10: {"name": "Rear Left Pots, Baskets & Planters (M)", "flow_rate": 3.9}
    }
    
    # Calculation thresholds
    HIGH_USAGE_MULTIPLIER = 2.0  # > 2.0x expected = too_high
    LOW_USAGE_MULTIPLIER = 0.5   # < 0.5x expected = too_low
    
    print(f"\nTHRESHOLDS:")
    print(f"  High Usage: > {HIGH_USAGE_MULTIPLIER}x expected")
    print(f"  Low Usage:  < {LOW_USAGE_MULTIPLIER}x expected")
    print(f"  Normal:     {LOW_USAGE_MULTIPLIER}x to {HIGH_USAGE_MULTIPLIER}x expected")
    
    # Test cases for each usage flag type
    test_cases = [
        # zero_reported cases
        {"zone_id": 1, "duration": 4, "actual": 0, "description": "Zone 1: Zero reported usage"},
        {"zone_id": 8, "duration": 3, "actual": 0, "description": "Zone 8: Zero reported usage"},
        
        # too_high cases  
        {"zone_id": 1, "duration": 4, "actual": 25.0, "description": "Zone 1: Too high usage"},
        {"zone_id": 4, "duration": 6, "actual": 15.0, "description": "Zone 4: Too high usage"},
        
        # too_low cases
        {"zone_id": 10, "duration": 5, "actual": 8.0, "description": "Zone 10: Too low usage"},
        {"zone_id": 8, "duration": 3, "actual": 12.0, "description": "Zone 8: Too low usage"},
        
        # normal cases
        {"zone_id": 1, "duration": 4, "actual": 8.5, "description": "Zone 1: Normal usage"},
        {"zone_id": 4, "duration": 6, "actual": 7.2, "description": "Zone 4: Normal usage"},
    ]
    
    for i, case in enumerate(test_cases, 1):
        zone_id = case['zone_id']
        zone_info = zones[zone_id]
        duration = case['duration']
        actual_gallons = case['actual']
        flow_rate = zone_info['flow_rate']
        
        print(f"\n" + "=" * 80)
        print(f"TEST CASE {i}: {case['description']}")
        print("=" * 80)
        
        print(f"Zone: {zone_id} - {zone_info['name']}")
        print(f"Flow Rate: {flow_rate} GPM")
        print(f"Duration: {duration} minutes")
        print(f"Actual Gallons: {actual_gallons}")
        
        # Calculate expected gallons
        expected_gallons = flow_rate * duration
        print(f"Expected Gallons: {flow_rate} GPM × {duration} min = {expected_gallons} gallons")
        
        # Determine usage flag and values
        if actual_gallons == 0:
            # zero_reported case
            usage_value = expected_gallons
            usage_type = 'estimated'
            usage_flag = 'zero_reported'
            print(f"\nCALCULATION:")
            print(f"  Since actual_gallons = 0:")
            print(f"  → usage_value = expected_gallons = {expected_gallons} gallons")
            print(f"  → usage_type = 'estimated'")
            print(f"  → usage_flag = 'zero_reported'")
            
        else:
            # Calculate ratio for comparison
            usage_ratio = actual_gallons / expected_gallons
            usage_value = actual_gallons
            usage_type = 'actual'
            
            print(f"Usage Ratio: {actual_gallons} ÷ {expected_gallons} = {usage_ratio:.2f}")
            
            if usage_ratio > HIGH_USAGE_MULTIPLIER:
                usage_flag = 'too_high'
                print(f"\nCALCULATION:")
                print(f"  Since {usage_ratio:.2f} > {HIGH_USAGE_MULTIPLIER}:")
                print(f"  → usage_flag = 'too_high'")
            elif usage_ratio < LOW_USAGE_MULTIPLIER:
                usage_flag = 'too_low'
                print(f"\nCALCULATION:")
                print(f"  Since {usage_ratio:.2f} < {LOW_USAGE_MULTIPLIER}:")
                print(f"  → usage_flag = 'too_low'")
            else:
                usage_flag = 'normal'
                print(f"\nCALCULATION:")
                print(f"  Since {LOW_USAGE_MULTIPLIER} ≤ {usage_ratio:.2f} ≤ {HIGH_USAGE_MULTIPLIER}:")
                print(f"  → usage_flag = 'normal'")
            
            print(f"  → usage_value = actual_gallons = {actual_gallons} gallons")
            print(f"  → usage_type = 'actual'")
        
        # Final results
        print(f"\nFINAL RESULTS:")
        print(f"  usage = {usage_value}")
        print(f"  usage_type = '{usage_type}'")
        print(f"  usage_flag = '{usage_flag}'")
        print(f"  actual_gallons = {actual_gallons} (preserved in database)")
        
        # Database storage explanation
        print(f"\nDATABASE STORAGE:")
        print(f"  The actual_runs table will contain:")
        print(f"    actual_gallons: {actual_gallons}")
        print(f"    usage: {usage_value}")
        print(f"    usage_type: '{usage_type}'")
        print(f"    usage_flag: '{usage_flag}'")
    
    print(f"\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("The insert_actual_runs method now includes comprehensive usage calculation:")
    print("1. Zero reported gallons → Estimate from flow rate × duration")
    print("2. Actual gallons > 2.0x expected → Flag as 'too_high'")
    print("3. Actual gallons < 0.5x expected → Flag as 'too_low'")
    print("4. Actual gallons within range → Flag as 'normal'")
    print("\nThis matches the previous SQLite implementation and provides")
    print("accurate water usage tracking and anomaly detection.")

if __name__ == "__main__":
    demonstrate_usage_calculations()

