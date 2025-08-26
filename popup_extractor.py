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
            'current_ma': None,
            'raw_popup_text': popup_text,  # Store complete original text
            'popup_lines': [],  # Store each line individually
            'parsed_data': {}  # Store structured parsed data
        }
        
        lines = popup_text.split('\n')
        
        # Store each line with metadata
        for i, line in enumerate(lines):
            line = line.strip()
            if line:  # Only store non-empty lines
                line_data = {
                    'line_number': i + 1,
                    'text': line,
                    'type': 'unknown',  # Will be determined by content
                    'parsed_value': None
                }
                data['popup_lines'].append(line_data)
            
            # Identify and categorize each line type
            line_type = 'other'
            parsed_value = None
            
            # Extract status/cycle type - handle all abort conditions
            if 'watering cycle' in line.lower():
                data['status'] = line
                line_type = 'status'
                parsed_value = line
            elif 'not scheduled to run' in line.lower():
                data['status'] = line
                data['rain_suspended'] = True
                data['duration_minutes'] = 0  # Override duration to 0 for not scheduled
                line_type = 'status'
                parsed_value = 'not_scheduled_rain'
            elif 'aborted due to sensor input' in line.lower():
                data['status'] = line
                data['rain_suspended'] = True
                data['duration_minutes'] = 0  # Override duration to 0 for sensor abort
                line_type = 'status'
                parsed_value = 'aborted_sensor'
            elif 'aborted due to high daily rainfall' in line.lower():
                data['status'] = line
                data['rain_suspended'] = True
                data['duration_minutes'] = 0  # Override duration to 0 for rainfall abort
                line_type = 'status'
                parsed_value = 'aborted_rainfall'
            elif 'scheduled to run' in line.lower() and 'not' not in line.lower():
                data['status'] = line
                line_type = 'status'
                parsed_value = 'scheduled'
            elif any(keyword in line.lower() for keyword in ['suspended', 'stopped', 'sensor', 'rain', 'aborted']):
                data['status'] = line
                line_type = 'status'
                parsed_value = 'suspended_other'
                if 'sensor' in line.lower() or 'rain' in line.lower():
                    data['rain_suspended'] = True
            
            # Extract time information
            time_match = re.search(r'Time[:\s]*([^,\n]+)', line, re.IGNORECASE)
            if time_match:
                time_str = time_match.group(1).strip()
                data['time_info'] = time_str
                line_type = 'time'
                parsed_value = time_str
            
            # Extract duration - try multiple patterns for both minutes and seconds
            duration_patterns = [
                r'Duration[:\s]*(\d+)\s*minutes?',  # "Duration: 3 minutes"
                r'Duration[:\s]*(\d+)\s*mins?',     # "Duration: 3 min"
                r'Duration[:\s]*(\d+)\s*seconds?',  # "Duration: 50 seconds"
                r'Duration[:\s]*(\d+)\s*secs?',     # "Duration: 50 sec"
                r'(\d+)\s*minutes?\s*duration',     # "3 minutes duration"  
                r'(\d+)\s*seconds?\s*duration',     # "50 seconds duration"
                r'Duration[:\s]*(\d+)',             # "Duration: 3"
            ]
            
            for pattern in duration_patterns:
                duration_match = re.search(pattern, line, re.IGNORECASE)
                if duration_match:
                    duration_value = int(duration_match.group(1))
                    
                    # Check if the matched text contains "seconds" and convert to decimal minutes
                    if re.search(r'seconds?|secs?', line, re.IGNORECASE):
                        # Convert seconds to decimal minutes
                        duration_minutes = duration_value / 60.0
                        self.logger.debug(f"Converted {duration_value} seconds to {duration_minutes} minutes")
                    else:
                        # Already in minutes
                        duration_minutes = duration_value
                    
                    data['duration_minutes'] = duration_minutes
                    line_type = 'duration'
                    parsed_value = duration_minutes
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
                    line_type = 'water_usage'
                    parsed_value = gallons
                    break
            
            # Extract current reading
            current_match = re.search(r'Current[:\s]*([0-9.]+)\s*mA', line, re.IGNORECASE)
            if current_match:
                current_value = float(current_match.group(1))
                data['current_ma'] = current_value
                line_type = 'current'
                parsed_value = current_value
            
            # Extract zone name (if in popup)
            if any(keyword in line.lower() for keyword in ['rear', 'front', 'left', 'right', 'pots', 'beds', 'turf']):
                if not data['zone_name'] and len(line) > 5:
                    data['zone_name'] = line
                    line_type = 'zone_name'
                    parsed_value = line
            
            # Update the line data with identified type and parsed value
            if data['popup_lines'] and line:
                # Find the corresponding line data and update it
                for line_data in data['popup_lines']:
                    if line_data['text'] == line:
                        line_data['type'] = line_type
                        line_data['parsed_value'] = parsed_value
                        break
        
        # Enhanced logging for detailed popup analysis
        self.logger.debug(f"Raw popup text: {popup_text}")
        self.logger.debug(f"Extracted popup data: {data}")
        
        # Log each parsed line with details
        if data['popup_lines']:
            self.logger.info(f"📄 POPUP ANALYSIS - {len(data['popup_lines'])} lines:")
            for line_data in data['popup_lines']:
                line_type = line_data['type']
                parsed_val = line_data['parsed_value']
                line_text = line_data['text']
                if parsed_val is not None:
                    self.logger.info(f"  Line {line_data['line_number']} [{line_type.upper()}]: '{line_text}' → {parsed_val}")
                else:
                    self.logger.info(f"  Line {line_data['line_number']} [{line_type.upper()}]: '{line_text}'")
        
        # Summary logging for key extracted data
        summary_items = []
        if 'duration_minutes' in data and data['duration_minutes'] > 0:
            summary_items.append(f"Duration: {data['duration_minutes']} min")
        elif 'rain_suspended' in data and data['rain_suspended']:
            summary_items.append("Status: RAIN SUSPENDED")
            data['duration_minutes'] = 0  # Set to 0 for rain-suspended zones
            
        if 'actual_gallons' in data and data['actual_gallons']:
            summary_items.append(f"Water: {data['actual_gallons']} gal")
        
        if 'current_ma' in data and data['current_ma']:
            summary_items.append(f"Current: {data['current_ma']} mA")
            
        if 'status' in data and data['status'] != 'Unknown':
            summary_items.append(f"Status: {data['status']}")
            
        if summary_items:
            self.logger.info(f"📊 POPUP SUMMARY: {' | '.join(summary_items)}")
        else:
            self.logger.warning(f"⚠️ NO STRUCTURED DATA: Could not parse popup: '{popup_text[:100]}...'")
            
        # Store parsed summary for easy access
        data['parsed_summary'] = ' | '.join(summary_items) if summary_items else 'No data parsed'
        
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
