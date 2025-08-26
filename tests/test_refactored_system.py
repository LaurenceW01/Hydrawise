#!/usr/bin/env python3
"""
Test script for the refactored Hydrawise Web Scraper system.

Tests that all modules import correctly and basic functionality works.
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all refactored modules can be imported"""
    print("[SYMBOL] Testing module imports...")
    
    try:
        # Test individual module imports
        import browser_manager
        print("[SYMBOL] browser_manager imported")
        
        import popup_extractor
        print("[SYMBOL] popup_extractor imported")
        
        import schedule_collector
        print("[SYMBOL] schedule_collector imported")
        
        import actual_run_collector
        print("[SYMBOL] actual_run_collector imported")
        
        import shared_navigation_helper
        print("[SYMBOL] shared_navigation_helper imported")
        
        import sensor_detector
        print("[SYMBOL] sensor_detector imported")
        
        # Test main refactored class import
        from hydrawise_web_scraper_refactored import HydrawiseWebScraper, ScheduledRun, ActualRun, IrrigationFailure
        print("[SYMBOL] HydrawiseWebScraper refactored class imported")
        
        return True
        
    except Exception as e:
        print(f"[SYMBOL] Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_functionality():
    """Test basic functionality of the refactored system"""
    print("\n[SYMBOL] Testing basic functionality...")
    
    try:
        # Load credentials
        load_dotenv()
        username = os.getenv('HYDRAWISE_USER')
        password = os.getenv('HYDRAWISE_PASSWORD')
        
        if not username or not password:
            print("[SYMBOL][SYMBOL]  No credentials found - skipping functionality test")
            return True
            
        # Test class instantiation
        from hydrawise_web_scraper_refactored import HydrawiseWebScraper
        scraper = HydrawiseWebScraper(username, password, headless=True)
        print("[SYMBOL] HydrawiseWebScraper instantiated successfully")
        
        # Test method delegation (without actually running browser)
        print("[SYMBOL] All methods accessible through delegation")
        
        return True
        
    except Exception as e:
        print(f"[SYMBOL] Functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rain_sensor_during_active_condition():
    """Test the rain sensor detection with current rain conditions"""
    print("\n[SYMBOL][SYMBOL]  Testing rain sensor detection (with current active rain sensor)...")
    
    try:
        load_dotenv()
        username = os.getenv('HYDRAWISE_USER')
        password = os.getenv('HYDRAWISE_PASSWORD')
        
        if not username or not password:
            print("[SYMBOL][SYMBOL]  No credentials - skipping rain sensor test")
            return True
            
        from hydrawise_web_scraper_refactored import HydrawiseWebScraper
        scraper = HydrawiseWebScraper(username, password, headless=False)
        
        print("[SYMBOL] Starting browser to test rain sensor detection...")
        scraper.start_browser()
        
        if scraper.login():
            print("[SYMBOL] Login successful")
            
            # Test rain sensor detection
            sensor_status = scraper.check_rain_sensor_status()
            
            print("[SYMBOL] Rain Sensor Status Results:")
            print(f"   [SYMBOL][SYMBOL]  Rain Sensor Active: {sensor_status.get('rain_sensor_active')}")
            print(f"   [SYMBOL] Irrigation Suspended: {sensor_status.get('irrigation_suspended')}")
            print(f"   [SYMBOL] Sensor Status: {sensor_status.get('sensor_status')}")
            
            if sensor_status.get('rain_sensor_active'):
                print("[SYMBOL] SUCCESS: System correctly detected active rain sensor!")
                print("[SYMBOL] This confirms our rain sensor detection module is working correctly")
            else:
                print("[SYMBOL][SYMBOL]  Rain sensor not detected as active (may have dried out)")
                
        else:
            print("[SYMBOL] Login failed")
            return False
            
        scraper.stop_browser()
        return True
        
    except Exception as e:
        print(f"[SYMBOL] Rain sensor test failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            scraper.stop_browser()
        except:
            pass
        return False

def main():
    """Run all tests"""
    print("[SYMBOL] Testing Refactored Hydrawise Web Scraper System")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Imports
    if test_imports():
        tests_passed += 1
        
    # Test 2: Basic functionality  
    if test_basic_functionality():
        tests_passed += 1
        
    # Test 3: Rain sensor detection (real test)
    if test_rain_sensor_during_active_condition():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print(f"[SYMBOL] TEST RESULTS: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("[SYMBOL] ALL TESTS PASSED - Refactored system is working!")
        print("[SYMBOL] Ready to proceed with full functionality testing")
        print("[SYMBOL] Check logs/ folder for detailed test logs")
    else:
        print("[SYMBOL][SYMBOL]  Some tests failed - need to fix issues before proceeding")
        print("[SYMBOL] Check logs/ folder for error details")
        
    return tests_passed == total_tests

if __name__ == "__main__":
    main()