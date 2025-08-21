#!/usr/bin/env python3
"""
Test script for Hydrawise Web Scraper

Tests the web scraping functionality for the Hydrawise portal.

Author: AI Assistant
Date: 2025
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hydrawise_web_scraper import HydrawiseWebScraper

def test_credentials():
    """Test that credentials are available"""
    print("🧪 Testing credentials...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username:
        print("❌ HYDRAWISE_USER not found in .env file")
        return False
        
    if not password:
        print("❌ HYDRAWISE_PASSWORD not found in .env file")
        return False
        
    print(f"✅ Credentials found for user: {username[:5]}...")
    return True

def test_browser_startup():
    """Test that the browser can start and stop"""
    print("\n🧪 Testing browser startup...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("❌ Missing credentials for browser test")
        return False
        
    try:
        scraper = HydrawiseWebScraper(username, password, headless=True)
        scraper.start_browser()
        print("✅ Browser started successfully")
        
        # Test navigation to Hydrawise
        scraper.driver.get("https://app.hydrawise.com")
        print("✅ Can navigate to Hydrawise portal")
        
        scraper.stop_browser()
        print("✅ Browser stopped successfully")
        return True
        
    except Exception as e:
        print(f"❌ Browser test failed: {e}")
        return False

def test_login_page_access():
    """Test that we can access the login page"""
    print("\n🧪 Testing login page access...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("❌ Missing credentials for login test")
        return False
        
    try:
        scraper = HydrawiseWebScraper(username, password, headless=True)
        scraper.start_browser()
        
        # Navigate to login page
        scraper.driver.get(scraper.login_url)
        print("✅ Can access login page")
        
        # Check for login form elements
        from selenium.webdriver.common.by import By
        email_field = scraper.driver.find_element(By.XPATH, "//input[@placeholder='Email']")
        password_field = scraper.driver.find_element(By.XPATH, "//input[@placeholder='Password']")
        
        if email_field and password_field:
            print("✅ Login form elements found")
        
        scraper.stop_browser()
        return True
        
    except Exception as e:
        print(f"❌ Login page test failed: {e}")
        return False

def test_full_login():
    """Test actual login to the portal (use with caution)"""
    print("\n🧪 Testing full login process...")
    print("⚠️  This will attempt to login to your actual Hydrawise account")
    
    response = input("Do you want to proceed with login test? (y/N): ")
    if response.lower() != 'y':
        print("🔄 Skipping login test")
        return True
        
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("❌ Missing credentials for login test")
        return False
        
    try:
        scraper = HydrawiseWebScraper(username, password, headless=False)  # Non-headless so you can see
        scraper.start_browser()
        
        # Attempt login
        if scraper.login():
            print("✅ Login successful!")
            
            # Try to navigate to reports
            scraper.navigate_to_reports()
            print("✅ Can access reports page")
            
            # Wait a moment for user to see the page
            input("Press Enter to continue...")
            
        else:
            print("❌ Login failed")
            return False
            
        scraper.stop_browser()
        return True
        
    except Exception as e:
        print(f"❌ Full login test failed: {e}")
        return False

def test_config_loading():
    """Test that configuration loads properly"""
    print("\n🧪 Testing configuration loading...")
    
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'config'))
        from web_scraper_config import SELECTORS, TIMEOUTS, URLS, get_zone_priority
        
        print("✅ Configuration imported successfully")
        print(f"   Login URL: {URLS['login']}")
        print(f"   Page timeout: {TIMEOUTS['page_load']}s")
        
        # Test zone priority function
        test_priority = get_zone_priority("Front Planters and Pots")
        print(f"   Zone priority test: 'Front Planters and Pots' -> {test_priority}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Hydrawise Web Scraper Test Suite")
    print("=" * 50)
    
    tests = [
        test_credentials,
        test_config_loading,
        test_browser_startup,
        test_login_page_access,
        test_full_login  # This one requires user confirmation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("   ⚠️ Test failed - continuing with remaining tests...")
        except Exception as e:
            print(f"   ❌ Test error: {e}")
            
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed >= 3:  # At least basic tests pass
        print("✅ Web scraper setup looks good!")
        print("   Ready to proceed with schedule extraction")
    else:
        print("❌ Web scraper setup needs work")
        print("   Check credentials and browser installation")
        
    return passed >= 3

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
