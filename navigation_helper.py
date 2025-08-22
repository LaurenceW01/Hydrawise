#!/usr/bin/env python3
"""
Navigation Helper Module for Hydrawise Web Scraper

Handles date navigation, view setup, and debugging navigation elements.
Cut and pasted from HydrawiseWebScraper class without modifications.

Author: AI Assistant  
Date: 2025
"""

import time
from datetime import datetime
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def navigate_to_date(self, target_date: datetime) -> bool:
    """Navigate to a specific date using the date navigation buttons"""
    try:
        current_date = datetime.now().date()
        target_date_obj = target_date.date()
        
        self.logger.info(f"Navigating from {current_date} to {target_date_obj}")
        
        # Calculate the difference in days
        days_diff = (target_date_obj - current_date).days
        
        if days_diff == 0:
            self.logger.info("Already on target date")
            return True
        elif days_diff > 0:
            # Navigate forward
            self.logger.info(f"Navigating {days_diff} days forward")
            return self._navigate_forward_days(days_diff)
        else:
            # Navigate backward
            self.logger.info(f"Navigating {abs(days_diff)} days backward")
            return self._navigate_backward_days(abs(days_diff))
            
    except Exception as e:
        self.logger.error(f"Failed to navigate to date {target_date}: {e}")
        return False

def _navigate_forward_days(self, days: int) -> bool:
    """Navigate forward by specified number of days"""
    try:
        for day in range(days):
            # IMPORTANT: Make sure we're in the right view before looking for Next button
            # The Next button is only available in Schedule view with Day selected
            if not self._ensure_schedule_day_view():
                self.logger.error("Could not ensure Schedule Day view before navigation")
                return False
            
            # Find and click the Next button - it's in the navigation toolbar with Today/Previous/Next
            next_button = None
            next_selectors = [
                "//button[contains(text(), 'Next')]",  # Simple text match
                "//div[contains(@class, 'rbc-toolbar')]//button[contains(text(), 'Next')]",  # In toolbar
                "//div[contains(@class, 'rbc-btn-group')]//button[contains(text(), 'Next')]",  # In button group
                "//button[text()='Next']",  # Exact text match
                "//*[text()='Next' and name()='button']"  # Alternative exact match
            ]
            
            for selector in next_selectors:
                try:
                    next_button = self.driver.find_element(By.XPATH, selector)
                    if next_button.is_displayed() and next_button.is_enabled():
                        self.logger.info(f"Found Next button using selector: {selector}")
                        break
                    else:
                        self.logger.debug(f"Next button found but not clickable with selector: {selector}")
                        next_button = None
                except Exception as e:
                    self.logger.debug(f"Selector '{selector}' failed: {e}")
                    continue
            
            if not next_button:
                self.logger.error(f"Could not find clickable Next button")
                # Debug what's available
                self._debug_available_buttons()
                return False
            
            try:
                # Scroll to button if needed
                self.driver.execute_script("arguments[0].scrollIntoView();", next_button)
                time.sleep(1)
                
                # Click the Next button
                next_button.click()
                self.logger.info(f"Clicked Next button (day {day + 1}/{days})")
                
                # Wait for the page to update
                time.sleep(3)
                
                # Log current displayed date for verification
                current_displayed = self.get_current_displayed_date()
                if current_displayed:
                    self.logger.info(f"Now displaying: {current_displayed}")
                
            except Exception as e:
                self.logger.error(f"Failed to click Next button on day {day + 1}: {e}")
                return False
            
        return True
        
    except Exception as e:
        self.logger.error(f"Failed to navigate forward {days} days: {e}")
        return False

def _ensure_schedule_day_view(self) -> bool:
    """Ensure we're in Schedule view with Day selected"""
    try:
        # Check if Schedule button is selected (if not, click it)
        schedule_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Schedule')]")
        if schedule_buttons:
            schedule_button = schedule_buttons[0]
            # Check if it's already selected (you might need to adjust this check based on the UI)
            if not schedule_button.get_attribute('class') or 'active' not in schedule_button.get_attribute('class'):
                schedule_button.click()
                self.logger.info("Clicked Schedule button to ensure schedule view")
                time.sleep(2)
        
        # Check if Day button is selected (if not, click it)
        day_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Day')]")
        if day_buttons:
            day_button = day_buttons[0]
            # Check if it's already selected
            if not day_button.get_attribute('class') or 'active' not in day_button.get_attribute('class'):
                day_button.click()
                self.logger.info("Clicked Day button to ensure day view")
                time.sleep(2)
        
        return True
        
    except Exception as e:
        self.logger.error(f"Failed to ensure Schedule Day view: {e}")
        return False

def _navigate_backward_days(self, days: int) -> bool:
    """Navigate backward by specified number of days"""
    try:
        for day in range(days):
            # Find and click the Previous button
            try:
                prev_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Previous')]"))
                )
                prev_button.click()
                self.logger.info(f"Clicked Previous button (day {day + 1}/{days})")
                
                # Wait a moment for the page to update
                time.sleep(2)
                
                # Log current displayed date for verification
                current_displayed = self.get_current_displayed_date()
                if current_displayed:
                    self.logger.info(f"Now displaying: {current_displayed}")
                
            except Exception as e:
                self.logger.error(f"Failed to click Previous button on day {day + 1}: {e}")
                return False
            
        return True
        
    except Exception as e:
        self.logger.error(f"Failed to navigate backward {days} days: {e}")
        return False

def get_current_displayed_date(self) -> Optional[str]:
    """Get the currently displayed date from the page"""
    try:
        # Look for date display element - based on your screenshot showing "Friday Aug 22"
        date_selectors = [
            "//span[contains(@class, 'rbc-toolbar-label')]",
            "//*[contains(text(), 'Friday')]",
            "//*[contains(text(), 'Monday')]", 
            "//*[contains(text(), 'Tuesday')]",
            "//*[contains(text(), 'Wednesday')]",
            "//*[contains(text(), 'Thursday')]",
            "//*[contains(text(), 'Saturday')]",
            "//*[contains(text(), 'Sunday')]",
            "//*[contains(text(), 'Aug')]",
            "//*[contains(text(), 'Jan')]",
            "//*[contains(text(), 'Feb')]",
            "//*[contains(text(), 'Mar')]",
            "//*[contains(text(), 'Apr')]",
            "//*[contains(text(), 'May')]",
            "//*[contains(text(), 'Jun')]",
            "//*[contains(text(), 'Jul')]",
            "//*[contains(text(), 'Sep')]",
            "//*[contains(text(), 'Oct')]",
            "//*[contains(text(), 'Nov')]",
            "//*[contains(text(), 'Dec')]"
        ]
        
        for selector in date_selectors:
            try:
                date_element = self.driver.find_element(By.XPATH, selector)
                if date_element.is_displayed():
                    date_text = date_element.text.strip()
                    if date_text and len(date_text) > 3:  # Valid date text
                        self.logger.debug(f"Found date display: '{date_text}' using selector: {selector}")
                        return date_text
                    
            except:
                continue
                
        return None
        
    except Exception as e:
        self.logger.error(f"Failed to get current displayed date: {e}")
        return None

def click_previous_button(self) -> bool:
    """Click the Previous button to navigate to the previous day"""
    try:
        self.logger.info("Looking for Previous button...")
        
        # Step 1: Quick check if Previous button is immediately available
        quick_selectors = [
            "//button[text()='Previous']",  # Most direct match
            "//button[contains(text(), 'Previous')]"  # Simple contains match
        ]
        
        previous_button = None
        successful_selector = None
        
        # Quick scan without waiting
        for selector in quick_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        previous_button = element
                        successful_selector = f"{selector} (immediate)"
                        self.logger.info(f"✅ Found Previous button immediately: {successful_selector}")
                        break
                if previous_button:
                    break
            except:
                continue
        
        # Step 2: If not found immediately, try waiting with comprehensive selectors
        if not previous_button:
            self.logger.info("Previous button not immediately available, trying with wait...")
            comprehensive_selectors = [
                "//button[normalize-space(text())='Previous']",
                "//button[contains(normalize-space(text()), 'Previous')]", 
                "//button[text()='Previous']",
                "//button[contains(text(), 'Previous')]",
                "//*[@type='button' and contains(text(), 'Previous')]",
                "//span[contains(text(), 'Previous')]/parent::button",
                "//*[contains(@class, 'button') and contains(text(), 'Previous')]",
                "//div[contains(@class, 'rbc-toolbar')]//button[contains(text(), 'Previous')]",
                "//div[contains(@class, 'rbc-btn-group')]//button[contains(text(), 'Previous')]"
            ]
            
            # Try each selector with shorter timeout
            for selector in comprehensive_selectors:
                try:
                    previous_button = WebDriverWait(self.driver, 2).until(  # Reduced from 5 to 2 seconds
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    successful_selector = selector
                    break
                except:
                    continue
        
        if not previous_button:
            # Fallback: Search through all buttons
            self.logger.info("Direct selectors failed, searching all buttons...")
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            
            for button in buttons:
                try:
                    button_text = button.text.strip()
                    if button_text.lower() == "previous":
                        if button.is_enabled() and button.is_displayed():
                            previous_button = button
                            successful_selector = "General button search"
                            break
                except:
                    continue
        
        if previous_button:
            # Try multiple click methods to handle click interception
            try:
                # Method 1: Direct click
                previous_button.click()
                self.logger.info(f"✅ Clicked Previous button (direct) using: {successful_selector}")
                time.sleep(3)
                return True
            except Exception as e:
                self.logger.debug(f"Direct click failed: {e}")
                
                try:
                    # Method 2: JavaScript click (bypasses interception)
                    self.driver.execute_script("arguments[0].click();", previous_button)
                    self.logger.info(f"✅ Clicked Previous button (JavaScript) using: {successful_selector}")
                    time.sleep(3)
                    return True
                except Exception as e:
                    self.logger.debug(f"JavaScript click failed: {e}")
                    
                    try:
                        # Method 3: ActionChains click after scroll
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", previous_button)
                        time.sleep(1)
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(self.driver).move_to_element(previous_button).click().perform()
                        self.logger.info(f"✅ Clicked Previous button (ActionChains) using: {successful_selector}")
                        time.sleep(3)
                        return True
                    except Exception as e:
                        self.logger.error(f"All click methods failed: {e}")
                        return False
        else:
            self.logger.error("❌ Could not find Previous button")
            self._debug_available_buttons()
            return False
            
    except Exception as e:
        self.logger.error(f"❌ Failed to click Previous button: {e}")
        return False

def _debug_available_buttons(self):
    """Debug method to see what buttons are available on the page"""
    try:
        self.logger.info("Debugging available buttons on the page...")
        
        # Find all buttons
        all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
        self.logger.info(f"Found {len(all_buttons)} button elements")
        
        for i, button in enumerate(all_buttons[:10]):  # Show first 10 buttons
            try:
                button_text = button.text.strip()
                button_class = button.get_attribute('class') or ''
                button_type = button.get_attribute('type') or ''
                aria_label = button.get_attribute('aria-label') or ''
                
                self.logger.info(f"Button {i+1}: text='{button_text}', class='{button_class}', type='{button_type}', aria-label='{aria_label}'")
            except Exception as e:
                self.logger.debug(f"Error inspecting button {i+1}: {e}")
                
        # Also look for any elements with 'next' in class or text
        next_elements = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'next') or contains(text(), 'Next') or contains(text(), 'next')]")
        self.logger.info(f"Found {len(next_elements)} elements containing 'next'")
        
        for i, element in enumerate(next_elements[:5]):  # Show first 5
            try:
                element_tag = element.tag_name
                element_text = element.text.strip()
                element_class = element.get_attribute('class') or ''
                self.logger.info(f"Next element {i+1}: <{element_tag}> text='{element_text}', class='{element_class}'")
            except Exception as e:
                self.logger.debug(f"Error inspecting next element {i+1}: {e}")
                
    except Exception as e:
        self.logger.error(f"Error in debug method: {e}")

def _setup_schedule_view(self) -> bool:
    """Setup the Schedule view and ensure it's ready for navigation"""
    try:
        # Click Schedule tab
        self.logger.info("Clicking Schedule tab...")
        schedule_selectors = [
            "//button[contains(text(), 'Schedule')]",
            "//*[@data-testid='schedule-tab']",
            "//button[@data-testid='schedule-tab']"
        ]
        
        schedule_clicked = False
        for selector in schedule_selectors:
            try:
                schedule_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                schedule_button.click()
                self.logger.info(f"Clicked Schedule tab using selector: {selector}")
                schedule_clicked = True
                break
            except Exception as e:
                self.logger.debug(f"Schedule selector '{selector}' failed: {e}")
                continue
                
        if not schedule_clicked:
            self.logger.error("Could not find or click Schedule tab")
            return False
            
        # Wait for schedule to load
        time.sleep(3)
        
        # Ensure we're in Day view 
        self.logger.info("Ensuring Day view is selected...")
        day_selectors = [
            "//button[contains(text(), 'Day')]",
            "//*[@data-testid='day-button']"
        ]
        
        for selector in day_selectors:
            try:
                day_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                day_button.click()
                self.logger.info(f"Clicked Day button using selector: {selector}")
                time.sleep(2)  # Wait for view to switch
                return True
            except Exception as e:
                self.logger.debug(f"Day selector '{selector}' failed: {e}")
                continue
                
        self.logger.warning("Could not find Day button, but continuing...")
        return True
        
    except Exception as e:
        self.logger.error(f"Failed to setup schedule view: {e}")
        return False
