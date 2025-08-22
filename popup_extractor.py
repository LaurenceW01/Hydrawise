#!/usr/bin/env python3
"""
Popup Data Extraction Module for Hydrawise Web Scraper

Handles hover popup detection and data extraction with retry logic.
Cut and pasted from HydrawiseWebScraper class without modifications.

Author: AI Assistant  
Date: 2025
"""

import time
import re
from typing import Dict, Optional
from selenium.webdriver.common.by import By

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
            
            # Extract status/cycle type - handle all abort conditions
            if 'watering cycle' in line.lower():
                data['status'] = line
            elif 'not scheduled to run' in line.lower():
                data['status'] = line
                data['rain_suspended'] = True
                data['duration_minutes'] = 0  # Override duration to 0 for not scheduled
            elif 'aborted due to sensor input' in line.lower():
                data['status'] = line
                data['rain_suspended'] = True
                data['duration_minutes'] = 0  # Override duration to 0 for sensor abort
            elif 'aborted due to high daily rainfall' in line.lower():
                data['status'] = line
                data['rain_suspended'] = True
                data['duration_minutes'] = 0  # Override duration to 0 for rainfall abort
            elif 'scheduled to run' in line.lower() and 'not' not in line.lower():
                data['status'] = line
            elif any(keyword in line.lower() for keyword in ['suspended', 'stopped', 'sensor', 'rain', 'aborted']):
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
