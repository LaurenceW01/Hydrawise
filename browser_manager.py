#!/usr/bin/env python3
"""
Browser Management Module for Hydrawise Web Scraper

Handles browser setup, authentication, and basic navigation.
Cut and pasted from HydrawiseWebScraper class without modifications.

Author: AI Assistant  
Date: 2025
"""

import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def setup_logging(self):
    """Set up logging for the scraper"""
    # Set up logging with timestamp and level
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format)
    
    self.logger = logging.getLogger(__name__)

def start_browser(self):
    """Start the Chrome browser with appropriate settings"""
    self.logger.info("Starting Chrome browser...")
    
    options = Options()
    
    if self.headless:
        options.add_argument("--headless")
        
    # Additional options for stability and compatibility
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Disable Google API services to prevent quota issues
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-hang-monitor")
    options.add_argument("--disable-prompt-on-repost")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-web-security")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--no-report-upload")
    options.add_argument("--disable-features=VizDisplayCompositor,TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    
    # Disable Google Cloud Messaging and registration services
    options.add_argument("--disable-background-mode")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins-discovery")
    options.add_argument("--disable-preconnect")
    
    # Use webdriver-manager to handle ChromeDriver installation
    service = Service(ChromeDriverManager().install())
    
    self.driver = webdriver.Chrome(service=service, options=options)
    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Set up WebDriverWait
    self.wait = WebDriverWait(self.driver, 20)
    
    self.logger.info("Browser started successfully")

def stop_browser(self):
    """Stop the browser and clean up"""
    if self.driver:
        try:
            self.driver.quit()
            self.logger.info("Browser stopped")
        except Exception as e:
            self.logger.debug(f"Browser cleanup warning (harmless): {e}")
            self.logger.info("Browser stopped")

def login(self) -> bool:
    """
    Login to the Hydrawise portal
    
    Returns:
        bool: True if login successful, False otherwise
    """
    try:
        self.logger.info("[SYMBOL] Step 1: Logging into Hydrawise portal...")
        
        # Navigate to login page
        self.driver.get(self.login_url)
        
        # Wait for and fill email field
        email_field = self.wait.until(
            EC.presence_of_element_located((By.XPATH, '//input[@placeholder="Email"]'))
        )
        email_field.clear()
        email_field.send_keys(self.username)
        
        # Fill password field
        password_field = self.driver.find_element(By.XPATH, '//input[@placeholder="Password"]')
        password_field.clear()
        password_field.send_keys(self.password)
        
        # Click login button
        login_button = self.driver.find_element(By.XPATH, '//button[contains(text(), "Log in")]')
        login_button.click()
        
        # Wait for successful login (check for dashboard or redirect)
        time.sleep(5)
        
        # Check if we're redirected to dashboard or if we're still on login page
        current_url = self.driver.current_url
        if "login" not in current_url.lower():
            self.logger.info("Login successful")
            return True
        else:
            self.logger.error("Login failed - still on login page")
            return False
            
    except Exception as e:
        self.logger.error(f"Login failed: {e}")
        return False

def navigate_to_reports(self):
    """Navigate to the reports page"""
    try:
        self.logger.info("[SYMBOL] Step 2: Navigating to reports page...")
        
        # Step 2: Navigate to reports URL with 2 second delay (as specified)
        self.driver.get(self.reports_url)
        self.logger.info("[SYMBOL] Waiting 2 seconds after reports page load...")
        time.sleep(2)
        
        # Log current URL for debugging
        current_url = self.driver.current_url
        self.logger.info(f"Current URL after login: {current_url}")
        
        # Wait for page to load by looking for a reports-specific element
        # Look for the "Reports" heading or similar element
        try:
            # Wait for the page to load with multiple possible indicators
            # Reordered to try the most reliable approach first based on log analysis
            indicators = [
                "//div[contains(@class, 'reports')]",  # Most reliable - uses class attribute
                "//h1[contains(text(), 'Reports')]",
                "//h2[contains(text(), 'Reports')]", 
                "//*[contains(text(), 'Schedule')]",
                "//*[contains(text(), 'Reported')]"
            ]
            
            element_found = False
            for indicator in indicators:
                try:
                    element = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, indicator))
                    )
                    if element:
                        self.logger.info(f"Reports page loaded successfully")
                        element_found = True
                        break
                except:
                    continue
                    
            if not element_found:
                self.logger.warning("Could not confirm reports page loaded, but continuing...")
                
        except Exception as e:
            self.logger.warning(f"Could not verify reports page load: {e}")
            
        return True
        
    except Exception as e:
        self.logger.error(f"[ERROR] Failed to navigate to reports: {e}")
        return False

def set_date(self, target_date: datetime):
    """
    Set the date for data extraction (placeholder for date navigation)
    
    Args:
        target_date (datetime): The date to set
    """
    # This method serves as a placeholder for more complex date navigation
    # For now, we rely on the current date being displayed
    self.logger.info(f"Target date set to: {target_date.date()}")
    # Actual date navigation would be implemented in navigation_helper.py
