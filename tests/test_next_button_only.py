#!/usr/bin/env python3
"""
Test Next Button Detection Only

Skips schedule collection and focuses on finding the Next button after Day button is pressed.
This is for debugging the Next button location issue quickly.

Author: AI Assistant
Date: 2025-08-21
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Import our scraper
from hydrawise_web_scraper import HydrawiseWebScraper

def main():
    """Test Next button detection only"""
    
    # Load environment variables
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("Error: HYDRAWISE_USER and HYDRAWISE_PASSWORD must be set in .env file")
        return
        
    print("Testing Next Button Detection Only")
    print("=" * 40)
    
    # Create scraper with debug mode enabled
    scraper = HydrawiseWebScraper(username, password, headless=False)
    
    try:
        # Start browser and login
        print("Starting browser and logging in...")
        scraper.start_browser()
        if not scraper.login():
            raise Exception("Failed to login to Hydrawise portal")
            
        # Navigate to reports
        print("Navigating to reports...")
        if not scraper.navigate_to_reports():
            raise Exception("Failed to navigate to reports page")
            
        print("SUCCESS: Reached reports page")
        
        # Click Schedule tab (using EXACT same selectors as working code)
        print("Clicking Schedule tab...")
        
        # Use the exact same selectors from extract_scheduled_runs that work
        schedule_selectors = [
            "//div[@data-testid='sub-tab-reports.name.watering-schedule']",
            "//div[contains(@class, 'reports-page__subtabs__tab') and contains(text(), 'Schedule')]",
            "//button[contains(text(), 'Schedule')]"
        ]
        
        schedule_tab = None
        successful_selector = None
        
        for i, selector in enumerate(schedule_selectors, 1):
            try:
                print(f"  Trying Schedule selector {i}: {selector}")
                schedule_tab = WebDriverWait(scraper.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                successful_selector = selector
                print(f"  SUCCESS: Found Schedule tab with selector {i}")
                break
            except Exception as e:
                print(f"  Failed with selector {i}: {e}")
                continue
                
        if not schedule_tab:
            raise Exception("Could not find Schedule tab with any selector")
            
        schedule_tab.click()
        time.sleep(3)
        print(f"SUCCESS: Clicked Schedule tab using: {successful_selector}")
        
        # Click Day button (using EXACT same logic as working code)
        print("Clicking Day button...")
        
        # Wait for Day button to appear after Schedule tab loads (same as working code)
        time.sleep(2)
        
        # Use the exact same Day button selection logic from extract_scheduled_runs
        day_button = None
        all_buttons = scraper.driver.find_elements(By.TAG_NAME, "button")
        for button in all_buttons:
            if button.text.strip().lower() == 'day' and button.is_displayed():
                day_button = button
                print(f"Found Day button: '{button.text}' (visible: {button.is_displayed()})")
                break
                
        if not day_button:
            print("FAILED: Could not find Day button")
            raise Exception("Could not find Day button")
            
        day_button.click()
        print("SUCCESS: Clicked Day button")
        
        # Wait for page to fully load after Day button click
        print("Waiting for page to fully stabilize after Day button...")
        time.sleep(5)
        
        # Wait for toolbar to be ready
        print("Waiting for toolbar to be ready...")
        try:
            WebDriverWait(scraper.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(@class, 'rbc-toolbar')]"))
            )
            print("SUCCESS: Toolbar found")
            time.sleep(2)  # Additional stability wait
        except Exception as e:
            print(f"WARNING: Could not confirm toolbar: {e}")
        
        # NOW LOOK FOR NEXT BUTTON
        print("\nSearching for Next button...")
        
        # Try different selectors for the Next button (matching the main scraper)
        next_selectors = [
            "//button[text()='Next']",
            "//button[contains(text(), 'Next')]",
            "//button[@type='button' and text()='Next']",
            "//*[@class='rbc-btn-group']/button[text()='Next']",
            "//*[contains(@class, 'rbc-btn-group')]//button[text()='Next']",
            "//*[contains(@class, 'rbc-toolbar')]//button[text()='Next']",
            "//*[contains(@class, 'toolbar')]//button[text()='Next']",
            "//button[contains(@class, 'rbc-btn') and text()='Next']"
        ]
        
        next_button = None
        successful_selector = None
        
        for i, selector in enumerate(next_selectors, 1):
            try:
                print(f"  Trying selector {i}: {selector}")
                buttons = scraper.driver.find_elements(By.XPATH, selector)
                if buttons:
                    next_button = buttons[0]
                    successful_selector = selector
                    print(f"  SUCCESS: Found {len(buttons)} button(s) with selector {i}")
                    break
                else:
                    print(f"  No buttons found with selector {i}")
            except Exception as e:
                print(f"  Error with selector {i}: {e}")
                
        if next_button:
            print(f"\nSUCCESS: Found Next button!")
            print(f"Using selector: {successful_selector}")
            print(f"Button text: '{next_button.text}'")
            print(f"Button enabled: {next_button.is_enabled()}")
            print(f"Button visible: {next_button.is_displayed()}")
            
            # Try clicking it
            print("Attempting to click Next button...")
            try:
                next_button.click()
                print("SUCCESS: Clicked Next button!")
                time.sleep(3)
                
                # Check if page changed
                print("Checking if date changed...")
                current_date = scraper.get_current_displayed_date()
                print(f"Current displayed date after click: '{current_date}'")
                
            except Exception as e:
                print(f"FAILED to click Next button: {e}")
        else:
            print("\nFAILED: Could not find Next button with any selector")
            
            # Debug what buttons ARE available
            print("\nDEBUG: Looking for ALL buttons in the page...")
            all_buttons = scraper.driver.find_elements(By.TAG_NAME, "button")
            print(f"Found {len(all_buttons)} total buttons")
            
            toolbar_buttons = []
            for i, button in enumerate(all_buttons):
                try:
                    button_text = button.text.strip()
                    button_class = button.get_attribute("class")
                    if button_text and ("toolbar" in button_class.lower() or "rbc" in button_class.lower() or button_text in ["Today", "Previous", "Next", "Day", "Week", "Month"]):
                        toolbar_buttons.append((button_text, button_class))
                        print(f"  Button {i+1}: '{button_text}' (class: {button_class})")
                except:
                    continue
                    
            if not toolbar_buttons:
                print("No toolbar-like buttons found")
            
    except Exception as e:
        print(f"FAILED: Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\nTest completed. Browser will stay open for manual inspection.")
        print("Press Enter to close browser...")
        input()
        try:
            scraper.stop_browser()
        except:
            pass

if __name__ == "__main__":
    main()
