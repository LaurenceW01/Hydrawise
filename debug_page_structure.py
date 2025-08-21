#!/usr/bin/env python3
"""
Debug Page Structure

Inspects the actual HTML structure of the Hydrawise Reports page
to understand what selectors we need for scraping.

Author: AI Assistant
Date: 2025
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add current directory to path
sys.path.append('.')
from hydrawise_web_scraper import HydrawiseWebScraper

def debug_page_structure():
    """Inspect the actual page structure"""
    load_dotenv()
    
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("❌ Missing credentials")
        return
        
    # Use visible browser so we can see what's happening
    scraper = HydrawiseWebScraper(username, password, headless=False)
    
    try:
        scraper.start_browser()
        
        if scraper.login() and scraper.navigate_to_reports():
            print("\n🔍 DEBUGGING PAGE STRUCTURE")
            print("=" * 50)
            
            # 1. Get page title and URL
            print(f"Page Title: {scraper.driver.title}")
            print(f"Current URL: {scraper.driver.current_url}")
            
            # 2. Look for all buttons on the page
            from selenium.webdriver.common.by import By
            buttons = scraper.driver.find_elements(By.TAG_NAME, "button")
            print(f"\n📋 Found {len(buttons)} buttons:")
            for i, button in enumerate(buttons):
                text = button.text.strip()
                classes = button.get_attribute('class')
                if text:
                    print(f"  {i+1}. '{text}' (classes: {classes})")
            
            # 3. Look for Schedule/Reported specifically
            print(f"\n🔍 Looking for Schedule/Reported buttons:")
            schedule_patterns = ['Schedule', 'Reported', 'Water Savings']
            for pattern in schedule_patterns:
                try:
                    elements = scraper.driver.find_elements(By.XPATH, f"//*[contains(text(), '{pattern}')]")
                    print(f"  {pattern}: Found {len(elements)} elements")
                    for elem in elements[:3]:
                        tag = elem.tag_name
                        text = elem.text.strip()
                        classes = elem.get_attribute('class')
                        print(f"    - {tag}: '{text}' (classes: {classes})")
                except Exception as e:
                    print(f"    - Error searching for {pattern}: {e}")
            
            # 4. Look for Day/Week/Month buttons
            print(f"\n📅 Looking for Day/Week/Month buttons:")
            time_patterns = ['Day', 'Week', 'Month', 'Today', 'Previous', 'Next']
            for pattern in time_patterns:
                try:
                    elements = scraper.driver.find_elements(By.XPATH, f"//*[contains(text(), '{pattern}')]")
                    print(f"  {pattern}: Found {len(elements)} elements")
                except:
                    print(f"  {pattern}: Not found")
            
            # 5. Look for timeline/schedule elements
            print(f"\n⏰ Looking for timeline elements:")
            timeline_selectors = [
                "//div[contains(@style, 'background-color')]",
                "//div[contains(@class, 'timeline')]", 
                "//div[contains(@class, 'schedule')]",
                "//div[contains(@class, 'zone')]",
                "//*[contains(text(), 'am') or contains(text(), 'pm')]"
            ]
            
            for selector in timeline_selectors:
                try:
                    elements = scraper.driver.find_elements(By.XPATH, selector)
                    print(f"  '{selector[:30]}...': {len(elements)} elements")
                    if elements:
                        # Show first few
                        for i, elem in enumerate(elements[:3]):
                            text = elem.text.strip()[:50]
                            if text:
                                print(f"    {i+1}. {text}")
                except Exception as e:
                    print(f"  Error with selector: {e}")
            
            # 6. Save page source for offline analysis
            page_source = scraper.driver.page_source
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'data/debug_page_source_{timestamp}.html'
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            print(f"\n💾 Page source saved to: {filename}")
            print("   You can open this file in a browser to inspect the HTML structure")
            
            # 7. Take a screenshot
            screenshot_file = f'data/debug_screenshot_{timestamp}.png'
            scraper.driver.save_screenshot(screenshot_file)
            print(f"📸 Screenshot saved to: {screenshot_file}")
            
            print(f"\n⏸️  Browser window is open - you can inspect the page manually")
            print("   Press Enter when ready to continue...")
            input()
            
        scraper.stop_browser()
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        try:
            scraper.stop_browser()
        except:
            pass

if __name__ == "__main__":
    debug_page_structure()
