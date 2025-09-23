#!/usr/bin/env python3
"""
Test only the configuration without any database connections
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_water_usage_config():
    """Test water usage configuration only"""
    try:
        print("Testing water usage configuration...")
        
        # Test the config module
        from config.water_usage_config import get_water_usage_thresholds
        
        # Test with no environment variables
        high, low = get_water_usage_thresholds()
        print(f"✓ Default thresholds: high={high}, low={low}")
        
        # Test with environment variables
        os.environ['HIGH_WATER_USAGE'] = '3.0'
        os.environ['LOW_WATER_USAGE'] = '0.3'
        
        # Need to reload the module to pick up env changes
        import importlib
        import config.water_usage_config
        importlib.reload(config.water_usage_config)
        
        high, low = config.water_usage_config.get_water_usage_thresholds()
        print(f"✓ Custom thresholds: high={high}, low={low}")
        
        # Clean up
        del os.environ['HIGH_WATER_USAGE']
        del os.environ['LOW_WATER_USAGE']
        
        return True
        
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_classes():
    """Test that we can create basic classes without database"""
    try:
        print("\nTesting basic event detection classes...")
        
        # Test the config class
        from water_usage_event_detector import EventDetectionConfig
        config = EventDetectionConfig(
            enabled=False,  # Disabled to avoid database
            detect_usage_anomalies=False,
            detect_irrigation_failures=False,
            detect_usage_flags=False
        )
        print(f"✓ EventDetectionConfig created: enabled={config.enabled}")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic classes test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Configuration-Only Test")
    print("=" * 30)
    
    success = True
    
    # Test 1: Water usage config
    if not test_water_usage_config():
        success = False
    
    # Test 2: Basic classes
    if not test_basic_classes():
        success = False
    
    if success:
        print("\n✅ Configuration tests passed!")
        print("\nThe hanging issue is likely due to:")
        print("1. Database connection timeout to render.com")
        print("2. Migration taking too long")
        print("3. Network connectivity issues")
        print("\nSuggestion: Try running automated_collector.py in a test mode")
        print("to see if the integration works without the full event detection.")
    else:
        print("\n❌ Configuration tests failed!")

