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
    
    # Balanced memory optimization for Render.com Starter plan (512MB limit)
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins") 
    options.add_argument("--disable-images")  # Save memory and bandwidth
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max_old_space_size=300")  # Increase to 300MB for stability
    options.add_argument("--remote-debugging-port=0")
    # Essential Render.com options
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    # Add stability options
    options.add_argument("--disable-web-security")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    
    # Set Chrome binary location for render.com and local environments
    chrome_binary_paths = [
        "/opt/render/project/.render/chrome/opt/google/chrome/chrome", # Render.com installation
        "/usr/bin/google-chrome",       # Standard Linux location
        "/usr/bin/google-chrome-stable", # Ubuntu/Debian standard
        "/usr/bin/chromium-browser",    # Chromium alternative
        "/usr/bin/chromium",            # Another Chromium location
        os.getenv('CHROME_BIN')         # Environment variable override
    ]
    
    chrome_found = False
    for chrome_path in chrome_binary_paths:
        if chrome_path and os.path.exists(chrome_path):
            options.binary_location = chrome_path
            self.logger.info(f"Using Chrome binary: {chrome_path}")
            chrome_found = True
            break
    
    if not chrome_found:
        self.logger.warning("Chrome binary not found in standard locations. Selenium will use system PATH.")
        # List what we checked for debugging
        self.logger.warning(f"Checked paths: {[p for p in chrome_binary_paths if p]}")
        # Check if any Chrome-like binaries exist
        import subprocess
        try:
            result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"Found Chrome via 'which': {result.stdout.strip()}")
                options.binary_location = result.stdout.strip()
        except Exception as e:
            self.logger.warning(f"Could not run 'which' command: {e}")
    
    # Conservative GPU disabling - just enough to prevent errors without breaking functionality
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-gpu-sandbox")
    options.add_argument("--disable-gpu-rasterization")
    options.add_argument("--disable-gpu-compositing")
    options.add_argument("--disable-features=VizDisplayCompositor,VizDisplayCompositorNG,Vulkan,UseSkiaRenderer")
    options.add_argument("--disable-3d-apis")
    options.add_argument("--disable-webgl")
    options.add_argument("--disable-webgl2")
    options.add_argument("--disable-canvas-aa")
    options.add_argument("--disable-2d-canvas-clip-aa")
    options.add_argument("--disable-gl-drawing-for-tests")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-blink-features=AutomationControlled")
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
    
    # Additional stability options for tab crash prevention
    # Moderate error suppression - reduce noise without breaking functionality
    options.add_argument("--disable-logging")
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--log-level=3")  # Only fatal errors
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max_old_space_size=16384")  # Increased from 8GB to 16GB
    options.add_argument("--max-heap-size=16384")
    options.add_argument("--aggressive-cache-discard")
    options.add_argument("--purge-memory-button")
    options.add_argument("--js-flags=--max-old-space-size=16384")  # V8 specific setting
    options.add_argument("--enable-precise-memory-info")
    options.add_argument("--force-high-dpi-scaling=1")
    options.add_argument("--disable-accelerated-2d-canvas")
    options.add_argument("--disable-accelerated-jpeg-decoding")
    options.add_argument("--disable-accelerated-mjpeg-decode")
    options.add_argument("--disable-accelerated-video-decode")
    
    # Note: Removed --single-process as it causes V8 proxy resolver and GPU context issues
    
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
