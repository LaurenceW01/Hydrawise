#!/usr/bin/env python3
"""
Rain Sensor Detection Module for Hydrawise Web Scraper

Handles rain sensor status detection from the dashboard.
Cut and pasted from HydrawiseWebScraper class without modifications.

Author: AI Assistant  
Date: 2025
"""

import time
from typing import Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
