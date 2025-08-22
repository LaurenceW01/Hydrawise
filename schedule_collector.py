#!/usr/bin/env python3
"""
Schedule Data Collection Module for Hydrawise Web Scraper

Handles extraction of scheduled irrigation runs from the Schedule tab.
Cut and pasted from HydrawiseWebScraper class without modifications.

Author: AI Assistant  
Date: 2025
"""

import time
import re
from datetime import datetime, timedelta
from typing import List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

def extract_scheduled_runs(self, target_date: datetime, limit_zones: int = None) -> List:
    """
    Extract scheduled runs from the Schedule tab
    
    Args:
        target_date (datetime): Date to extract schedule for
        limit_zones (int, optional): Limit to first N zones for testing speed
        
    Returns:
        List[ScheduledRun]: List of scheduled irrigation runs
    """
    scheduled_runs = []
    
    try:
        self.logger.info("Extracting scheduled runs...")
        
        # Navigate to the Schedule tab first
        # Look for the Schedule tab element using multiple strategies
        schedule_selectors = [
            "//div[@data-testid='sub-tab-reports.name.watering-schedule']",
            "//div[contains(@class, 'reports-page__subtabs__tab') and contains(text(), 'Schedule')]",
            "//button[contains(text(), 'Schedule')]",
            "//*[contains(text(), 'Schedule')]"
        ]
        
        schedule_clicked = False
        for selector in schedule_selectors:
            try:
                schedule_element = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                schedule_element.click()
                self.logger.info("Clicked Schedule tab - waiting for data to load")
                time.sleep(5)  # Wait for schedule data to load
                schedule_clicked = True
                break
            except Exception as e:
                self.logger.debug(f"Schedule selector '{selector}' failed: {e}")
                continue
        
        if not schedule_clicked:
            self.logger.error("❌ Could not find or click Schedule tab")
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
        
        # Strategy 1: Look for individual zone elements (rbc-event-content)
        self.logger.info("Strategy 1: Looking for individual rbc-event-content elements...")
        
        content_events = self.driver.find_elements(By.XPATH, "//div[@class='rbc-event-content']")
        self.logger.info(f"Strategy 1: Found {len(content_events)} rbc-event-content blocks")
        
        # Strategy 2: Fallback to broader rbc-event elements if content elements not found
        broader_events = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'rbc-event')]")
        self.logger.info(f"Strategy 2: Found {len(broader_events)} broader rbc-event blocks")
        
        # Use content elements if found, otherwise use broader elements
        timeline_elements = content_events if len(content_events) > 0 else broader_events
        self.logger.info(f"FINAL: Using {len(timeline_elements)} schedule elements (target: 24)")
        
        if not timeline_elements:
            self.logger.warning("❌ No schedule elements found")
            return []
        
        # Use a set to track zone+time combinations to avoid duplicates
        seen_runs = set()
        
        # Limit zones for testing if specified
        zones_to_process = timeline_elements
        if limit_zones:
            zones_to_process = timeline_elements[:limit_zones]
            self.logger.info(f"🚀 TESTING MODE: Processing only first {limit_zones} zones out of {len(timeline_elements)}")
            
        # Debug: Show what elements we're about to process
        self.logger.info(f"📋 About to process {len(zones_to_process)} elements:")
        
        for i, element in enumerate(zones_to_process):
            try:
                # Small delay to ensure DOM element is fully rendered
                time.sleep(0.1)
                
                # Extract zone name from text content (more accurate than title)
                zone_name = ""
                
                # Method 1: Try text content first (more accurate for zone names)
                element_text = element.text.strip()
                self.logger.info(f"🔍 Element {i+1} text content: '{element_text[:100]}...'")
                if element_text:
                    # Take only the first line to avoid getting all zone names concatenated
                    first_line = element_text.split('\n')[0].strip()
                    self.logger.info(f"🔍 Element {i+1} first line: '{first_line}'")
                    if first_line and len(first_line) > 3:
                        zone_name = first_line
                
                # Method 2: Fallback to title attribute if no text content
                if not zone_name:
                    title_attr = element.get_attribute('title')
                    if title_attr:
                        zone_name = title_attr.strip()
                
                # Method 3: Try looking for nested elements with zone names
                if not zone_name:
                    nested_elements = element.find_elements(By.XPATH, ".//*")
                    for nested in nested_elements:
                        nested_text = nested.text.strip()
                        if nested_text and len(nested_text) > 3:
                            # Also take only first line for nested elements
                            first_line = nested_text.split('\n')[0].strip()
                            if first_line:
                                zone_name = first_line
                                break
                
                if not zone_name:
                    self.logger.debug(f"Skipping element {i+1} - no zone name found")
                    continue
                
                # Parse time from zone name if it's concatenated (like "3:30amFront Right Turf")
                original_zone_name = zone_name
                parsed_start_time = None
                
                # Check if zone name starts with time pattern
                time_pattern = r'^(\d{1,2}:\d{2}[ap]m)(.*)$'
                time_match = re.match(time_pattern, zone_name, re.IGNORECASE)
                if time_match:
                    time_str = time_match.group(1).lower()
                    zone_name = time_match.group(2).strip()
                    
                    # Parse the time string to get actual start time
                    try:
                        from datetime import datetime
                        temp_time = datetime.strptime(time_str, '%I:%M%p')
                        parsed_start_time = (temp_time.hour, temp_time.minute)
                        self.logger.debug(f"Parsed time {time_str} -> {parsed_start_time} for zone: {zone_name}")
                    except Exception as e:
                        self.logger.debug(f"Failed to parse time {time_str}: {e}")
                
                # Extract start time from position or style attributes
                start_time_minutes = 0
                duration_minutes = 0
                
                # Try to get time from CSS position or data attributes
                try:
                    style = element.get_attribute('style') or ''
                    
                    # Look for top position which indicates time of day
                    top_match = re.search(r'top:\s*([0-9.]+)px', style)
                    if top_match:
                        top_pixels = float(top_match.group(1))
                        # Convert pixels to time (this is an approximation)
                        # Based on observation, early morning starts around 120px
                        start_time_minutes = max(0, (top_pixels - 120) * 0.5)  # Rough conversion
                    
                    # Look for height which indicates duration
                    height_match = re.search(r'height:\s*([0-9.]+)px', style)
                    if height_match:
                        height_pixels = float(height_match.group(1))
                        duration_minutes = max(1, height_pixels * 0.5)  # Rough conversion
                        
                except Exception as e:
                    self.logger.debug(f"Could not extract timing from style for {zone_name}: {e}")
                
                # Try to extract more precise timing from visual content
                if duration_minutes == 0:
                    # Look for any numeric content that might be duration
                    zone_text = zone_name.lower()
                    duration_numbers = re.findall(r'\d+', zone_text)
                    if duration_numbers:
                        # Take the last number found as potential duration
                        duration_minutes = int(duration_numbers[-1])
                        self.logger.debug(f"Found potential duration {duration_minutes} in zone text")
                    else:
                        duration_minutes = 1  # Default minimum duration
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
                        is_rain_suspended = popup_data.get('rain_suspended', False)
                        popup_status = popup_data.get('status', 'Unknown')
                        
                        self.logger.info(f"Zone {zone_name}: Visual duration={duration_minutes}, Popup duration={popup_duration}, Rain suspended={is_rain_suspended}")
                        
                        # Check for rain suspension first - this overrides everything
                        if is_rain_suspended or 'not scheduled to run' in popup_status.lower():
                            duration_minutes = 0  # Override to 0 for rain-suspended zones
                            self.logger.info(f"🌧️ RAIN SUSPENDED: Zone duration set to 0 min due to: {popup_status}")
                        elif popup_duration > 0:
                            # Use popup duration if available and not rain-suspended
                            self.logger.info(f"Using popup duration: {popup_duration} min (overriding visual: {duration_minutes})")
                            duration_minutes = popup_duration
                        else:
                            self.logger.warning(f"Popup found but no duration - using visual: {duration_minutes} min")
                    else:
                        self.logger.warning(f"No popup data found for {zone_name}")
                        
                except Exception as e:
                    self.logger.debug(f"Failed to get popup data for {zone_name}: {e}")
                
                # Calculate actual start time - use parsed time if available
                if parsed_start_time:
                    start_hour, start_minute = parsed_start_time
                    self.logger.debug(f"Using parsed time: {start_hour}:{start_minute:02d}")
                else:
                    start_hour = int(start_time_minutes // 60)
                    start_minute = int(start_time_minutes % 60)
                    self.logger.debug(f"Using calculated time: {start_hour}:{start_minute:02d}")
                
                # Create datetime for the scheduled run
                start_datetime = target_date.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
                
                # Create unique identifier to avoid duplicates - use clean zone name
                clean_zone_id = zone_name.strip().lower().replace(' ', '_')
                run_id = f"{clean_zone_id}_{start_datetime.strftime('%H:%M')}"
                
                if run_id in seen_runs:
                    self.logger.info(f"🔄 SKIPPING DUPLICATE: {run_id} (original zone: {original_zone_name})")
                    continue
                
                seen_runs.add(run_id)
                self.logger.info(f"✅ PROCESSING ZONE {len(scheduled_runs)+1}: {zone_name} at {start_datetime.strftime('%I:%M %p')}")
                
                # Create ScheduledRun object
                from hydrawise_web_scraper import ScheduledRun  # Import here to avoid circular imports
                scheduled_run = ScheduledRun(
                    zone_id=f"zone_{i+1}",  # Generate ID since not available
                    zone_name=zone_name,
                    start_time=start_datetime,
                    duration_minutes=duration_minutes,
                    expected_gallons=popup_data.get('expected_gallons'),
                    notes=popup_data.get('status', 'Scheduled run')
                )
                
                scheduled_runs.append(scheduled_run)
                self.logger.info(f"Extracted {len(scheduled_runs)}: '{zone_name}' at {start_datetime.strftime('%I:%M%p').lower()} for {duration_minutes} minutes")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to process schedule element {i+1}: {e}")
                continue
        
        self.logger.info(f"✅ Successfully extracted {len(scheduled_runs)} scheduled runs for {target_date.date()}")
        return scheduled_runs
        
    except Exception as e:
        self.logger.error(f"❌ Failed to extract scheduled runs: {e}")
        return []

def collect_24_hour_schedule(self, start_date: datetime = None, limit_zones: int = None) -> Dict[str, List]:
    """
    Collect schedule data for current day and next day (24 hour window)
    
    Args:
        start_date: Starting date (defaults to today)
        limit_zones: Limit to first N zones for testing speed
        
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
        today_schedule = self.extract_scheduled_runs(start_date, limit_zones)
        results['today'] = today_schedule
        self.logger.info(f"Collected {len(today_schedule)} runs for today")
        
        # Only attempt tomorrow if today worked
        if len(today_schedule) > 0:
            self.logger.info("Today's collection successful, attempting tomorrow...")
            
            # Click Next button using the same approach that works
            try:
                self.logger.info("Looking for Next button in toolbar...")
                
                # Wait longer for page to be completely ready after schedule extraction
                self.logger.info("Waiting for page to fully load after schedule extraction...")
                time.sleep(5)
                
                # Wait for toolbar to be present and stable
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(@class, 'rbc-toolbar')]"))
                    )
                    self.logger.info("Toolbar found, waiting for it to be stable...")
                    time.sleep(2)
                except Exception as e:
                    self.logger.warning(f"Could not find toolbar: {e}")
                
                # Look for Next button in the same toolbar as Today/Previous
                next_button = None
                
                # Try different selectors for the Next button - simplified based on debug findings
                next_selectors = [
                    "//button[normalize-space(text())='Next']",  # Handle whitespace
                    "//button[contains(normalize-space(text()), 'Next')]",  # Handle whitespace + contains
                    "//button[text()='Next']",  # Exact match
                    "//button[contains(text(), 'Next')]"  # Contains match
                ]
                
                # First try XPath selectors
                for selector in next_selectors:
                    try:
                        # Use WebDriverWait for each selector to ensure element is ready
                        self.logger.info(f"Trying selector: {selector}")
                        buttons = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_all_elements_located((By.XPATH, selector))
                        )
                        if buttons:
                            # Check if button is actually visible and enabled
                            for button in buttons:
                                if button.is_displayed() and button.is_enabled():
                                    next_button = button
                                    self.logger.info(f"Found Next button using selector: {selector}")
                                    self.logger.info(f"Button visible: {button.is_displayed()}, enabled: {button.is_enabled()}")
                                    break
                            if next_button:
                                break
                    except Exception as e:
                        self.logger.debug(f"Selector {selector} failed: {e}")
                        continue
                
                # If XPath selectors failed, use the same approach as debug (find all buttons)
                if not next_button:
                    self.logger.info("XPath selectors failed, trying find all buttons approach...")
                    try:
                        all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                        self.logger.info(f"Found {len(all_buttons)} total buttons on page")
                        
                        for i, button in enumerate(all_buttons):
                            try:
                                button_text = button.text.strip()
                                if button_text.lower() == 'next':
                                    if button.is_displayed() and button.is_enabled():
                                        next_button = button
                                        self.logger.info(f"Found Next button using all-buttons search: Button {i+1} text='{button_text}'")
                                        break
                            except Exception as e:
                                continue
                                
                    except Exception as e:
                        self.logger.error(f"All-buttons search failed: {e}")
                
                if next_button:
                    self.logger.info("Clicking Next button to navigate to tomorrow...")
                    next_button.click()
                    time.sleep(4)  # Wait for navigation
                    
                    # Extract tomorrow's schedule using same proven method
                    self.logger.info("Extracting tomorrow's schedule using proven method...")
                    tomorrow_schedule = self.extract_scheduled_runs(tomorrow, limit_zones)
                    results['tomorrow'] = tomorrow_schedule
                    self.logger.info(f"Collected {len(tomorrow_schedule)} runs for tomorrow")
                else:
                    self.logger.error("Could not find Next button for tomorrow navigation")
                    results['errors'].append("Next button not found for tomorrow")
                    
            except Exception as e:
                self.logger.error(f"Failed to navigate to tomorrow: {e}")
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
