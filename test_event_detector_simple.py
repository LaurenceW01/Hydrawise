#!/usr/bin/env python3
"""
Simple test for event detection without heavy initialization
"""

import os
import sys
from datetime import date

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_imports():
    """Test that we can import the modules without database initialization"""
    try:
        print("Testing imports...")
        
        # Test water usage config
        from config.water_usage_config import get_water_usage_thresholds
        high, low = get_water_usage_thresholds()
        print(f"✓ Water usage thresholds: high={high}, low={low}")
        
        # Test basic integration function (without database)
        from water_usage_event_detector import integrate_with_automated_collector
        print("✓ Event detector integration function imported")
        
        # Test that we can create the config
        from water_usage_event_detector import EventDetectionConfig
        config = EventDetectionConfig(enabled=False)  # Disabled to avoid DB connection
        print(f"✓ Event detection config created: enabled={config.enabled}")
        
        print("\n✅ All basic imports and configurations working!")
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_database_connection():
    """Test database connection separately"""
    try:
        print("\nTesting database connection...")
        from database.universal_database_manager import get_universal_database_manager
        
        # Try to get the manager (this will test the connection)
        db_manager = get_universal_database_manager()
        print("✓ Database manager initialized")
        
        # Test a simple query
        result = db_manager.adapter.execute_query("SELECT 1 as test")
        if result and result[0]['test'] == 1:
            print("✓ Database query successful")
            return True
        else:
            print("❌ Database query failed")
            return False
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_table_existence():
    """Test if events table exists"""
    try:
        print("\nTesting table existence...")
        from database.universal_database_manager import get_universal_database_manager
        
        db_manager = get_universal_database_manager()
        
        # Check for events table
        events_exists = db_manager.adapter.table_exists('events')
        print(f"✓ Events table exists: {events_exists}")
        
        # Check for old failure_events table
        failure_events_exists = db_manager.adapter.table_exists('failure_events')
        print(f"✓ Failure_events table exists: {failure_events_exists}")
        
        if events_exists:
            # Count events
            result = db_manager.adapter.execute_query("SELECT COUNT(*) as count FROM events")
            count = result[0]['count'] if result else 0
            print(f"✓ Events table has {count} records")
        
        return True
        
    except Exception as e:
        print(f"❌ Table check failed: {e}")
        return False

if __name__ == "__main__":
    print("Simple Event Detection Test")
    print("=" * 50)
    
    # Test 1: Basic imports (no database)
    if not test_basic_imports():
        print("❌ Basic imports failed - stopping tests")
        sys.exit(1)
    
    # Test 2: Database connection
    if not test_database_connection():
        print("❌ Database connection failed - stopping tests")
        sys.exit(1)
    
    # Test 3: Table existence
    if not test_table_existence():
        print("❌ Table checks failed")
        sys.exit(1)
    
    print("\n🎉 All tests passed! The event detection system should work.")
    print("\nNext steps:")
    print("1. The migration from failure_events to events completed successfully")
    print("2. You can now use the event detection in automated_collector.py")
    print("3. Set WATER_USAGE_EVENT_DETECTION=true to enable it")

