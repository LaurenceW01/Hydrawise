#!/usr/bin/env python3
"""
Example: Configuring Water Usage Thresholds

This script demonstrates how to configure water usage variance thresholds
using environment variables or programmatically.

Author: AI Assistant
Date: 2025-01-27
"""

import os
import sys

# Add project root to path for config imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.water_usage_config import get_water_usage_thresholds
from database.water_usage_estimator import WaterUsageEstimator

def demonstrate_environment_configuration():
    """Demonstrate configuring thresholds via environment variables"""
    print("=" * 70)
    print("WATER USAGE THRESHOLD CONFIGURATION EXAMPLES")
    print("=" * 70)
    
    print("\n1. DEFAULT CONFIGURATION (no environment variables)")
    print("-" * 50)
    
    # Clear any existing environment variables
    if 'HIGH_WATER_USAGE' in os.environ:
        del os.environ['HIGH_WATER_USAGE']
    if 'LOW_WATER_USAGE' in os.environ:
        del os.environ['LOW_WATER_USAGE']
    
    high, low = get_water_usage_thresholds()
    print(f"High threshold: {high}x expected (flags usage as 'too_high' when > {high}x)")
    print(f"Low threshold:  {low}x expected (flags usage as 'too_low' when < {low}x)")
    
    # Create estimator with defaults
    estimator = WaterUsageEstimator()
    print(f"WaterUsageEstimator initialized with defaults: high={estimator.high_usage_multiplier}, low={estimator.low_usage_multiplier}")
    
    print("\n2. CUSTOM CONFIGURATION (via environment variables)")
    print("-" * 50)
    
    # Set custom environment variables
    os.environ['HIGH_WATER_USAGE'] = '3.0'
    os.environ['LOW_WATER_USAGE'] = '0.3'
    
    high, low = get_water_usage_thresholds()
    print(f"HIGH_WATER_USAGE=3.0 → High threshold: {high}x expected")
    print(f"LOW_WATER_USAGE=0.3  → Low threshold:  {low}x expected")
    
    # Create new estimator with custom values
    estimator_custom = WaterUsageEstimator()
    print(f"WaterUsageEstimator with env vars: high={estimator_custom.high_usage_multiplier}, low={estimator_custom.low_usage_multiplier}")
    
    print("\n3. PROGRAMMATIC OVERRIDE")
    print("-" * 50)
    
    # Override programmatically
    estimator_override = WaterUsageEstimator(high_usage_multiplier=2.5, low_usage_multiplier=0.4)
    print(f"WaterUsageEstimator with programmatic override: high={estimator_override.high_usage_multiplier}, low={estimator_override.low_usage_multiplier}")
    
    print("\n4. EXAMPLE USAGE SCENARIOS")
    print("-" * 50)
    
    scenarios = [
        {"name": "Conservative (strict)", "high": 1.5, "low": 0.7, "description": "Flags smaller deviations"},
        {"name": "Standard (default)", "high": 2.0, "low": 0.5, "description": "Balanced detection"},
        {"name": "Lenient (relaxed)", "high": 3.0, "low": 0.3, "description": "Only flags major deviations"}
    ]
    
    for scenario in scenarios:
        print(f"\n{scenario['name']} Configuration:")
        print(f"  HIGH_WATER_USAGE={scenario['high']} LOW_WATER_USAGE={scenario['low']}")
        print(f"  {scenario['description']}")
        
        # Set environment and test
        os.environ['HIGH_WATER_USAGE'] = str(scenario['high'])
        os.environ['LOW_WATER_USAGE'] = str(scenario['low'])
        
        # Example calculation
        expected_gallons = 10.0
        test_cases = [
            {"actual": 20.0, "desc": "Double usage"},
            {"actual": 4.0, "desc": "Low usage"},
            {"actual": 8.0, "desc": "Normal usage"}
        ]
        
        for case in test_cases:
            actual = case['actual']
            ratio = actual / expected_gallons
            
            high_thresh, low_thresh = get_water_usage_thresholds()
            if ratio > high_thresh:
                flag = 'too_high'
            elif ratio < low_thresh:
                flag = 'too_low'
            else:
                flag = 'normal'
                
            print(f"    {case['desc']}: {actual}g vs {expected_gallons}g expected ({ratio:.1f}x) → {flag}")
    
    print("\n5. DEPLOYMENT EXAMPLES")
    print("-" * 50)
    print("# For Docker/container deployment:")
    print("docker run -e HIGH_WATER_USAGE=2.5 -e LOW_WATER_USAGE=0.4 hydrawise-app")
    print("")
    print("# For systemd service:")
    print("Environment=HIGH_WATER_USAGE=2.5")
    print("Environment=LOW_WATER_USAGE=0.4")
    print("")
    print("# For shell/bash:")
    print("export HIGH_WATER_USAGE=2.5")
    print("export LOW_WATER_USAGE=0.4")
    print("python main.py")
    
    # Clean up environment variables
    if 'HIGH_WATER_USAGE' in os.environ:
        del os.environ['HIGH_WATER_USAGE']
    if 'LOW_WATER_USAGE' in os.environ:
        del os.environ['LOW_WATER_USAGE']
    
    print("\n" + "=" * 70)
    print("CONFIGURATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    demonstrate_environment_configuration()
