#!/usr/bin/env python3
"""
Test script for Irrigation Monitor

Tests the core functionality of the irrigation failure detection system.

Author: AI Assistant
Date: 2025
"""

import os
import sys
import time
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from irrigation_monitor import IrrigationMonitor
from config.failure_detection_rules import FailureType, AlertLevel

def test_monitor_initialization():
    """Test that the monitor initializes correctly"""
    print("🧪 Testing monitor initialization...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    if not api_key:
        print("❌ No API key found for testing")
        return False
        
    try:
        monitor = IrrigationMonitor(api_key, check_interval_minutes=1)
        
        print(f"✅ Monitor initialized successfully")
        print(f"   Zones found: {len(monitor.zone_status)}")
        
        for zone_id, zone in list(monitor.zone_status.items())[:3]:  # Show first 3
            print(f"   Zone {zone_id}: {zone.name} ({zone.priority} priority)")
            
        return True
        
    except Exception as e:
        print(f"❌ Monitor initialization failed: {e}")
        return False

def test_zone_status_check():
    """Test that zone status checking works"""
    print("\n🧪 Testing zone status check...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    if not api_key:
        print("❌ No API key found for testing")
        return False
        
    try:
        monitor = IrrigationMonitor(api_key)
        
        # Check status
        status = monitor.check_zone_status()
        
        print(f"✅ Status check completed")
        print(f"   Checked {len(status)} zones")
        
        # Show status of a few zones
        for zone_id, zone in list(status.items())[:3]:
            running_status = "🟢 RUNNING" if zone.running else "⚫ IDLE"
            print(f"   Zone {zone_id} ({zone.name}): {running_status}")
            if zone.time_left:
                print(f"      Next/Time left: {zone.time_left}")
                
        return True
        
    except Exception as e:
        print(f"❌ Zone status check failed: {e}")
        return False

def test_failure_detection():
    """Test the failure detection logic"""
    print("\n🧪 Testing failure detection...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    if not api_key:
        print("❌ No API key found for testing")
        return False
        
    try:
        monitor = IrrigationMonitor(api_key)
        
        # Get current status
        monitor.check_zone_status()
        
        # Simulate some zones having old last_successful_run times for testing
        test_zone_id = list(monitor.zone_status.keys())[0]
        test_zone = monitor.zone_status[test_zone_id]
        
        # Simulate zone not watered for a while (for high priority zone)
        if test_zone.priority == "HIGH":
            test_zone.last_successful_run = datetime.now() - timedelta(hours=25)
            print(f"   Simulating Zone {test_zone_id} without water for 25 hours...")
        
        # Run failure detection
        alerts = monitor.detect_failures()
        
        print(f"✅ Failure detection completed")
        print(f"   Generated {len(alerts)} alerts")
        
        for alert in alerts:
            print(f"   {alert.alert_level.value}: {alert.zone_name} - {alert.description}")
            
        return True
        
    except Exception as e:
        print(f"❌ Failure detection test failed: {e}")
        return False

def test_short_monitoring_session():
    """Test a short monitoring session"""
    print("\n🧪 Testing short monitoring session...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    if not api_key:
        print("❌ No API key found for testing")
        return False
        
    try:
        monitor = IrrigationMonitor(api_key, check_interval_minutes=1)
        
        print("   Starting monitor for 30 seconds...")
        monitor.start_monitoring()
        
        # Let it run for a short time
        time.sleep(30)
        
        # Check results
        summary = monitor.get_zone_summary()
        active_alerts = monitor.get_active_alerts()
        
        print(f"✅ Monitoring session completed")
        print(f"   Active alerts: {len(active_alerts)}")
        print(f"   Critical alerts: {summary['critical_alerts']}")
        print(f"   Warning alerts: {summary['warning_alerts']}")
        
        # Show any alerts
        for alert in active_alerts[:3]:  # Show first 3
            print(f"   {alert.alert_level.value}: {alert.zone_name} - {alert.description}")
            
        monitor.stop_monitoring()
        return True
        
    except Exception as e:
        print(f"❌ Monitoring session test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Irrigation Monitor Test Suite")
    print("=" * 50)
    
    tests = [
        test_monitor_initialization,
        test_zone_status_check,
        test_failure_detection,
        test_short_monitoring_session
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print("   ⚠️ Test failed - continuing with remaining tests...")
            
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! Monitor is ready for production use.")
    else:
        print("❌ Some tests failed. Check configuration and API connectivity.")
        
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
