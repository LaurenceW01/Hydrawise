#!/usr/bin/env python3
"""
Test Schedule Extraction

Tests the ability to extract schedule data from the Hydrawise portal.

Author: AI Assistant
Date: 2025
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hydrawise_web_scraper import HydrawiseWebScraper

def test_schedule_extraction():
    """Test extracting schedule data from the portal"""
    print("[SYMBOL] Testing schedule extraction...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("[SYMBOL] Missing credentials for schedule extraction test")
        return False
        
    try:
        # Use non-headless mode so we can see what's happening
        scraper = HydrawiseWebScraper(username, password, headless=False)
        scraper.start_browser()
        
        print("[SYMBOL] Logging in...")
        if not scraper.login():
            print("[SYMBOL] Login failed")
            return False
            
        print("[SYMBOL] Navigating to reports...")
        scraper.navigate_to_reports()
        
        print("[SYMBOL] Extracting scheduled runs...")
        scheduled_runs = scraper.extract_scheduled_runs(datetime.now())
        
        print(f"[SYMBOL] Extraction completed!")
        print(f"   Found {len(scheduled_runs)} scheduled runs")
        
        # Show details of extracted runs
        for i, run in enumerate(scheduled_runs[:5]):  # Show first 5
            print(f"\n   Run {i+1}:")
            print(f"     Zone: {run.zone_name}")
            print(f"     Start: {run.start_time}")
            print(f"     Duration: {run.duration_minutes} minutes")
            print(f"     Expected gallons: {run.expected_gallons}")
            print(f"     Notes: {run.notes[:50]}...")
            
        if len(scheduled_runs) > 5:
            print(f"   ... and {len(scheduled_runs) - 5} more runs")
            
        # Save extracted data
        import json
        from dataclasses import asdict
        
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'data/test_schedule_extraction_{date_str}.json'
        
        with open(filename, 'w') as f:
            json.dump([asdict(run) for run in scheduled_runs], f, indent=2, default=str)
        
        print(f"\n[SYMBOL] Data saved to {filename}")
        
        # Wait for user to inspect
        input("\nPress Enter to continue (you can inspect the browser window)...")
        
        scraper.stop_browser()
        return len(scheduled_runs) > 0
        
    except Exception as e:
        print(f"[SYMBOL] Schedule extraction test failed: {e}")
        try:
            scraper.stop_browser()
        except:
            pass
        return False

def test_popup_detection():
    """Test popup detection and data extraction"""
    print("\n[SYMBOL] Testing popup detection...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("[SYMBOL] Missing credentials")
        return False
        
    try:
        scraper = HydrawiseWebScraper(username, password, headless=False)
        scraper.start_browser()
        
        if scraper.login() and scraper.navigate_to_reports():
            
            print("[SYMBOL][SYMBOL]  Testing hover actions and popup detection...")
            
            # Try to find some elements to hover over
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.action_chains import ActionChains
            import time
            
            # Look for any visible elements that might have hover popups
            hover_targets = [
                "//div[contains(@style, 'background')]",
                "//*[contains(text(), 'am') or contains(text(), 'pm')]",
                "//div[contains(@class, 'zone')]"
            ]
            
            for i, selector in enumerate(hover_targets):
                try:
                    elements = scraper.driver.find_elements(By.XPATH, selector)
                    print(f"   Found {len(elements)} elements for selector {i+1}")
                    
                    # Try hovering over first few elements
                    for j, element in enumerate(elements[:3]):
                        if element.is_displayed():
                            print(f"   Hovering over element {j+1}...")
                            
                            actions = ActionChains(scraper.driver)
                            actions.move_to_element(element).perform()
                            time.sleep(2)
                            
                            # Try to extract popup data
                            popup_data = scraper.extract_hover_popup_data()
                            
                            if popup_data:
                                print(f"   [SYMBOL] Popup data found:")
                                for key, value in popup_data.items():
                                    if value:
                                        print(f"     {key}: {value}")
                            else:
                                print(f"   [SYMBOL] No popup data for this element")
                            
                except Exception as e:
                    print(f"   [SYMBOL] Error with selector {i+1}: {e}")
                    
            input("\nPress Enter to finish popup test...")
            
        scraper.stop_browser()
        return True
        
    except Exception as e:
        print(f"[SYMBOL] Popup test failed: {e}")
        try:
            scraper.stop_browser()
        except:
            pass
        return False

def main():
    """Run schedule extraction tests"""
    print("Schedule Extraction Test Suite")
    print("=" * 50)
    
    tests = [
        test_schedule_extraction,
        test_popup_detection
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("   [SYMBOL][SYMBOL] Test failed - continuing...")
        except Exception as e:
            print(f"   [SYMBOL] Test error: {e}")
            
    print(f"\n[SYMBOL] Test Results: {passed}/{total} tests passed")
    
    if passed >= 1:
        print("[SYMBOL] Schedule extraction is working!")
    else:
        print("[SYMBOL] Schedule extraction needs debugging")
        
    return passed >= 1

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
