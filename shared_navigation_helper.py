#!/usr/bin/env python3
"""
Shared Navigation Helper for Hydrawise Reports

Provides robust navigation functions that can be shared by schedule collection
and reported runs collection systems. Incorporates proven patterns from:
- reported_run_collector.py 
- schedule_collector.py
- navigation_helper.py

Key features:
- Multiple selector strategies with retries
- Robust button clicking with fallback methods
- View switching (Day/Week/Month) with verification
- Date range navigation (Previous/Next buttons)
- Tab switching (Schedule/Reported) with waits
- Current date detection and display parsing

Author: AI Assistant
Date: 2025-08-25
"""

import time
import re
import calendar
from datetime import datetime, date, timedelta
from typing import Optional, List, Union
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains


class HydrawiseNavigationHelper:
    """Shared navigation helper for Hydrawise reports interface"""
    
    def __init__(self, scraper):
        """
        Initialize with scraper instance
        
        Args:
            scraper: HydrawiseWebScraper instance with driver, wait, and logger
        """
        self.scraper = scraper
        self.driver = scraper.driver
        self.wait = scraper.wait
        self.logger = scraper.logger
    
    # ========== TAB NAVIGATION ==========
    
    def navigate_to_schedule_tab(self, wait_seconds: int = 5) -> bool:
        """
        Navigate to Schedule tab with robust clicking and waiting
        
        Args:
            wait_seconds: Seconds to wait after clicking
            
        Returns:
            bool: True if successful
        """
        self.logger.info("🔄 Navigating to Schedule tab...")
        
        # Multiple selector strategies based on working implementations
        schedule_selectors = [
            "//div[@data-testid='sub-tab-reports.name.watering-schedule']",
            "//div[contains(@class, 'reports-page__subtabs__tab') and contains(text(), 'Schedule')]",
            "//button[contains(text(), 'Schedule')]",
            "//*[contains(text(), 'Schedule')]",
            "//button[@data-testid='schedule-tab']"
        ]
        
        for selector in schedule_selectors:
            try:
                # Use shorter wait for each selector to reduce total delay
                schedule_element = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                schedule_element.click()
                self.logger.info(f"✅ Clicked Schedule tab using: {selector}")
                time.sleep(wait_seconds)  # Wait for data to load
                return True
            except Exception as e:
                self.logger.debug(f"Schedule selector '{selector}' failed: {e}")
                continue
        
        self.logger.error("❌ Could not find or click Schedule tab")
        return False
    
    def navigate_to_reported_tab(self, wait_seconds: int = 5) -> bool:
        """
        Navigate to Reported tab with robust clicking and waiting
        
        Args:
            wait_seconds: Seconds to wait after clicking
            
        Returns:
            bool: True if successful
        """
        self.logger.info("🔄 Navigating to Reported tab...")
        
        # Multiple selector strategies - most reliable first to minimize wait time
        reported_selectors = [
            "//div[contains(@class, 'reports-page__subtabs__tab') and contains(text(), 'Reported')]",  # This one works!
            "//div[@data-testid='sub-tab-reports.name.watering-reported']",
            "//button[contains(text(), 'Reported')]",
            "//*[contains(text(), 'Reported')]",
            "//button[@data-testid='reported-tab']"
        ]
        
        for selector in reported_selectors:
            try:
                # Use shorter wait for each selector to reduce total delay
                reported_element = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                reported_element.click()
                self.logger.info(f"✅ Clicked Reported tab using: {selector}")
                time.sleep(wait_seconds)  # Wait for data to load
                return True
            except Exception as e:
                self.logger.debug(f"Reported selector '{selector}' failed: {e}")
                continue
        
        self.logger.error("❌ Could not find or click Reported tab")
        return False
    
    # ========== VIEW SWITCHING ==========
    
    def switch_to_day_view(self, wait_seconds: int = 3) -> bool:
        """
        Switch to Day view with robust button detection and clicking
        
        Args:
            wait_seconds: Seconds to wait after clicking
            
        Returns:
            bool: True if successful
        """
        self.logger.info("🔄 Switching to Day view...")
        
        # Wait for UI to be ready
        time.sleep(2)
        
        # Multiple selector strategies
        day_selectors = [
            "//button[text()='Day']",  # Exact text match
            "//button[contains(text(), 'Day')]",  # Contains match
            "//button[contains(text(), 'day')]",  # lowercase
            "//button[@type='button' and contains(text(), 'day')]",
            "//button[contains(@class, 'rbc') and contains(text(), 'day')]",
            "//*[@data-testid='day-button']"
        ]
        
        # Quick check for immediately available buttons
        day_button = None
        successful_selector = None
        
        for selector in day_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for element in elements:
                    if element.is_displayed() and element.text.strip().lower() == 'day':
                        day_button = element
                        successful_selector = f"{selector} (immediate)"
                        break
                if day_button:
                    break
            except:
                continue
        
        # If not found, try general button search
        if not day_button:
            self.logger.info("Day button not immediately found, searching all buttons...")
            all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for button in all_buttons:
                try:
                    if button.text.strip().lower() == 'day' and button.is_displayed():
                        day_button = button
                        successful_selector = "General button search"
                        break
                except:
                    continue
        
        if day_button:
            try:
                # Try multiple click methods
                try:
                    day_button.click()
                    self.logger.info(f"✅ Clicked Day button (direct) using: {successful_selector}")
                except Exception as e:
                    self.logger.debug(f"Direct click failed: {e}")
                    # Try JavaScript click
                    self.driver.execute_script("arguments[0].click();", day_button)
                    self.logger.info(f"✅ Clicked Day button (JavaScript) using: {successful_selector}")
                
                time.sleep(wait_seconds)
                return True
            except Exception as e:
                self.logger.error(f"Failed to click Day button: {e}")
                return False
        else:
            self.logger.warning("⚠️ Could not find Day button - may already be in daily view")
            return True  # Assume already in day view
    
    def switch_to_week_view(self, wait_seconds: int = 3) -> bool:
        """
        Switch to Week view with robust button detection and clicking
        
        Args:
            wait_seconds: Seconds to wait after clicking
            
        Returns:
            bool: True if successful
        """
        self.logger.info("🔄 Switching to Week view...")
        
        week_selectors = [
            "//button[text()='Week']",
            "//button[contains(text(), 'Week')]",
            "//button[contains(text(), 'week')]",
            "//*[@data-testid='week-button']"
        ]
        
        return self._click_view_button(week_selectors, "Week", wait_seconds)
    
    def switch_to_month_view(self, wait_seconds: int = 3) -> bool:
        """
        Switch to Month view with robust button detection and clicking
        
        Args:
            wait_seconds: Seconds to wait after clicking
            
        Returns:
            bool: True if successful
        """
        self.logger.info("🔄 Switching to Month view...")
        
        month_selectors = [
            "//button[text()='Month']",
            "//button[contains(text(), 'Month')]",
            "//button[contains(text(), 'month')]",
            "//*[@data-testid='month-button']"
        ]
        
        return self._click_view_button(month_selectors, "Month", wait_seconds)
    
    def _click_view_button(self, selectors: List[str], button_name: str, wait_seconds: int) -> bool:
        """
        Optimized method to click view buttons with primary general search
        
        Args:
            selectors: List of XPath selectors to try (used as fallback)
            button_name: Name of button for logging
            wait_seconds: Seconds to wait after clicking
            
        Returns:
            bool: True if successful
        """
        # Step 1: PRIMARY METHOD - General button search (most reliable)
        self.logger.debug(f"Trying primary method for {button_name}: General button search...")
        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        
        for button in buttons:
            try:
                button_text = button.text.strip()
                if button_text.lower() == button_name.lower():
                    if button.is_enabled() and button.is_displayed():
                        return self._robust_click(button, button_name, "General button search (primary)", wait_seconds)
            except:
                continue
        
        # Step 2: FALLBACK - Use provided XPath selectors
        self.logger.debug(f"Primary method failed for {button_name}, trying XPath selectors...")
        for selector in selectors:
            try:
                button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                return self._robust_click(button, button_name, f"{selector} (fallback)", wait_seconds)
            except Exception as e:
                self.logger.debug(f"{button_name} selector '{selector}' failed: {e}")
                continue
        
        self.logger.error(f"❌ Could not find or click {button_name} button using any method")
        return False
    
    # ========== DATE NAVIGATION ==========
    
    def click_previous_button(self, wait_seconds: int = 3) -> bool:
        """
        Click Previous button with optimized detection order
        Prioritizes the most reliable method first (General button search)
        
        Args:
            wait_seconds: Seconds to wait after clicking
            
        Returns:
            bool: True if successful
        """
        self.logger.info("🔄 Clicking Previous button...")
        
        # Step 1: PRIMARY METHOD - General button search (most reliable)
        self.logger.debug("Trying primary method: General button search...")
        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        
        for button in buttons:
            try:
                button_text = button.text.strip()
                if button_text.lower() == "previous":
                    if button.is_enabled() and button.is_displayed():
                        return self._robust_click(button, "Previous", "General button search (primary)", wait_seconds)
            except:
                continue
        
        # Step 2: FALLBACK - Quick XPath selectors
        self.logger.debug("Primary method failed, trying XPath selectors...")
        quick_selectors = [
            "//button[text()='Previous']",
            "//button[contains(text(), 'Previous')]",
            "//button[contains(text(), 'previous')]"  # Add lowercase version
        ]
        
        for selector in quick_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return self._robust_click(element, "Previous", f"{selector} (fallback)", wait_seconds)
            except:
                continue
        
        # Step 3: LAST RESORT - Comprehensive search with wait
        self.logger.debug("XPath selectors failed, trying comprehensive search...")
        comprehensive_selectors = [
            "//button[normalize-space(text())='Previous']",
            "//button[contains(normalize-space(text()), 'Previous')]", 
            "//*[@type='button' and contains(text(), 'Previous')]",
            "//span[contains(text(), 'Previous')]/parent::button",
            "//*[contains(@class, 'button') and contains(text(), 'Previous')]",
            "//div[contains(@class, 'rbc-toolbar')]//button[contains(text(), 'Previous')]",
            "//div[contains(@class, 'rbc-btn-group')]//button[contains(text(), 'Previous')]"
        ]
        
        for selector in comprehensive_selectors:
            try:
                previous_button = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                return self._robust_click(previous_button, "Previous", f"{selector} (comprehensive)", wait_seconds)
            except:
                continue
        
        # If all methods fail
        self.logger.error("❌ Could not find Previous button using any method")
        self._debug_available_buttons()
        return False
    
    def click_next_button(self, wait_seconds: int = 3) -> bool:
        """
        Click Next button with optimized detection order
        Prioritizes the most reliable method first (General button search)
        
        Args:
            wait_seconds: Seconds to wait after clicking
            
        Returns:
            bool: True if successful
        """
        self.logger.info("🔄 Clicking Next button...")
        
        # Step 1: PRIMARY METHOD - General button search (most reliable)
        self.logger.debug("Trying primary method: General button search...")
        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        
        for button in buttons:
            try:
                button_text = button.text.strip()
                if button_text.lower() == "next":
                    if button.is_enabled() and button.is_displayed():
                        return self._robust_click(button, "Next", "General button search (primary)", wait_seconds)
            except:
                continue
        
        # Step 2: FALLBACK - Quick XPath selectors
        self.logger.debug("Primary method failed, trying XPath selectors...")
        quick_selectors = [
            "//button[text()='Next']",
            "//button[contains(text(), 'Next')]",
            "//button[contains(text(), 'next')]"  # Add lowercase version
        ]
        
        for selector in quick_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return self._robust_click(element, "Next", f"{selector} (fallback)", wait_seconds)
            except:
                continue
        
        # Step 3: LAST RESORT - Comprehensive search with wait
        self.logger.debug("XPath selectors failed, trying comprehensive search...")
        comprehensive_selectors = [
            "//div[contains(@class, 'rbc-toolbar')]//button[contains(text(), 'Next')]",
            "//div[contains(@class, 'rbc-btn-group')]//button[contains(text(), 'Next')]",
            "//*[text()='Next' and name()='button']",
            "//*[@type='button' and contains(text(), 'Next')]",
            "//span[contains(text(), 'Next')]/parent::button"
        ]
        
        for selector in comprehensive_selectors:
            try:
                next_button = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                return self._robust_click(next_button, "Next", f"{selector} (comprehensive)", wait_seconds)
            except Exception as e:
                self.logger.debug(f"Next comprehensive selector '{selector}' failed: {e}")
                continue
        
        # If all methods fail
        self.logger.error("❌ Could not find Next button using any method")
        self._debug_available_buttons()
        return False
    
    def _robust_click(self, element, button_name: str, selector_info: str, wait_seconds: int) -> bool:
        """
        Perform robust clicking with multiple fallback methods
        
        Args:
            element: WebElement to click
            button_name: Name for logging
            selector_info: Selector information for logging
            wait_seconds: Seconds to wait after clicking
            
        Returns:
            bool: True if successful
        """
        try:
            # Method 1: Direct click
            element.click()
            self.logger.info(f"✅ Clicked {button_name} button (direct) using: {selector_info}")
            time.sleep(wait_seconds)
            return True
        except Exception as e:
            self.logger.debug(f"Direct click failed: {e}")
            
            try:
                # Method 2: JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
                self.logger.info(f"✅ Clicked {button_name} button (JavaScript) using: {selector_info}")
                time.sleep(wait_seconds)
                return True
            except Exception as e:
                self.logger.debug(f"JavaScript click failed: {e}")
                
                try:
                    # Method 3: ActionChains click after scroll
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(1)
                    ActionChains(self.driver).move_to_element(element).click().perform()
                    self.logger.info(f"✅ Clicked {button_name} button (ActionChains) using: {selector_info}")
                    time.sleep(wait_seconds)
                    return True
                except Exception as e:
                    self.logger.error(f"All click methods failed for {button_name}: {e}")
                    return False
    
    # ========== DATE DETECTION AND PARSING ==========
    
    def get_current_displayed_date(self) -> Optional[str]:
        """
        Get currently displayed date from the page
        Based on working implementation from navigation_helper.py
        
        Returns:
            Optional[str]: Current displayed date string or None
        """
        try:
            # Look for date display element - prioritize rbc-toolbar-label
            primary_selectors = [
                "//span[contains(@class, 'rbc-toolbar-label')]",
                "//*[contains(@class, 'rbc-toolbar-label')]"
            ]
            
            # Try primary selectors first (most reliable)
            for selector in primary_selectors:
                try:
                    date_element = self.driver.find_element(By.XPATH, selector)
                    if date_element.is_displayed():
                        date_text = date_element.text.strip()
                        if date_text and len(date_text) > 3:
                            self.logger.debug(f"Found primary date display: '{date_text}' using: {selector}")
                            return date_text
                except:
                    continue
            
            # Fallback selectors for other patterns
            fallback_selectors = [
                # Day of week patterns
                "//*[contains(text(), 'Monday')]",
                "//*[contains(text(), 'Tuesday')]", 
                "//*[contains(text(), 'Wednesday')]",
                "//*[contains(text(), 'Thursday')]",
                "//*[contains(text(), 'Friday')]",
                "//*[contains(text(), 'Saturday')]",
                "//*[contains(text(), 'Sunday')]",
                # Month patterns
                "//*[contains(text(), 'Jan')]",
                "//*[contains(text(), 'Feb')]",
                "//*[contains(text(), 'Mar')]",
                "//*[contains(text(), 'Apr')]",
                "//*[contains(text(), 'May')]",
                "//*[contains(text(), 'Jun')]",
                "//*[contains(text(), 'Jul')]",
                "//*[contains(text(), 'Aug')]",
                "//*[contains(text(), 'Sep')]",
                "//*[contains(text(), 'Oct')]",
                "//*[contains(text(), 'Nov')]",
                "//*[contains(text(), 'Dec')]"
            ]
            
            for selector in fallback_selectors:
                try:
                    date_element = self.driver.find_element(By.XPATH, selector)
                    if date_element.is_displayed():
                        date_text = date_element.text.strip()
                        if date_text and len(date_text) > 3:
                            self.logger.debug(f"Found fallback date display: '{date_text}' using: {selector}")
                            return date_text
                except:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get current displayed date: {e}")
            return None
    
    def get_current_view_type(self) -> Optional[str]:
        """
        Determine current view type (day/week/month) by checking active buttons
        
        Returns:
            Optional[str]: 'day', 'week', 'month', or None
        """
        try:
            # Check for active button classes
            view_checks = [
                ("//button[contains(@class, 'rbc-active') and contains(text(), 'Day')]", "day"),
                ("//button[contains(@class, 'rbc-active') and contains(text(), 'Week')]", "week"),
                ("//button[contains(@class, 'rbc-active') and contains(text(), 'Month')]", "month"),
                ("//button[contains(@class, 'active') and contains(text(), 'Day')]", "day"),
                ("//button[contains(@class, 'active') and contains(text(), 'Week')]", "week"),
                ("//button[contains(@class, 'active') and contains(text(), 'Month')]", "month"),
            ]
            
            for selector, view_type in view_checks:
                try:
                    element = self.driver.find_element(By.XPATH, selector)
                    if element.is_displayed():
                        self.logger.debug(f"Detected {view_type} view using: {selector}")
                        return view_type
                except:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to determine view type: {e}")
            return None
    
    def parse_displayed_date_range(self, date_text: str) -> Optional[dict]:
        """
        Parse the displayed date range from rbc-toolbar-label text
        
        Handles formats like:
        - "August 24 – 30" (single month week)
        - "August 31 – September 06" (cross-month week)  
        - "Friday Aug 22" (day view)
        - "August 2025" (month view)
        
        Args:
            date_text: The text from rbc-toolbar-label
            
        Returns:
            dict: {
                'view_type': 'day'|'week'|'month',
                'start_date': date object,
                'end_date': date object (same as start for day view),
                'contains_target': bool (if target date is in range)
            }
        """
        try:
            import re
            
            current_year = date.today().year
            month_map = {
                'jan': 1, 'january': 1,
                'feb': 2, 'february': 2,
                'mar': 3, 'march': 3,
                'apr': 4, 'april': 4,
                'may': 5,
                'jun': 6, 'june': 6,
                'jul': 7, 'july': 7,
                'aug': 8, 'august': 8,
                'sep': 9, 'september': 9, 'sept': 9,  # Add 'sept' abbreviation
                'oct': 10, 'october': 10,
                'nov': 11, 'november': 11,
                'dec': 12, 'december': 12
            }
            
            date_text_lower = date_text.lower()
            
            # Week view patterns:
            # - Single month: "August 24 – 30" 
            # - Cross-month: "August 31 – September 06", "June 29 – July 05", "May 26 – Jun 01"
            # - Year boundary: "December 30 – January 05"
            # Pattern captures: (start_month) (start_day) [–-] (optional_end_month) (end_day)
            week_pattern = r'(\w+)\s+(\d+)\s*[–-]\s*(?:(\w+)\s+)?(\d+)'
            week_match = re.search(week_pattern, date_text_lower)
            
            if week_match:
                start_month_name = week_match.group(1)
                start_day = int(week_match.group(2))
                end_month_name = week_match.group(3) if week_match.group(3) else start_month_name
                end_day = int(week_match.group(4))
                
                self.logger.debug(f"Week parsing: '{date_text}' -> start='{start_month_name} {start_day}', end='{end_month_name} {end_day}'")
                
                start_month = month_map.get(start_month_name, None)
                end_month = month_map.get(end_month_name, None)
                
                if start_month is None:
                    self.logger.warning(f"Could not map start month '{start_month_name}' in '{date_text}'")
                    return None
                if end_month is None:
                    self.logger.warning(f"Could not map end month '{end_month_name}' in '{date_text}'")
                    return None
                
                # Handle year boundaries (though rare)
                start_year = current_year
                end_year = current_year
                if start_month > end_month:  # Dec -> Jan
                    end_year = current_year + 1
                
                start_date = date(start_year, start_month, start_day)
                end_date = date(end_year, end_month, end_day)
                
                return {
                    'view_type': 'week',
                    'start_date': start_date,
                    'end_date': end_date,
                    'original_text': date_text
                }
            
            # Day view: "Friday Aug 22" or "Friday August 22"
            day_pattern = r'(?:\w+\s+)?(\w+)\s+(\d+)'
            day_match = re.search(day_pattern, date_text_lower)
            
            if day_match:
                month_name = day_match.group(1)
                day_num = int(day_match.group(2))
                
                month_num = month_map.get(month_name, 1)
                target_date = date(current_year, month_num, day_num)
                
                return {
                    'view_type': 'day',
                    'start_date': target_date,
                    'end_date': target_date,
                    'original_text': date_text
                }
            
            # Month view: "August 2025" or just "August"
            month_pattern = r'(\w+)(?:\s+(\d{4}))?'
            month_match = re.search(month_pattern, date_text_lower)
            
            if month_match:
                month_name = month_match.group(1)
                year = int(month_match.group(2)) if month_match.group(2) else current_year
                
                month_num = month_map.get(month_name, 1)
                
                # Month view - start is first day, end is last day
                import calendar
                start_date = date(year, month_num, 1)
                last_day = calendar.monthrange(year, month_num)[1]
                end_date = date(year, month_num, last_day)
                
                return {
                    'view_type': 'month',
                    'start_date': start_date,
                    'end_date': end_date,
                    'original_text': date_text
                }
            
            # If no pattern matches, return None
            self.logger.warning(f"Could not parse date text: '{date_text}'")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to parse displayed date range: {e}")
            return None
    
    def is_target_date_in_current_view(self, target_date: date) -> bool:
        """
        Check if target date is currently visible in the current view
        
        Args:
            target_date: Date we're looking for
            
        Returns:
            bool: True if target date is in current view
        """
        try:
            current_display = self.get_current_displayed_date()
            if not current_display:
                return False
            
            parsed_range = self.parse_displayed_date_range(current_display)
            if not parsed_range:
                return False
            
            # Check if target date is within the displayed range
            is_in_range = (parsed_range['start_date'] <= target_date <= parsed_range['end_date'])
            
            self.logger.debug(f"Target {target_date} in range {parsed_range['start_date']} to {parsed_range['end_date']}: {is_in_range}")
            return is_in_range
            
        except Exception as e:
            self.logger.error(f"Failed to check if target date is in current view: {e}")
            return False
    
    # ========== HIGH-LEVEL NAVIGATION FUNCTIONS ==========
    
    def navigate_to_date(self, target_date: Union[date, datetime], tab: str = "schedule") -> bool:
        """
        Navigate to a specific date using intelligent hierarchical navigation strategy
        
        Args:
            target_date: Target date to navigate to
            tab: 'schedule' or 'reported'
            
        Returns:
            bool: True if successful
        """
        try:
            # Convert to date if datetime
            if isinstance(target_date, datetime):
                target_date = target_date.date()
            
            current_date = date.today()
            days_diff = (target_date - current_date).days
            
            self.logger.info(f"🎯 Navigating to {target_date} ({days_diff:+d} days from today)")
            
            # Navigate to appropriate tab
            if tab.lower() == "schedule":
                if not self.navigate_to_schedule_tab():
                    return False
            elif tab.lower() == "reported":
                if not self.navigate_to_reported_tab():
                    return False
            
            # Use intelligent navigation strategy based on date difference
            if abs(days_diff) == 0:
                self.logger.info("✅ Already on target date")
                # Still ensure we're in day view
                return self.switch_to_day_view()
            elif abs(days_diff) <= 6:
                # Small difference: Use day view directly
                self.logger.info(f"📅 Small date difference ({abs(days_diff)} days) - using day navigation")
                return self._navigate_using_day_view(target_date, current_date)
            elif abs(days_diff) <= 30:
                # Medium difference: Use week view then day view
                self.logger.info(f"📅 Medium date difference ({abs(days_diff)} days) - using week navigation")
                return self._navigate_using_week_view(target_date, current_date)
            else:
                # Large difference: Use month view, then week view, then day view
                self.logger.info(f"📅 Large date difference ({abs(days_diff)} days) - using hierarchical navigation")
                return self._navigate_using_month_view(target_date, current_date)
                
        except Exception as e:
            self.logger.error(f"❌ Failed to navigate to date {target_date}: {e}")
            return False
    
    def navigate_date_range(self, start_date: Union[date, datetime], 
                           end_date: Union[date, datetime], tab: str = "schedule") -> List[date]:
        """
        Navigate through a date range, returning list of successfully navigated dates
        
        Args:
            start_date: Start date of range
            end_date: End date of range  
            tab: 'schedule' or 'reported'
            
        Returns:
            List[date]: List of dates successfully navigated to
        """
        try:
            # Convert to dates if datetime
            if isinstance(start_date, datetime):
                start_date = start_date.date()
            if isinstance(end_date, datetime):
                end_date = end_date.date()
            
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            
            self.logger.info(f"🗓️ Navigating date range: {start_date} to {end_date}")
            
            successful_dates = []
            current_date = start_date
            
            # Navigate to start date
            if self.navigate_to_date(current_date, tab):
                successful_dates.append(current_date)
                
                # Navigate through remaining dates
                while current_date < end_date:
                    if self.click_next_button():
                        current_date += timedelta(days=1)
                        successful_dates.append(current_date)
                        
                        # Verify we're on the right date
                        displayed_date = self.get_current_displayed_date()
                        if displayed_date:
                            self.logger.info(f"📅 Now on: {displayed_date}")
                    else:
                        self.logger.error(f"❌ Failed to navigate to {current_date + timedelta(days=1)}")
                        break
            
            self.logger.info(f"✅ Successfully navigated to {len(successful_dates)} dates")
            return successful_dates
            
        except Exception as e:
            self.logger.error(f"❌ Failed to navigate date range: {e}")
            return []
    
    def _navigate_forward_days(self, days: int) -> bool:
        """Navigate forward by specified number of days"""
        try:
            for day in range(days):
                if not self.click_next_button():
                    self.logger.error(f"❌ Failed to navigate forward on day {day + 1}/{days}")
                    return False
                    
                # Log progress
                displayed_date = self.get_current_displayed_date()
                if displayed_date:
                    self.logger.info(f"📅 Day {day + 1}/{days}: {displayed_date}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to navigate forward {days} days: {e}")
            return False
    
    def _navigate_backward_days(self, days: int) -> bool:
        """Navigate backward by specified number of days"""
        try:
            for day in range(days):
                if not self.click_previous_button():
                    self.logger.error(f"❌ Failed to navigate backward on day {day + 1}/{days}")
                    return False
                    
                # Log progress
                displayed_date = self.get_current_displayed_date()
                if displayed_date:
                    self.logger.info(f"📅 Day {day + 1}/{days}: {displayed_date}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to navigate backward {days} days: {e}")
            return False
    
    # ========== INTELLIGENT HIERARCHICAL NAVIGATION ==========
    
    def _fine_tune_to_exact_day(self, target_date: date, max_attempts: int = 10) -> bool:
        """
        Fine-tune navigation to exact day when already in the right week/month
        
        Args:
            target_date: Target date to navigate to
            max_attempts: Maximum navigation attempts to prevent infinite loops
            
        Returns:
            bool: True if successfully navigated to target date
        """
        try:
            self.logger.info(f"🔧 Fine-tuning to exact day: {target_date}")
            
            for attempt in range(max_attempts):
                # Check if we've found the target
                if self.is_target_date_in_current_view(target_date):
                    current_display = self.get_current_displayed_date()
                    self.logger.info(f"✅ Successfully navigated to target: {current_display}")
                    return True
                
                # Parse current position to determine direction
                current_display = self.get_current_displayed_date()
                if not current_display:
                    self.logger.warning("⚠️ Could not get current display for fine-tuning")
                    return False
                
                parsed_range = self.parse_displayed_date_range(current_display)
                if not parsed_range:
                    self.logger.warning("⚠️ Could not parse current display for fine-tuning")
                    return False
                
                # Determine direction based on current position
                if target_date < parsed_range['start_date']:
                    # Target is before current view - go backward
                    if not self.click_previous_button():
                        self.logger.error("❌ Failed to navigate backward during fine-tuning")
                        return False
                    self.logger.info(f"📅 Fine-tune {attempt + 1}: backward")
                elif target_date > parsed_range['end_date']:
                    # Target is after current view - go forward
                    if not self.click_next_button():
                        self.logger.error("❌ Failed to navigate forward during fine-tuning")
                        return False
                    self.logger.info(f"📅 Fine-tune {attempt + 1}: forward")
                else:
                    # Target should be in current range but check failed
                    self.logger.warning(f"⚠️ Target {target_date} should be in range {parsed_range['start_date']} to {parsed_range['end_date']} but not detected")
                    return True  # Assume success
                
                time.sleep(1)  # Allow transition to complete
            
            self.logger.warning(f"⚠️ Could not fine-tune to exact day after {max_attempts} attempts")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Fine-tuning failed: {e}")
            return False
    
    def _navigate_using_day_view(self, target_date: date, current_date: date) -> bool:
        """Navigate using day view for small date differences (<= 6 days)"""
        try:
            self.logger.info("🔄 Using day view navigation...")
            
            # Switch to day view
            if not self.switch_to_day_view():
                return False
            
            # Calculate difference and navigate
            days_diff = (target_date - current_date).days
            
            if days_diff > 0:
                return self._navigate_forward_days(days_diff)
            else:
                return self._navigate_backward_days(abs(days_diff))
                
        except Exception as e:
            self.logger.error(f"❌ Day view navigation failed: {e}")
            return False
    
    def _navigate_using_week_view(self, target_date: date, current_date: date) -> bool:
        """Navigate using week view for medium date differences (7-30 days)"""
        try:
            self.logger.info("🔄 Using week view navigation...")
            
            # Switch to week view
            if not self.switch_to_week_view():
                return False
            
            # Check if target is already in current week view
            if self.is_target_date_in_current_view(target_date):
                self.logger.info("✅ Target date already in current week view")
                # Switch to day view for final positioning
                if not self.switch_to_day_view():
                    return False
                return self._fine_tune_to_exact_day(target_date)
            
            # Calculate week difference using intelligent parsing
            max_week_attempts = 10  # Prevent infinite loops
            
            for attempt in range(max_week_attempts):
                current_display = self.get_current_displayed_date()
                if not current_display:
                    self.logger.error("❌ Could not get current week display")
                    return False
                
                parsed_range = self.parse_displayed_date_range(current_display)
                if not parsed_range:
                    self.logger.error("❌ Could not parse current week range")
                    return False
                
                self.logger.info(f"📅 Current week: {parsed_range['original_text']}")
                self.logger.info(f"📅 Range: {parsed_range['start_date']} to {parsed_range['end_date']}")
                
                # Check if we've found our target
                if parsed_range['start_date'] <= target_date <= parsed_range['end_date']:
                    self.logger.info("✅ Target date found in current week")
                    # Switch to day view for final positioning
                    if not self.switch_to_day_view():
                        return False
                    return self._fine_tune_to_exact_day(target_date)
                
                # Determine navigation direction
                if target_date < parsed_range['start_date']:
                    # Target is before current week - go backward
                    if not self.click_previous_button():
                        self.logger.error("❌ Failed to navigate backward week")
                        return False
                    self.logger.info(f"📅 Week {attempt + 1}: backward to reach {target_date}")
                else:
                    # Target is after current week - go forward
                    if not self.click_next_button():
                        self.logger.error("❌ Failed to navigate forward week")
                        return False
                    self.logger.info(f"📅 Week {attempt + 1}: forward to reach {target_date}")
                
                time.sleep(1)  # Allow week transition to complete
            
            self.logger.warning("⚠️ Could not reach target week after maximum attempts")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Week view navigation failed: {e}")
            return False
    
    def _navigate_using_month_view(self, target_date: date, current_date: date) -> bool:
        """Navigate using month view for large date differences (> 30 days)"""
        try:
            self.logger.info("🔄 Using month view navigation...")
            
            # Switch to month view
            if not self.switch_to_month_view():
                return False
            
            # Calculate month difference
            target_month = target_date.replace(day=1)
            current_month = current_date.replace(day=1)
            
            # Calculate difference in months
            months_diff = (target_month.year - current_month.year) * 12 + (target_month.month - current_month.month)
            
            self.logger.info(f"📅 Need to navigate {months_diff:+d} months")
            
            # Navigate by months
            if months_diff > 0:
                for month in range(months_diff):
                    if not self.click_next_button():
                        self.logger.error(f"❌ Failed to navigate forward month {month + 1}/{months_diff}")
                        return False
                    self.logger.info(f"📅 Month {month + 1}/{months_diff} forward")
                    time.sleep(1)  # Extra pause for month transitions
            elif months_diff < 0:
                for month in range(abs(months_diff)):
                    if not self.click_previous_button():
                        self.logger.error(f"❌ Failed to navigate backward month {month + 1}/{abs(months_diff)}")
                        return False
                    self.logger.info(f"📅 Month {month + 1}/{abs(months_diff)} backward")
                    time.sleep(1)  # Extra pause for month transitions
            
            # Now switch to week view and use intelligent navigation
            self.logger.info("📅 Switching to week view for precise positioning...")
            if not self.switch_to_week_view():
                return False
            
            # Use the same intelligent week navigation logic as _navigate_using_week_view
            max_week_attempts = 10  # Prevent infinite loops
            
            for attempt in range(max_week_attempts):
                # Check if we've found our target week
                if self.is_target_date_in_current_view(target_date):
                    self.logger.info("✅ Target date found in current week")
                    # Switch to day view for final positioning
                    if not self.switch_to_day_view():
                        return False
                    return self._fine_tune_to_exact_day(target_date)
                
                # Get current week range using intelligent parsing
                current_display = self.get_current_displayed_date()
                if not current_display:
                    self.logger.error("❌ Could not get current week display")
                    return False
                
                parsed_range = self.parse_displayed_date_range(current_display)
                if not parsed_range:
                    self.logger.error("❌ Could not parse current week range")
                    return False
                
                self.logger.info(f"📅 Current week: {parsed_range['original_text']}")
                self.logger.info(f"📅 Range: {parsed_range['start_date']} to {parsed_range['end_date']}")
                self.logger.info(f"📅 Target: {target_date}")
                
                # Determine navigation direction based on intelligent parsing
                if target_date < parsed_range['start_date']:
                    # Target is before current week - go backward
                    if not self.click_previous_button():
                        self.logger.error("❌ Failed to navigate backward week")
                        return False
                    self.logger.info(f"📅 Week {attempt + 1}: backward to reach {target_date}")
                elif target_date > parsed_range['end_date']:
                    # Target is after current week - go forward
                    if not self.click_next_button():
                        self.logger.error("❌ Failed to navigate forward week")
                        return False
                    self.logger.info(f"📅 Week {attempt + 1}: forward to reach {target_date}")
                else:
                    # Target should be in current range but check failed
                    self.logger.info("✅ Target date should be in current week based on parsing")
                    # Switch to day view for final positioning
                    if not self.switch_to_day_view():
                        return False
                    return self._fine_tune_to_exact_day(target_date)
                
                time.sleep(1)  # Allow week transition to complete
            
            self.logger.warning("⚠️ Could not reach target week after maximum attempts")
            # Try to proceed anyway - switch to day view for final attempts
            if self.switch_to_day_view():
                return self._fine_tune_to_exact_day(target_date)
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Month view navigation failed: {e}")
            return False
    
    # ========== DEBUGGING AND UTILITY ==========
    
    def _debug_available_buttons(self):
        """Debug method to see what buttons are available on the page"""
        try:
            self.logger.info("🔍 Debugging available buttons on the page...")
            
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
            
            # Also look for navigation-related elements
            nav_elements = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'rbc') or contains(text(), 'Next') or contains(text(), 'Previous')]")
            self.logger.info(f"Found {len(nav_elements)} navigation-related elements")
            
        except Exception as e:
            self.logger.error(f"Error in debug method: {e}")
    
    def get_navigation_status(self) -> dict:
        """
        Get comprehensive status of current navigation state
        
        Returns:
            dict: Status information including current date, view, tab, etc.
        """
        try:
            status = {
                'current_displayed_date': self.get_current_displayed_date(),
                'current_view_type': self.get_current_view_type(),
                'navigation_buttons_available': {
                    'previous': False,
                    'next': False
                }
            }
            
            # Check button availability
            try:
                self.driver.find_element(By.XPATH, "//button[contains(text(), 'Previous')]")
                status['navigation_buttons_available']['previous'] = True
            except:
                pass
            
            try:
                self.driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]")
                status['navigation_buttons_available']['next'] = True
            except:
                pass
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get navigation status: {e}")
            return {}


# ========== CONVENIENCE FUNCTIONS ==========

def create_navigation_helper(scraper) -> HydrawiseNavigationHelper:
    """
    Create navigation helper instance
    
    Args:
        scraper: HydrawiseWebScraper instance
        
    Returns:
        HydrawiseNavigationHelper: Configured navigation helper
    """
    return HydrawiseNavigationHelper(scraper)


def navigate_to_date_for_collection(scraper, target_date: Union[date, datetime], 
                                   collection_type: str = "schedule") -> bool:
    """
    Convenience function for navigating to a date for data collection
    
    Args:
        scraper: HydrawiseWebScraper instance
        target_date: Date to navigate to
        collection_type: 'schedule' or 'reported'
        
    Returns:
        bool: True if successful
    """
    nav_helper = create_navigation_helper(scraper)
    return nav_helper.navigate_to_date(target_date, collection_type)
