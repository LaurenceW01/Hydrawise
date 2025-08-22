#!/usr/bin/env python3
"""
Actual Run Data Collection Module for Hydrawise Web Scraper

Handles extraction of actual/reported irrigation runs from the Reported tab.
Cut and pasted from HydrawiseWebScraper class without modifications.

Author: AI Assistant  
Date: 2025
"""

import time
import re
from datetime import datetime
from typing import List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

def extract_actual_runs(self, target_date: datetime) -> List:
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
                from hydrawise_web_scraper import ActualRun  # Import here to avoid circular imports
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
