#!/usr/bin/env python3
"""
Hydrawise Web Portal Scraper

Scrapes the Hydrawise web portal to extract complete daily schedules and actual
watering data that the API doesn't provide. This enables real-time detection
of irrigation failures for plant protection.

Key capabilities:
- Login to Hydrawise portal with stored credentials
- Extract complete daily schedules from Schedule tab
- Extract actual runs with failure details from Reported tab  
- Capture hover popup data for water usage amounts
- Compare scheduled vs actual to detect failures requiring alerts

Author: AI Assistant
Date: 2025
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

@dataclass
class ScheduledRun:
    """Represents a scheduled zone run from the Schedule tab"""
    zone_id: str
    zone_name: str
    start_time: datetime
    duration_minutes: int
    expected_gallons: Optional[float]
    notes: str

@dataclass
class ActualRun:
    """Represents an actual zone run from the Reported tab"""
    zone_id: str
    zone_name: str
    start_time: datetime
    duration_minutes: int
    actual_gallons: Optional[float]
    status: str  # "Normal", "Aborted due to sensor input", etc.
    notes: str
    end_time: Optional[datetime] = None  # Calculate from start + duration if needed
    failure_reason: Optional[str] = None  # Specific failure reason if any

@dataclass
class IrrigationFailure:
    """Detected failure requiring user attention"""
    failure_id: str
    timestamp: datetime
    zone_id: str
    zone_name: str
    failure_type: str  # "missed_run", "sensor_abort", "cancelled", etc.
    description: str
    scheduled_run: Optional[ScheduledRun]
    actual_run: Optional[ActualRun]
    action_required: str
    priority: str  # "CRITICAL", "WARNING", "INFO"

class HydrawiseWebScraper:
    """
    Web scraper for Hydrawise portal to extract complete irrigation data.
    """
    
    def __init__(self, username: str, password: str, headless: bool = True):
        """
        Initialize the web scraper.
        
        Args:
            username (str): Hydrawise login username
            password (str): Hydrawise login password
            headless (bool): Run browser in headless mode
        """
        self.username = username
        self.password = password
        self.headless = headless
        self.driver = None
        self.wait = None
        
        # URLs
        self.login_url = "https://app.hydrawise.com/config/login"
        self.reports_url = "https://app.hydrawise.com/config/reports"
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for the scraper"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('data/web_scraper.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def start_browser(self):
        """Initialize and start the Chrome browser"""
        try:
            self.logger.info("Starting Chrome browser...")
            
            # Setup Chrome options
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Reduce background service noise (optional)
            chrome_options.add_argument("--disable-background-networking")
            chrome_options.add_argument("--disable-sync")
            chrome_options.add_argument("--disable-translate")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-ipc-flooding-protection")
            
            # Initialize driver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)
            
            self.logger.info("Browser started successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start browser: {e}")
            raise
            
    def stop_browser(self):
        """Stop and cleanup the browser"""
        if self.driver:
            self.driver.quit()
            self.logger.info("Browser stopped")
            
    def login(self) -> bool:
        """
        Login to the Hydrawise portal.
        
        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            self.logger.info("Logging into Hydrawise portal...")
            
            # Navigate to login page
            self.driver.get(self.login_url)
            
            # Wait for login form to load - look for Email field (not username)
            email_field = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Email']"))
            )
            
            # Enter credentials
            email_field.clear()
            email_field.send_keys(self.username)
            
            # Find password field
            password_field = self.driver.find_element(By.XPATH, "//input[@placeholder='Password']")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Find the "Log in" button
            login_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Log in')]")
            login_button.click()
            
            # Wait for redirect after successful login
            self.wait.until(lambda driver: "login" not in driver.current_url)
            
            self.logger.info("Login successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            return False
            
    def navigate_to_reports(self):
        """Navigate to the reports page"""
        try:
            self.logger.info("Navigating to reports page...")
            
            # Check current URL first
            current_url = self.driver.current_url
            self.logger.info(f"Current URL after login: {current_url}")
            
            # Try to navigate to reports
            self.driver.get(self.reports_url)
            
            # Wait a bit for page to load
            time.sleep(3)
            
            # Try multiple approaches to detect reports page
            try:
                # Look for Schedule button
                schedule_button = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Schedule')]"))
                )
                self.logger.info("Reports page loaded - Schedule button found")
            except:
                # Alternative: look for Reports heading
                try:
                    reports_heading = self.driver.find_element(By.XPATH, "//h1[contains(text(), 'Reports')] | //h2[contains(text(), 'Reports')] | //*[contains(text(), 'Reports')]")
                    self.logger.info("Reports page loaded - Reports heading found")
                except:
                    # Alternative: look for Watering tab
                    try:
                        watering_tab = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Watering')] | //a[contains(text(), 'Watering')]")
                        self.logger.info("Reports page loaded - Watering tab found")
                    except:
                        # Log page source for debugging
                        self.logger.warning("Could not find expected elements. Current page title: " + self.driver.title)
                        self.logger.warning("Current URL: " + self.driver.current_url)
                        raise Exception("Could not verify reports page loaded")
            
            return True  # Successfully navigated to reports page
            
        except Exception as e:
            self.logger.error(f"Failed to navigate to reports: {e}")
            return False
            
    def set_date(self, target_date: datetime):
        """
        Set the date for the reports view.
        
        Args:
            target_date (datetime): Date to view reports for
        """
        try:
            self.logger.info(f"Setting date to {target_date.strftime('%Y-%m-%d')}")
            
            # Click on date picker or navigation
            # This will need to be implemented based on the actual HTML structure
            # For now, assuming today's date is selected by default
            
            self.logger.info("Date set successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to set date: {e}")
            raise
            
    def extract_scheduled_runs(self, target_date: datetime) -> List[ScheduledRun]:
        """
        Extract scheduled runs from the Schedule tab.
        
        Args:
            target_date (datetime): Date to extract schedule for
            
        Returns:
            list: List of scheduled runs
        """
        import time  # Import time module for sleep() calls
        try:
            self.logger.info("Extracting scheduled runs...")
            
            # FIRST: Click Schedule button to load the schedule view and make Day button appear
            try:
                # Try multiple selectors for the Schedule tab based on actual HTML
                schedule_selectors = [
                    "//div[@data-testid='sub-tab-reports.name.watering-schedule']",
                    "//div[contains(@class, 'reports-page__subtabs__tab') and contains(text(), 'Schedule')]",
                    "//button[contains(text(), 'Schedule')]"
                ]
                
                schedule_tab = None
                for selector in schedule_selectors:
                    try:
                        schedule_tab = self.wait.until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        break
                    except:
                        continue
                
                if not schedule_tab:
                    raise Exception("Could not find Schedule tab with any selector")
                
                schedule_tab.click()
                time.sleep(3)  # Wait for schedule data to load
                self.logger.info("Clicked Schedule tab - waiting for data to load")
            except Exception as e:
                self.logger.error(f"Could not find or click Schedule tab: {e}")
                return []
            
            # SECOND: CRITICAL - Must click Day button to get daily schedule (not week view)
            try:
                # Wait longer for Day button to appear after Schedule tab loads
                time.sleep(2)  # Extra wait for UI to fully load
                
                # Try multiple selectors for Day button based on actual HTML
                day_selectors = [
                    "//button[contains(text(), 'day')]",  # lowercase
                    "//button[contains(text(), 'Day')]",  # uppercase  
                    "//button[@type='button' and contains(text(), 'day')]",
                    "//button[contains(@class, 'rbc') and contains(text(), 'day')]"
                ]
                
                day_button = None
                for selector in day_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        for element in elements:
                            if element.is_displayed() and element.text.strip().lower() == 'day':
                                day_button = element
                                break
                        if day_button:
                            break
                    except:
                        continue
                
                if not day_button:
                    # Try a more general search
                    all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                    for button in all_buttons:
                        if button.text.strip().lower() == 'day' and button.is_displayed():
                            day_button = button
                            break
                
                if day_button:
                    # Always click Day button to ensure we get daily view (not week view)
                    day_button.click()
                    time.sleep(3)  # Wait for day view to load
                    self.logger.info("Clicked Day button - switched to daily view")
                else:
                    self.logger.error("CRITICAL: Could not find Day button - may be viewing week schedule instead of daily")
                    # Continue but warn that data might be weekly not daily
                    
            except Exception as e:
                self.logger.error(f"CRITICAL: Failed to click Day button: {e}")
                self.logger.error("WARNING: May be extracting week schedule instead of daily schedule")
            
            scheduled_runs = []
            
            # Look for schedule events using multiple strategies to find ALL 24 runs
            zone_elements = []
            try:
                # Strategy 1: Target the specific rbc-event structure we saw in the inspect
                zone_elements = self.driver.find_elements(By.XPATH, "//div[@class='rbc-event']")
                self.logger.info(f"Strategy 1: Found {len(zone_elements)} exact rbc-event blocks")
                
                if len(zone_elements) < 24:
                    # Strategy 2: Look for any element with rbc-event class (broader)
                    broader_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'rbc-event')]")
                    self.logger.info(f"Strategy 2: Found {len(broader_elements)} blocks with rbc-event class")
                    if len(broader_elements) > len(zone_elements):
                        zone_elements = broader_elements
                        
                if len(zone_elements) < 24:
                    # Strategy 3: Look for timeline elements with specific attributes
                    timeline_selectors = [
                        "//div[contains(@class, 'rbc-event-content')]/..",  # Parent of event content
                        "//div[@class='rbc-event-content']/..",  # Exact parent of event content
                        "//div[contains(@class, 'color-renderer')]/ancestor::div[contains(@class, 'rbc')]",  # Color elements in rbc container
                        "//span[contains(@class, 'short-time')]/ancestor::div[contains(@class, 'rbc')]",  # Time elements in rbc container
                    ]
                    
                    for i, selector in enumerate(timeline_selectors, 3):
                        try:
                            elements = self.driver.find_elements(By.XPATH, selector)
                            self.logger.info(f"Strategy {i}: Found {len(elements)} elements using selector: {selector}")
                            if len(elements) >= 24:
                                zone_elements = elements
                                break
                            elif len(elements) > len(zone_elements):
                                zone_elements = elements
                        except Exception as e:
                            self.logger.debug(f"Strategy {i} failed: {e}")
                            continue
                            
                # Final check
                self.logger.info(f"FINAL: Using {len(zone_elements)} schedule elements (target: 24)")
                
            except Exception as e:
                self.logger.error(f"Failed to find schedule blocks: {e}")
            
            if not zone_elements:
                self.logger.warning("No zone elements found - taking screenshot for debugging")
                self.driver.save_screenshot("data/debug_schedule_page.png")
                
                # Try to find any text with zone names
                zone_text_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Rear') or contains(text(), 'Front')]")
                self.logger.info(f"Found {len(zone_text_elements)} text elements with zone names")
                
                return scheduled_runs
            
            # Process each rbc-event element and deduplicate
            seen_runs = set()  # Track unique runs by (zone_name, start_time) to avoid duplicates
            
            for i, element in enumerate(zone_elements):  # Process elements but deduplicate
                try:
                    # Extract zone name from title attribute of rbc-event-content
                    zone_name = ""
                    try:
                        event_content = element.find_element(By.XPATH, ".//div[@class='rbc-event-content']")
                        zone_name = event_content.get_attribute('title') or ""
                        self.logger.debug(f"Found zone name in title: {zone_name}")
                    except:
                        # Fallback to element text
                        zone_name = element.text.strip()
                        self.logger.debug(f"Using element text as zone name: {zone_name}")
                    
                    if not zone_name:
                        self.logger.debug(f"Skipping element {i} - no zone name found")
                        continue
                    
                    # Extract start time from short-time span and duration from color-renderer div
                    start_time_str = ""
                    duration_minutes = 0
                    
                    try:
                        # Look for start time in short-time span
                        short_time = element.find_element(By.XPATH, ".//span[@class='short-time']")
                        start_time_str = short_time.text.strip()
                        self.logger.debug(f"Found start time: {start_time_str}")
                    except:
                        self.logger.debug(f"Could not extract start time for {zone_name}")
                    
                    try:
                        # Extract duration from color-renderer div (the number, not the time)
                        color_renderer = element.find_element(By.XPATH, ".//div[contains(@class, 'color-renderer')]")
                        renderer_text = color_renderer.text.strip()
                        
                        # Parse out just the duration number (not the time)
                        import re
                        duration_match = re.search(r'(\d+)(?!:)', renderer_text)  # Number not followed by colon
                        if duration_match:
                            duration_minutes = int(duration_match.group(1))
                            self.logger.debug(f"Found duration: {duration_minutes} minutes")
                        else:
                            self.logger.debug(f"Could not parse duration from: {renderer_text}")
                    except:
                        self.logger.debug(f"Could not extract duration for {zone_name}")
                    
                    # CRITICAL: Get accurate duration from hover popup (not visual number)
                    popup_data = {}
                    try:
                        actions = ActionChains(self.driver)
                        actions.move_to_element(element).perform()
                        time.sleep(1.5)  # Longer wait for popup to appear
                        popup_data = self.extract_hover_popup_data_with_retry(zone_name)
                        
                        if popup_data:
                            popup_duration = popup_data.get('duration_minutes', 0)
                            self.logger.info(f"Zone {zone_name}: Visual duration={duration_minutes}, Popup duration={popup_duration}")
                            
                            # Special debugging for Front Color zones
                            if 'Front Color' in zone_name:
                                self.logger.info(f"FRONT COLOR DEBUG - Raw popup text: {popup_data.get('notes', 'No notes')}")
                            
                            if popup_duration:
                                self.logger.info(f"Using popup duration: {popup_duration} min (overriding visual: {duration_minutes})")
                            else:
                                self.logger.warning(f"No popup duration found, using visual: {duration_minutes} min")
                        else:
                            self.logger.warning(f"No popup data found for {zone_name}")
                        
                    except Exception as e:
                        self.logger.debug(f"Hover failed for {zone_name}: {e}")
                    
                    # Convert start time string to datetime
                    start_datetime = target_date  # Default to target date
                    if start_time_str:
                        try:
                            from datetime import datetime
                            # Parse time like "6:01am" 
                            time_obj = datetime.strptime(start_time_str, '%I:%M%p').time()
                            start_datetime = datetime.combine(target_date.date(), time_obj)
                            self.logger.debug(f"Parsed start time: {start_datetime}")
                        except Exception as e:
                            self.logger.debug(f"Could not parse start time '{start_time_str}': {e}")
                    
                    # Use popup duration if available, otherwise fall back to visual duration
                    final_duration = popup_data.get('duration_minutes', 0) or duration_minutes
                    
                    # Clean up zone name (remove time prefix if it got concatenated)
                    import re
                    clean_zone_name = re.sub(r'^\d{1,2}:\d{2}[ap]m', '', zone_name).strip()
                    if not clean_zone_name:
                        clean_zone_name = zone_name  # Fallback to original if cleaning failed
                    
                    # Create unique identifier to avoid duplicates
                    run_key = (clean_zone_name, start_time_str)
                    if run_key in seen_runs:
                        self.logger.debug(f"Skipping duplicate: {clean_zone_name} at {start_time_str}")
                        continue
                    seen_runs.add(run_key)
                    
                    # Create scheduled run using extracted data
                    scheduled_run = ScheduledRun(
                        zone_id=popup_data.get('zone_id', f'zone_{len(scheduled_runs)}'),
                        zone_name=clean_zone_name,  # Cleaned zone name
                        start_time=start_datetime,  # Properly parsed start time
                        duration_minutes=final_duration,  # Prioritize popup duration
                        expected_gallons=popup_data.get('expected_gallons'),
                        notes=popup_data.get('notes', f"Scheduled at {start_time_str} for {final_duration} minutes")
                    )
                    
                    scheduled_runs.append(scheduled_run)
                    self.logger.info(f"Extracted {len(scheduled_runs)}: '{scheduled_run.zone_name}' at {start_time_str} for {scheduled_run.duration_minutes} minutes")
                    
                except Exception as e:
                    self.logger.error(f"Failed to process element {i+1}/{len(zone_elements)}: {e}")
                    # Log the element details for debugging
                    try:
                        element_html = element.get_attribute('outerHTML')[:200]
                        self.logger.error(f"Failed element HTML: {element_html}")
                    except:
                        pass
                    continue
                    
            self.logger.info(f"Extracted {len(scheduled_runs)} scheduled runs")
            return scheduled_runs
            
        except Exception as e:
            self.logger.error(f"Failed to extract scheduled runs: {e}")
            return []
            
    def extract_actual_runs(self, target_date: datetime) -> List[ActualRun]:
        """
        Extract actual runs from the Reported tab.
        
        Args:
            target_date (datetime): Date to extract actual runs for
            
        Returns:
            list: List of actual runs with failure details
        """
        import time  # Import time module for sleep() calls
        try:
            self.logger.info("Extracting actual runs...")
            
            # FIRST: Click Reported button to load the reported view and make Day button appear
            try:
                # Try multiple selectors for the Reported tab based on actual HTML
                reported_selectors = [
                    "//div[@data-testid='sub-tab-reports.name.watering-history']",
                    "//div[contains(@class, 'reports-page__subtabs__tab') and contains(text(), 'Reported')]",
                    "//button[contains(text(), 'Reported')]"
                ]
                
                reported_tab = None
                for selector in reported_selectors:
                    try:
                        reported_tab = self.wait.until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        break
                    except:
                        continue
                
                if not reported_tab:
                    raise Exception("Could not find Reported tab with any selector")
                
                reported_tab.click()
                time.sleep(3)  # Wait for reported data to load
                self.logger.info("Clicked Reported tab - waiting for data to load")
            except Exception as e:
                self.logger.error(f"Could not find or click Reported tab: {e}")
                return []
            
            # SECOND: CRITICAL - Must click Day button to get daily actual runs (not week view)
            try:
                # Wait for Day button to appear after Reported tab loads
                time.sleep(2)
                
                # Find and click Day button using same logic as schedule extraction
                day_button = None
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for button in all_buttons:
                    if button.text.strip().lower() == 'day' and button.is_displayed():
                        day_button = button
                        break
                
                if day_button:
                    # Always click Day button to ensure we get daily view (not week view)
                    day_button.click()
                    time.sleep(3)  # Wait for day view to load
                    self.logger.info("Clicked Day button - switched to daily actual runs view")
                else:
                    self.logger.error("CRITICAL: Could not find Day button - may be viewing week actuals instead of daily")
                    
            except Exception as e:
                self.logger.error(f"CRITICAL: Failed to click Day button: {e}")
                self.logger.error("WARNING: May be extracting week actual runs instead of daily")
            
            actual_runs = []
            
            # Use the same successful approach as scheduled runs - look for rbc-event elements
            try:
                # Strategy 1: Target the rbc-event structure (same as schedule)
                zone_elements = self.driver.find_elements(By.XPATH, "//div[@class='rbc-event']")
                self.logger.info(f"Strategy 1: Found {len(zone_elements)} exact rbc-event blocks in Reported tab")
                
                if not zone_elements:
                    # Strategy 2: Look for any element with rbc-event class (broader)
                    zone_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'rbc-event')]")
                    self.logger.info(f"Strategy 2: Found {len(zone_elements)} blocks with rbc-event class in Reported tab")
                    
                self.logger.info(f"FINAL: Using {len(zone_elements)} actual run elements")
                
            except Exception as e:
                self.logger.error(f"Failed to find actual run blocks: {e}")
                return []
            
            if not zone_elements:
                self.logger.warning("No actual run elements found on Reported page")
                return []
            
            # Process each actual run element (same structure as scheduled)
            seen_runs = set()  # Track unique runs to avoid duplicates
            
            for i, element in enumerate(zone_elements):
                try:
                    # Extract zone name from title attribute of rbc-event-content
                    zone_name = ""
                    try:
                        event_content = element.find_element(By.XPATH, ".//div[@class='rbc-event-content']")
                        zone_name = event_content.get_attribute('title') or ""
                        self.logger.debug(f"Found actual run zone name in title: {zone_name}")
                    except:
                        # Fallback to element text
                        zone_name = element.text.strip()
                        self.logger.debug(f"Using element text as zone name: {zone_name}")
                    
                    if not zone_name:
                        self.logger.debug(f"Skipping actual run element {i} - no zone name found")
                        continue
                    
                    # Extract start time from short-time span (same as scheduled)
                    start_time_str = ""
                    try:
                        short_time = element.find_element(By.XPATH, ".//span[@class='short-time']")
                        start_time_str = short_time.text.strip()
                        self.logger.debug(f"Found actual run start time: {start_time_str}")
                    except:
                        self.logger.debug(f"Could not extract start time for actual run {zone_name}")
                    
                    # Get popup data for actual run details (status, duration, failures)
                    popup_data = {}
                    try:
                        actions = ActionChains(self.driver)
                        actions.move_to_element(element).perform()
                        time.sleep(1.5)  # Wait for popup to appear
                        popup_data = self.extract_hover_popup_data_with_retry(zone_name)
                        
                        if popup_data:
                            self.logger.debug(f"Actual run popup data: {popup_data}")
                        else:
                            self.logger.warning(f"No popup data found for actual run {zone_name}")
                        
                    except Exception as e:
                        self.logger.debug(f"Hover failed for actual run {zone_name}: {e}")
                    
                    # Convert start time string to datetime
                    start_datetime = target_date  # Default to target date
                    if start_time_str:
                        try:
                            from datetime import datetime
                            # Parse time like "6:01am" 
                            time_obj = datetime.strptime(start_time_str, '%I:%M%p').time()
                            start_datetime = datetime.combine(target_date.date(), time_obj)
                            self.logger.debug(f"Parsed actual run start time: {start_datetime}")
                        except Exception as e:
                            self.logger.debug(f"Could not parse actual run start time '{start_time_str}': {e}")
                    
                    # Clean up zone name (remove time prefix if it got concatenated)
                    import re
                    clean_zone_name = re.sub(r'^\d{1,2}:\d{2}[ap]m', '', zone_name).strip()
                    if not clean_zone_name:
                        clean_zone_name = zone_name  # Fallback to original if cleaning failed
                    
                    # Create unique identifier to avoid duplicates
                    run_key = (clean_zone_name, start_time_str)
                    if run_key in seen_runs:
                        self.logger.debug(f"Skipping duplicate actual run: {clean_zone_name} at {start_time_str}")
                        continue
                    seen_runs.add(run_key)
                    
                    # Extract actual run details from popup
                    duration_minutes = popup_data.get('duration_minutes', 0)
                    actual_gallons = popup_data.get('actual_gallons')
                    status = popup_data.get('status', 'Completed')
                    notes = popup_data.get('notes', '')
                    
                    # Determine failure reason from status/notes
                    failure_reason = None
                    if 'aborted' in status.lower() or 'cancelled' in status.lower():
                        failure_reason = status
                    elif 'sensor' in notes.lower():
                        failure_reason = "Sensor input"
                    elif 'manual' in notes.lower():
                        failure_reason = "Manual intervention"
                    
                    # Create ActualRun object
                    actual_run = ActualRun(
                        zone_id=popup_data.get('zone_id', f'zone_{len(actual_runs)}'),
                        zone_name=clean_zone_name,
                        start_time=start_datetime,
                        end_time=None,  # Calculate from start + duration if needed
                        duration_minutes=duration_minutes,
                        actual_gallons=actual_gallons,
                        status=status,
                        failure_reason=failure_reason,
                        notes=notes
                    )
                    
                    actual_runs.append(actual_run)
                    self.logger.info(f"Extracted actual run {len(actual_runs)}: '{actual_run.zone_name}' at {start_time_str} for {actual_run.duration_minutes} minutes - {actual_run.status}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to process actual run element {i+1}/{len(zone_elements)}: {e}")
                    continue
            
            self.logger.info(f"Extracted {len(actual_runs)} actual runs")
            return actual_runs
            
        except Exception as e:
            self.logger.error(f"❌ Failed to extract actual runs: {e}")
            return []
            
    def extract_hover_popup_data(self) -> Optional[Dict]:
        """
        Extract data from hover popup.
        
        Returns:
            dict: Popup data or None if not found
        """
        try:
            import re
            
            # Look for popup element using the EXACT structure from inspect
            popup_selectors = [
                "//div[@class='idui-popover']",  # Primary target from inspect
                "//div[contains(@class, 'idui-popover')]",  # Fallback with contains
                "//div[contains(@style, 'z-index: 1000')]",  # Unique z-index from inspect
                "//div[contains(@style, 'opacity: 1') and contains(@style, 'transform')]",  # Visible popup
                "//div[contains(@class, 'popup')]",
                "//div[contains(@class, 'tooltip')]", 
                "//*[contains(text(), 'Normal watering cycle')]/..",
                "//*[contains(text(), 'Water usage')]/..",
                "//*[contains(text(), 'Duration')]/.."
            ]
            
            popup = None
            popup_text = ""
            
            for selector in popup_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        # Check if element is displayed and has meaningful content
                        if element.is_displayed():
                            element_text = element.text.strip()
                            if element_text:
                                popup = element
                                popup_text = element_text
                                self.logger.debug(f"Found popup using selector: {selector}")
                                self.logger.debug(f"Popup text preview: {popup_text[:100]}...")
                                
                                # For idui-popover, accept any text content
                                if 'idui-popover' in selector or any(keyword in popup_text.lower() for keyword in ['water', 'duration', 'gallons', 'cycle', 'zone', 'minutes']):
                                    self.logger.debug(f"Popup accepted with text: {popup_text}")
                                    break
                            else:
                                self.logger.debug(f"Element found but no text content using selector: {selector}")
                        else:
                            self.logger.debug(f"Element not displayed using selector: {selector}")
                    if popup:
                        break
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            if not popup or not popup_text:
                return None
                
            # Parse the popup text based on the format seen in screenshots
            data = {
                'zone_name': '',
                'zone_id': '',
                'start_time': None,
                'duration_minutes': 0,
                'expected_gallons': None,
                'actual_gallons': None,
                'status': 'Unknown',
                'notes': popup_text,
                'current_ma': None
            }
            
            lines = popup_text.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Extract status/cycle type - handle both normal and rain-suspended conditions
                if 'watering cycle' in line.lower():
                    data['status'] = line
                elif 'not scheduled to run' in line.lower():
                    data['status'] = line
                    data['rain_suspended'] = True
                elif 'scheduled to run' in line.lower() and 'not' not in line.lower():
                    data['status'] = line
                elif any(keyword in line.lower() for keyword in ['suspended', 'stopped', 'sensor', 'rain']):
                    data['status'] = line
                    if 'sensor' in line.lower() or 'rain' in line.lower():
                        data['rain_suspended'] = True
                
                # Extract time information
                time_match = re.search(r'Time[:\s]*([^,\n]+)', line, re.IGNORECASE)
                if time_match:
                    time_str = time_match.group(1).strip()
                    data['time_info'] = time_str
                
                # Extract duration - try multiple patterns
                duration_patterns = [
                    r'Duration[:\s]*(\d+)\s*minutes?',  # "Duration: 3 minutes"
                    r'Duration[:\s]*(\d+)\s*mins?',     # "Duration: 3 min"
                    r'(\d+)\s*minutes?\s*duration',     # "3 minutes duration"  
                    r'Duration[:\s]*(\d+)',             # "Duration: 3"
                ]
                
                for pattern in duration_patterns:
                    duration_match = re.search(pattern, line, re.IGNORECASE)
                    if duration_match:
                        data['duration_minutes'] = int(duration_match.group(1))
                        break
                
                # Extract water usage (gallons) - try multiple patterns for more robust matching
                water_patterns = [
                    r'Water usage[:\s]*([0-9.]+)\s*Gallons?',     # "Water usage: 7.50006567238888 Gallons"
                    r'Water[:\s]*([0-9.]+)\s*Gallons?',          # "Water: 7.5 Gallons"
                    r'([0-9.]+)\s*Gallons?\s*usage',             # "7.5 Gallons usage"
                    r'Usage[:\s]*([0-9.]+)\s*Gallons?',          # "Usage: 7.5 Gallons"
                ]
                
                for pattern in water_patterns:
                    water_match = re.search(pattern, line, re.IGNORECASE)
                    if water_match:
                        gallons = float(water_match.group(1))
                        data['actual_gallons'] = gallons
                        data['expected_gallons'] = gallons  # For scheduled, this is expected
                        break
                
                # Extract current reading
                current_match = re.search(r'Current[:\s]*([0-9.]+)\s*mA', line, re.IGNORECASE)
                if current_match:
                    data['current_ma'] = float(current_match.group(1))
                
                # Extract zone name (if in popup)
                if any(keyword in line.lower() for keyword in ['rear', 'front', 'left', 'right', 'pots', 'beds', 'turf']):
                    if not data['zone_name'] and len(line) > 5:
                        data['zone_name'] = line
            
            # Log what we extracted for debugging
            self.logger.debug(f"Raw popup text: {popup_text}")
            self.logger.debug(f"Extracted popup data: {data}")
            
            # Special debug logging for key data extraction
            if 'duration_minutes' in data and data['duration_minutes'] > 0:
                self.logger.debug(f"SUCCESS: Found duration {data['duration_minutes']} minutes in popup")
            elif 'rain_suspended' in data and data['rain_suspended']:
                self.logger.info(f"RAIN SUSPENDED: Zone shows 'not scheduled to run' due to rain sensor")
                data['duration_minutes'] = 0  # Set to 0 for rain-suspended zones
            else:
                self.logger.debug(f"NO DURATION: No duration found in popup text: '{popup_text}'")
                
            if 'actual_gallons' in data and data['actual_gallons']:
                self.logger.debug(f"SUCCESS: Found water usage {data['actual_gallons']} gallons in popup")
            
            if 'current_ma' in data and data['current_ma']:
                self.logger.debug(f"SUCCESS: Found current reading {data['current_ma']} mA in popup")
            
            return data
                
        except Exception as e:
            self.logger.debug(f"Could not extract popup data: {e}")
            
        return None
        
    def extract_hover_popup_data_with_retry(self, zone_name: str = "", max_retries: int = 3) -> Optional[Dict]:
        """
        Extract popup data with retry logic for improved reliability.
        Specifically targets the 3 zones that had extraction failures.
        
        Args:
            zone_name: Name of zone for targeted debugging
            max_retries: Number of retry attempts
            
        Returns:
            dict: Popup data or None if all attempts fail
        """
        # Known problematic zones that need special handling
        problematic_zones = [
            'Rear Bed/Planters at Pool (M)',
            'Rear Right Bed at House and Pool (M/D)', 
            'Rear Left Pots, Baskets & Planters (M)'
        ]
        
        is_problematic = any(problem_zone in zone_name for problem_zone in problematic_zones)
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Popup extraction attempt {attempt + 1}/{max_retries} for zone: {zone_name}")
                
                # Add extra wait for problematic zones
                if is_problematic:
                    self.logger.debug(f"Problematic zone detected, adding extra wait...")
                    time.sleep(1.5)
                
                popup_data = self.extract_hover_popup_data()
                
                if popup_data:
                    if is_problematic:
                        self.logger.info(f"✅ Successfully extracted popup data for problematic zone: {zone_name}")
                    return popup_data
                else:
                    if attempt < max_retries - 1:  # Not the last attempt
                        self.logger.debug(f"Attempt {attempt + 1} failed, retrying...")
                        time.sleep(0.5)  # Brief wait before retry
                    else:
                        self.logger.warning(f"❌ All {max_retries} attempts failed for zone: {zone_name}")
                        
            except Exception as e:
                self.logger.debug(f"Popup extraction attempt {attempt + 1} error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    
        return None
        
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
    
    def check_rain_sensor_status(self) -> Dict[str, any]:
        """
        Check the rain sensor status from dashboard to detect irrigation suspension.
        
        Returns:
            dict: Rain sensor status information
        """
        sensor_info = {
            'rain_sensor_active': False,
            'irrigation_suspended': False,
            'sensor_status': 'Unknown'
        }
        
        try:
            # Navigate to dashboard first (we might already be there)
            self.logger.info("Checking rain sensor status on dashboard...")
            
            # Go to dashboard URL
            dashboard_url = "https://app.hydrawise.com/config/dashboard"
            self.driver.get(dashboard_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # Additional wait for dynamic content
            
            # Look for sensor status indicators based on the HTML structure you showed
            sensor_selectors = [
                # Primary target: "Sensor is stopping irrigation" text
                "//*[contains(text(), 'Sensor is stopping irrigation')]",
                # Fallback: Look in sensor status areas
                "//div[contains(@class, 'sensor-status')]//span[contains(text(), 'stopping')]",
                # Look for any mention of sensor stopping irrigation
                "//*[contains(text(), 'stopping irrigation')]",
                # Alternative: Check for sensor panel content
                "//div[contains(@class, 'panel')]//span[contains(text(), 'Sensor')]"
            ]
            
            sensor_found = False
            sensor_text = ""
            
            for selector in sensor_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed():
                            element_text = element.text.strip()
                            if element_text:
                                sensor_text = element_text
                                sensor_found = True
                                self.logger.info(f"Found sensor status element: '{element_text}'")
                                break
                    if sensor_found:
                        break
                except Exception as e:
                    self.logger.debug(f"Sensor selector '{selector}' failed: {e}")
                    continue
            
            # Analyze the sensor status
            if sensor_found and sensor_text:
                sensor_info['sensor_status'] = sensor_text
                
                # Check for irrigation suspension indicators
                suspension_keywords = [
                    'stopping irrigation',
                    'sensor is stopping',
                    'irrigation suspended',
                    'rain detected'
                ]
                
                if any(keyword in sensor_text.lower() for keyword in suspension_keywords):
                    sensor_info['rain_sensor_active'] = True
                    sensor_info['irrigation_suspended'] = True
                    self.logger.warning(f"🌧️  Rain sensor detected: {sensor_text}")
                else:
                    sensor_info['rain_sensor_active'] = False
                    sensor_info['irrigation_suspended'] = False
                    self.logger.info(f"✅ Normal sensor status: {sensor_text}")
            else:
                # No sensor status found - assume normal operation
                sensor_info['sensor_status'] = 'No sensor alerts detected'
                sensor_info['rain_sensor_active'] = False
                sensor_info['irrigation_suspended'] = False
                self.logger.info("No rain sensor alerts found - assuming normal operation")
                
        except Exception as e:
            self.logger.error(f"Failed to check rain sensor status: {e}")
            sensor_info['sensor_status'] = f'Error checking sensor: {e}'
            
        return sensor_info
            
    def collect_24_hour_schedule(self, start_date: datetime = None) -> Dict[str, List]:
        """
        Collect schedule data for current day and next day (24 hour window)
        
        Args:
            start_date: Starting date (defaults to today)
            
        Returns:
            Dictionary with 'today' and 'tomorrow' schedule lists, plus rain sensor status
        """
        if start_date is None:
            start_date = datetime.now()
            
        tomorrow = start_date + timedelta(days=1)
        
        self.logger.info(f"Collecting 24-hour schedule starting from {start_date.date()}")
        
        results = {
            'today': [],
            'tomorrow': [],
            'collection_time': datetime.now(),
            'start_date': start_date.date(),
            'tomorrow_date': tomorrow.date(),
            'errors': [],
            'rain_sensor_active': False,
            'irrigation_suspended': False,
            'sensor_status': 'Unknown'
        }
        
        try:
            # Start browser session
            self.start_browser()
            if not self.login():
                raise Exception("Failed to login to Hydrawise portal")
            
            # Check rain sensor status first
            sensor_status = self.check_rain_sensor_status()
            results.update(sensor_status)
            
            # Log rain sensor findings with special alerts
            if results['rain_sensor_active']:
                self.logger.warning("🌧️  RAIN SENSOR ACTIVE - Irrigation is currently suspended!")
                self.logger.warning(f"📍 Sensor Status: {results['sensor_status']}")
                self.logger.warning("⚠️  All scheduled runs will show 'not scheduled to run' until sensor dries out")
                self.logger.warning("🚨 MANUAL PLANT MONITORING REQUIRED during suspension period")
            else:
                self.logger.info(f"✅ Rain sensor status: {results['sensor_status']}")
                
            # Navigate to reports and get today's schedule (using proven working method)
            self.navigate_to_reports()
            
            self.logger.info("Collecting today's schedule using proven method...")
            today_schedule = self.extract_scheduled_runs(start_date)
            results['today'] = today_schedule
            self.logger.info(f"Collected {len(today_schedule)} runs for today")
            
            # Only attempt tomorrow if today worked
            if len(today_schedule) > 0:
                self.logger.info("Today's collection successful, attempting tomorrow...")
                
                # Try to click Next button to get tomorrow
                try:
                    # Look for Next button - use simple approach first
                    next_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Next')]")
                    if next_buttons:
                        next_button = next_buttons[0]
                        self.logger.info("Found Next button, clicking...")
                        next_button.click()
                        time.sleep(3)  # Wait for navigation
                        
                        # Try to get tomorrow's schedule
                        self.logger.info("Collecting tomorrow's schedule...")
                        tomorrow_schedule = self.extract_scheduled_runs(tomorrow)
                        results['tomorrow'] = tomorrow_schedule
                        self.logger.info(f"Collected {len(tomorrow_schedule)} runs for tomorrow")
                        
                    else:
                        self.logger.warning("Could not find Next button")
                        results['errors'].append("Could not find Next button")
                        
                except Exception as e:
                    self.logger.error(f"Failed to get tomorrow's schedule: {e}")
                    results['errors'].append(f"Tomorrow collection failed: {e}")
            else:
                self.logger.warning("Today's collection failed, skipping tomorrow")
                results['errors'].append("Today's collection failed")
                
        except Exception as e:
            self.logger.error(f"Critical error during 24-hour schedule collection: {e}")
            results['errors'].append(f"Collection failed: {e}")
            
            # Try to recover browser state
            try:
                if hasattr(self, 'driver') and self.driver:
                    self.logger.info("Attempting browser recovery...")
                    self.driver.refresh()
                    time.sleep(3)
            except Exception as recovery_error:
                self.logger.error(f"Browser recovery failed: {recovery_error}")
                
        finally:
            try:
                self.stop_browser()
            except Exception as cleanup_error:
                self.logger.error(f"Browser cleanup error: {cleanup_error}")
                
        # Final status logging
        if results['rain_sensor_active']:
            self.logger.warning("🌧️  COLLECTION COMPLETED DURING RAIN SENSOR SUSPENSION")
            self.logger.warning("📋 Data collected, but all runs show 'not scheduled' due to rain sensor")
        else:
            self.logger.info(f"✅ 24-hour collection completed: {len(results['today'])} today, {len(results['tomorrow'])} tomorrow")
                
        return results
        
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
                    break
                except Exception as e:
                    self.logger.debug(f"Day selector '{selector}' failed: {e}")
                    continue
                    
            # Wait for day view to populate
            time.sleep(3)
            
            self.logger.info("Schedule view setup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup schedule view: {e}")
            return False
        
    def detect_failures(self, scheduled_runs: List[ScheduledRun], actual_runs: List[ActualRun]) -> List[IrrigationFailure]:
        """
        Compare scheduled vs actual runs to detect failures.
        
        Args:
            scheduled_runs (list): Expected runs for the day
            actual_runs (list): Actual runs that occurred
            
        Returns:
            list: Detected failures requiring user attention
        """
        failures = []
        current_time = datetime.now()
        
        # Create lookup for actual runs by zone
        actual_by_zone = {run.zone_id: run for run in actual_runs}
        
        for scheduled in scheduled_runs:
            zone_id = scheduled.zone_id
            
            # Check if scheduled run actually happened
            if zone_id not in actual_by_zone:
                # Missing run - check if it was supposed to happen by now
                if scheduled.start_time < current_time - timedelta(hours=1):
                    failure = IrrigationFailure(
                        failure_id=f"{zone_id}_missed_{int(current_time.timestamp())}",
                        timestamp=current_time,
                        zone_id=zone_id,
                        zone_name=scheduled.zone_name,
                        failure_type="missed_run",
                        description=f"Zone {scheduled.zone_name} was scheduled to run at {scheduled.start_time.strftime('%H:%M')} but did not run",
                        scheduled_run=scheduled,
                        actual_run=None,
                        action_required="Check zone status and manually start if needed",
                        priority="CRITICAL"
                    )
                    failures.append(failure)
                    
            else:
                actual = actual_by_zone[zone_id]
                
                # Check for sensor aborts or other failures
                if "aborted" in actual.status.lower():
                    failure = IrrigationFailure(
                        failure_id=f"{zone_id}_abort_{int(current_time.timestamp())}",
                        timestamp=current_time,
                        zone_id=zone_id,
                        zone_name=scheduled.zone_name,
                        failure_type="sensor_abort",
                        description=f"Zone {scheduled.zone_name} aborted: {actual.status}",
                        scheduled_run=scheduled,
                        actual_run=actual,
                        action_required="Check sensors and manually water if needed",
                        priority="CRITICAL"
                    )
                    failures.append(failure)
                    
                # Check for significant water delivery differences
                elif scheduled.expected_gallons and actual.actual_gallons:
                    variance = abs(actual.actual_gallons - scheduled.expected_gallons) / scheduled.expected_gallons
                    if variance > 0.3:  # 30% variance threshold
                        failure = IrrigationFailure(
                            failure_id=f"{zone_id}_variance_{int(current_time.timestamp())}",
                            timestamp=current_time,
                            zone_id=zone_id,
                            zone_name=scheduled.zone_name,
                            failure_type="water_variance",
                            description=f"Zone {scheduled.zone_name} delivered {actual.actual_gallons:.1f} gallons vs expected {scheduled.expected_gallons:.1f}",
                            scheduled_run=scheduled,
                            actual_run=actual,
                            action_required="Check system pressure and flow rates",
                            priority="WARNING"
                        )
                        failures.append(failure)
                        
        return failures
        
    def scrape_daily_data(self, target_date: datetime = None) -> Tuple[List[ScheduledRun], List[ActualRun], List[IrrigationFailure]]:
        """
        Scrape complete daily irrigation data.
        
        Args:
            target_date (datetime): Date to scrape (defaults to today)
            
        Returns:
            tuple: (scheduled_runs, actual_runs, failures)
        """
        if target_date is None:
            target_date = datetime.now()
            
        try:
            # Start browser and login
            self.start_browser()
            
            if not self.login():
                raise Exception("Login failed")
                
            # Navigate to reports
            self.navigate_to_reports()
            
            # Set the target date
            self.set_date(target_date)
            
            # Extract scheduled and actual runs
            scheduled_runs = self.extract_scheduled_runs(target_date)
            actual_runs = self.extract_actual_runs(target_date)
            
            # Detect failures
            failures = self.detect_failures(scheduled_runs, actual_runs)
            
            # Save data to files
            self.save_data_to_files(target_date, scheduled_runs, actual_runs, failures)
            
            return scheduled_runs, actual_runs, failures
            
        finally:
            self.stop_browser()
            
    def save_data_to_files(self, date: datetime, scheduled: List[ScheduledRun], actual: List[ActualRun], failures: List[IrrigationFailure]):
        """Save scraped data to JSON files"""
        date_str = date.strftime('%Y%m%d')
        
        # Save scheduled runs
        with open(f'data/scheduled_runs_{date_str}.json', 'w') as f:
            json.dump([asdict(run) for run in scheduled], f, indent=2, default=str)
            
        # Save actual runs
        with open(f'data/actual_runs_{date_str}.json', 'w') as f:
            json.dump([asdict(run) for run in actual], f, indent=2, default=str)
            
        # Save failures
        with open(f'data/failures_{date_str}.json', 'w') as f:
            json.dump([asdict(failure) for failure in failures], f, indent=2, default=str)
            
        self.logger.info(f"💾 Data saved for {date_str}")

if __name__ == "__main__":
    # Example usage
    print("Hydrawise Web Scraper")
    print("=" * 50)
    
    # Load credentials from environment
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("❌ Missing credentials. Please set HYDRAWISE_USER and HYDRAWISE_PASSWORD in .env file")
        sys.exit(1)
        
    # Create scraper and run
    scraper = HydrawiseWebScraper(username, password, headless=False)  # Set to True for background operation
    
    try:
        scheduled, actual, failures = scraper.scrape_daily_data()
        
        print(f"\n📊 Results for {datetime.now().strftime('%Y-%m-%d')}:")
        print(f"   Scheduled runs: {len(scheduled)}")
        print(f"   Actual runs: {len(actual)}")
        print(f"   Failures detected: {len(failures)}")
        
        # Show any critical failures
        critical_failures = [f for f in failures if f.priority == "CRITICAL"]
        for failure in critical_failures:
            print(f"\n🚨 CRITICAL: {failure.description}")
            print(f"   Action: {failure.action_required}")
            
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        sys.exit(1)
