#!/usr/bin/env python3
"""
Reported Run Data Collection Module for Hydrawise Web Scraper

Handles extraction of actual/reported irrigation runs from the Reported tab.
Centralizes all reported data parsing logic for reuse across different collection methods.

Author: AI Assistant  
Date: 2025
"""

import time
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def navigate_to_reported_tab(self):
    """Navigate to the Reported tab and ensure Day view is selected"""
    try:
        self.logger.info("[SYMBOL] Navigating to Reported tab with Day view...")
        
        # Use shared navigation helper - same efficient approach as schedule collection
        from shared_navigation_helper import create_navigation_helper
        nav_helper = create_navigation_helper(self)
        
        # Navigate to Reported tab (includes built-in wait)
        if not nav_helper.navigate_to_reported_tab():
            self.logger.error("[ERROR] Failed to navigate to Reported tab")
            return False
        
        # Switch to Day view (includes built-in wait)
        if not nav_helper.switch_to_day_view():
            self.logger.warning("[WARNING] Failed to switch to Day view - may already be in daily view")
        
        self.logger.info("[OK] Ready for data extraction")
        return True
        
    except Exception as e:
        self.logger.error(f"[ERROR] Failed to navigate to Reported tab: {e}")
        return False


def _click_day_button_for_reported(self):
    """Click Day button specifically for reported view"""
    try:
        self.logger.info("Clicking Day button for reported view...")
        
        # Step 1: Quick check if Day button is immediately available
        quick_selectors = [
            '//button[text()="Day"]',  # Most direct match
            '//button[contains(text(), "Day")]'  # Simple contains match
        ]
        
        day_button = None
        successful_selector = None
        
        # Quick scan without waiting
        for selector in quick_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        day_button = element
                        successful_selector = f"{selector} (immediate)"
                        self.logger.info(f"[OK] Found Day button immediately: {successful_selector}")
                        break
                if day_button:
                    break
            except:
                continue
        
        # Step 2: If not found immediately, try waiting with comprehensive selectors
        if not day_button:
            self.logger.info("Day button not immediately available, trying with wait...")
            comprehensive_selectors = [
                '//button[normalize-space(text())="Day"]',
                '//button[contains(normalize-space(text()), "Day")]',
                '//button[text()="Day"]',
                '//button[contains(text(), "Day")]',
                '//*[@type="button" and contains(text(), "Day")]',
                '//span[contains(text(), "Day")]/parent::button',
                '//*[contains(@class, "button") and contains(text(), "Day")]'
            ]
            
            for selector in comprehensive_selectors:
                try:
                    day_button = WebDriverWait(self.driver, 2).until(  # Reduced from 5 to 2 seconds
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    successful_selector = selector
                    break
                except:
                    continue
        
        if not day_button:
            # Fallback: Search through all buttons
            self.logger.info("Direct selectors failed, searching all buttons...")
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            
            for button in buttons:
                try:
                    button_text = button.text.strip()
                    if button_text.lower() == "day":
                        if button.is_enabled() and button.is_displayed():
                            day_button = button
                            successful_selector = "General button search"
                            break
                except:
                    continue
        
        if day_button:
            day_button.click()
            time.sleep(2)
            self.logger.info(f"[OK] Clicked Day button using: {successful_selector}")
        else:
            self.logger.warning("[WARNING] Could not find Day button - may already be in daily view")
            
    except Exception as e:
        self.logger.warning(f"Day button click failed: {e}")


def get_current_date_label(self) -> Optional[str]:
    """Extract the current date label from the reported page"""
    try:
        # Look for date labels in the reported page
        date_selectors = [
            "//span[contains(@class, 'rbc-toolbar-label')]",  # React Big Calendar toolbar label
            "//*[contains(@class, 'toolbar') and contains(@class, 'label')]",
            "//*[contains(@class, 'date-label')]",
            "//*[contains(@class, 'current-date')]",
            "//h2[contains(text(), '202')]",  # Year-based search
            "//span[contains(text(), 'Aug') or contains(text(), 'Sep') or contains(text(), 'Oct')]"
        ]
        
        for selector in date_selectors:
            try:
                date_element = self.driver.find_element(By.XPATH, selector)
                date_text = date_element.text.strip()
                if date_text and len(date_text) > 5:  # Valid date text
                    self.logger.info(f"[DATE] Current date label: '{date_text}'")
                    return date_text
            except:
                continue
                
        self.logger.warning("[WARNING] Could not extract current date label")
        return None
        
    except Exception as e:
        self.logger.error(f"[ERROR] Failed to get date label: {e}")
        return None


def extract_reported_zones(self) -> List[Dict]:
    """Extract all reported zone elements from the current page"""
    try:
        self.logger.info("Extracting reported zone elements...")
        
        # Ensure we start from the top of the page
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        # Use similar strategy as schedule collection but for reported data
        reported_selectors = [
            "//div[@class='rbc-event-content']",  # Individual reported events
            "//div[contains(@class, 'rbc-event')]",  # Broader reported events
            "//div[contains(@class, 'timeline-block')]",  # Timeline blocks
            "//div[contains(@class, 'zone-block')]"  # Zone blocks
        ]
        
        zones = []
        
        for selector in reported_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                if elements:
                    self.logger.info(f"[OK] Found {len(elements)} reported elements with: {selector}")
                    zones = elements
                    break
            except:
                continue
        
        if not zones:
            self.logger.warning("[ERROR] No reported zone elements found")
            
            # DEBUG: Let's see what elements are actually on the page
            self.logger.info("[ANALYSIS] DEBUG: Looking for any elements that might contain zone data...")
            debug_selectors = [
                "//div[contains(text(), ':')]",  # Elements with time format
                "//div[contains(text(), 'am')]",  # Morning times
                "//div[contains(text(), 'pm')]",  # Evening times
                "//*[contains(text(), 'Pots')]",  # Common zone word
                "//*[contains(text(), 'Turf')]",  # Common zone word
                "//*[contains(text(), 'Beds')]"   # Common zone word
            ]
            
            for debug_selector in debug_selectors:
                try:
                    debug_elements = self.driver.find_elements(By.XPATH, debug_selector)
                    if debug_elements:
                        self.logger.info(f"[ANALYSIS] Found {len(debug_elements)} elements with: {debug_selector}")
                        # Show first few elements
                        for i, elem in enumerate(debug_elements[:3]):
                            try:
                                elem_text = elem.text.strip()
                                if elem_text:
                                    self.logger.info(f"   Example {i+1}: '{elem_text}'")
                            except:
                                pass
                except:
                    continue
            
            return []
            
        # Convert elements to zone data with progressive scrolling to ensure all zones are captured
        zone_data_list = []
        self.logger.info(f"[LOG] Processing {len(zones)} zone elements with progressive scrolling...")
        
        for i, element in enumerate(zones):
            try:
                # Progressive scrolling: Scroll the element into view before processing
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                    time.sleep(0.2)  # Brief pause to let scroll complete
                except:
                    pass  # Continue even if scroll fails
                
                # Extract zone name from element text
                element_text = element.text.strip()
                if element_text:
                    # Take only the first line to get zone name
                    first_line = element_text.split('\n')[0].strip()
                    if first_line and len(first_line) > 3:
                        zone_data = {
                            'element': element,
                            'zone_name': first_line,
                            'element_text': element_text,
                            'index': i
                        }
                        zone_data_list.append(zone_data)
                        self.logger.debug(f"[OK] Zone {i+1}/{len(zones)}: {first_line}")
                        
            except Exception as e:
                self.logger.debug(f"Error extracting zone {i}: {e}")
                continue
        
        # Final scroll back to top to prepare for hover operations
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        self.logger.info(f"[OK] Extracted {len(zone_data_list)} reported zones (with progressive scrolling)")
        return zone_data_list
        
    except Exception as e:
        self.logger.error(f"[ERROR] Failed to extract reported zones: {e}")
        return []


def extract_reported_runs_for_date(self, target_date: datetime) -> List:
    """Extract all reported runs for the current displayed date"""
    try:
        from hydrawise_web_scraper_refactored import ActualRun
        
        self.logger.info(f"Extracting reported runs for date: {target_date.strftime('%Y-%m-%d')}")
        
        # Get current date label to verify we're on the right date
        current_date_label = get_current_date_label(self)
        if current_date_label:
            self.logger.info(f"[DATE] Collecting reported data for: {current_date_label}")
        
        # IMPORTANT: Scroll to top before extracting zones to ensure we get all zones
        self.logger.info("[SYMBOL] Ensuring page is scrolled to top before zone extraction...")
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        # Extract all reported zone elements
        zone_data_list = extract_reported_zones(self)
        if not zone_data_list:
            self.logger.warning("[ERROR] No reported zones found")
            return []
        
        actual_runs = []
        seen_runs = set()
        
        for zone_data in zone_data_list:
            try:
                element = zone_data['element']
                zone_name = zone_data['zone_name']
                
                self.logger.info(f"[ANALYSIS] Processing reported zone: {zone_name}")
                
                # Parse time from zone name if present (e.g., "6:01am Rear Left Pots")
                parsed_start_time = None
                time_pattern = r'^(\d{1,2}:\d{2}[ap]m)'
                time_match = re.match(time_pattern, zone_name, re.IGNORECASE)
                if time_match:
                    time_str = time_match.group(1)
                    try:
                        # Parse time and combine with target date
                        time_obj = datetime.strptime(time_str, '%I:%M%p').time()
                        parsed_start_time = datetime.combine(target_date.date(), time_obj)
                        # Remove time prefix from zone name
                        zone_name = zone_name[len(time_str):].strip()
                        self.logger.debug(f"[RESULTS] Parsed time {time_str} -> {parsed_start_time}, cleaned zone: {zone_name}")
                    except:
                        self.logger.debug(f"Failed to parse time from: {time_str}")
                
                # Hover over element to get popup data with enhanced scrolling
                try:
                    # Enhanced scrolling: Center the element in viewport for reliable hover
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'});", element)
                    time.sleep(0.5)  # Allow scroll to complete
                    
                    # Ensure element is fully visible and not obstructed
                    element_rect = element.rect
                    viewport_height = self.driver.execute_script("return window.innerHeight;")
                    element_y = element_rect['y']
                    
                    self.logger.debug(f"[ANALYSIS] Hovering over zone {zone_name}: element_y={element_y}, viewport_height={viewport_height}")
                    
                    # Additional small scroll if element is too close to edges
                    if element_y < 100:  # Too close to top
                        self.driver.execute_script("window.scrollBy(0, -100);")
                        time.sleep(0.3)
                    elif element_y > (viewport_height - 150):  # Too close to bottom
                        self.driver.execute_script("window.scrollBy(0, 100);")
                        time.sleep(0.3)
                    
                    from selenium.webdriver.common.action_chains import ActionChains
                    ActionChains(self.driver).move_to_element(element).perform()
                    time.sleep(1.5)  # Wait for popup to appear
                    
                    # Extract popup data using existing popup extractor
                    import popup_extractor
                    popup_data = popup_extractor.extract_hover_popup_data_with_retry(self, zone_name)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to hover/extract popup for {zone_name}: {e}")
                    popup_data = None
                
                # Create ActualRun from collected data
                if popup_data:
                    # Use parsed time if available, otherwise try to extract from popup
                    start_time = parsed_start_time
                    if not start_time:
                        # Try to extract time from visual position or other methods
                        # For now, use a placeholder - this can be enhanced
                        start_time = target_date
                    
                    # Generate unique run ID for deduplication
                    clean_zone_name = re.sub(r'[^\w]', '', zone_name.lower())
                    start_time_str = start_time.strftime('%H:%M')
                    run_id = f"{clean_zone_name}_{start_time_str}"
                    
                    if run_id in seen_runs:
                        self.logger.debug(f"[PERIODIC] Skipping duplicate: {run_id}")
                        continue
                    seen_runs.add(run_id)
                    
                    # Extract data from popup
                    duration_minutes = popup_data.get('duration_minutes', 0)
                    actual_gallons = popup_data.get('actual_gallons')
                    current_ma = popup_data.get('current_ma')
                    status = popup_data.get('status', 'Normal watering cycle')
                    notes = popup_data.get('notes', '')
                    
                    # Determine failure reason
                    failure_reason = None
                    if 'aborted' in status.lower() or 'cancelled' in status.lower():
                        failure_reason = status
                    elif 'sensor' in notes.lower() or 'sensor' in status.lower():
                        failure_reason = "Sensor input"
                    elif 'manual' in notes.lower():
                        failure_reason = "Manual intervention"
                    
                    # Create ActualRun object with enhanced popup data
                    enhanced_notes = f"Current: {current_ma}mA, {notes}" if current_ma else notes
                    
                    actual_run = ActualRun(
                        zone_id=f'zone_{len(actual_runs) + 1}',
                        zone_name=zone_name,
                        start_time=start_time,
                        duration_minutes=duration_minutes,
                        actual_gallons=actual_gallons,
                        status=status,
                        failure_reason=failure_reason,
                        notes=enhanced_notes
                    )
                    
                    # Add enhanced popup data as attributes
                    if popup_data:
                        actual_run.raw_popup_text = popup_data.get('raw_popup_text', '')
                        actual_run.popup_lines = popup_data.get('popup_lines', [])
                        actual_run.parsed_summary = popup_data.get('parsed_summary', '')
                        actual_run.parsed_data = popup_data.get('parsed_data', {})
                    
                    actual_runs.append(actual_run)
                    self.logger.info(f"[OK] Extracted reported run {len(actual_runs)}: '{zone_name}' at {start_time_str}, {duration_minutes}min, {actual_gallons}gal - {status}")
                else:
                    self.logger.warning(f"[WARNING] No popup data for zone: {zone_name}")
                    
            except Exception as e:
                self.logger.error(f"[ERROR] Error processing zone {zone_data.get('zone_name', 'unknown')}: {e}")
                continue
        
        self.logger.info(f"[OK] Successfully extracted {len(actual_runs)} reported runs")
        return actual_runs
        
    except Exception as e:
        self.logger.error(f"[ERROR] Failed to extract reported runs: {e}")
        return []


def extract_previous_day_reported_runs(self, reference_date: datetime = None) -> List:
    """Extract reported runs for the target date (typically previous day from reference_date)"""
    try:
        if reference_date is None:
            reference_date = datetime.now()
            
        # Navigate directly to target date using efficient shared navigation (matching schedule collection)
        from shared_navigation_helper import create_navigation_helper
        nav_helper = create_navigation_helper(self)
        
        # Calculate target date
        target_date = (reference_date - timedelta(days=1)).date()
        self.logger.info(f"[SYMBOL] Navigating directly to {target_date} using efficient navigation...")
        
        if not nav_helper.navigate_to_date(target_date, "reported"):
            self.logger.error(f"[ERROR] Failed to navigate to {target_date}")
            return []
        
        self.logger.info(f"[OK] Successfully navigated to {target_date} for reported data collection")
        
        # CRITICAL: Scroll to top to ensure we capture all zones (especially early morning ones)
        self.logger.info("[SYMBOL] Scrolling to top of page to capture all zones...")
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)  # Brief pause after scroll
        
        # Also scroll the main content area to top if it exists
        try:
            # Look for common scrollable containers
            scrollable_selectors = [
                "//div[contains(@class, 'rbc-calendar')]",
                "//div[contains(@class, 'calendar')]", 
                "//div[contains(@class, 'schedule')]",
                "//div[contains(@class, 'timeline')]"
            ]
            
            for selector in scrollable_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed():
                            self.driver.execute_script("arguments[0].scrollTop = 0;", element)
                            self.logger.info(f"[OK] Scrolled container to top: {selector}")
                            break
                    break
                except:
                    continue
        except Exception as e:
            self.logger.debug(f"Could not scroll container: {e}")
        
        # Verify we're on the previous day
        current_date_label = get_current_date_label(self)
        if current_date_label:
            self.logger.info(f"[DATE] Now viewing: {current_date_label}")
        
        # Calculate previous day date
        previous_day = reference_date - timedelta(days=1)
        
        # Extract reported runs for previous day
        reported_runs = extract_reported_runs_for_date(self, previous_day)
        
        self.logger.info(f"[OK] Collected {len(reported_runs)} reported runs from previous day")
        return reported_runs
        
    except Exception as e:
        self.logger.error(f"[ERROR] Failed to extract previous day reported runs: {e}")
        return []
