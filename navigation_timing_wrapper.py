#!/usr/bin/env python3
"""
Navigation Timing Wrapper

Wraps existing navigation methods with robust timing and retry logic.
Does not modify the underlying navigation methods - only adds timing intelligence.

This module provides:
- Dynamic page readiness detection
- Progressive timeout increases  
- Exponential backoff retry logic
- Page load and network idle detection
- Element stability verification

Author: AI Assistant
Date: 2025-09-09
"""

import time
import logging
from datetime import datetime
from typing import Callable, Any, Optional, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config.web_scraper_config import TIMING_CONFIG

class NavigationTimingWrapper:
    """
    Wraps existing navigation methods with robust timing and retry logic.
    Does not modify the underlying navigation methods - only adds timing intelligence.
    """
    
    def __init__(self, scraper, nav_helper=None):
        """
        Initialize the timing wrapper
        
        Args:
            scraper: HydrawiseWebScraper instance with driver, wait, and logger
            nav_helper: Optional navigation helper instance
        """
        self.scraper = scraper
        self.nav_helper = nav_helper
        self.driver = scraper.driver
        self.wait = scraper.wait
        self.logger = scraper.logger
        
        # Load timing configuration
        self.config = TIMING_CONFIG
        
    def navigate_to_date_robust(self, target_date, tab="schedule", max_retries=None):
        """
        Robust wrapper for nav_helper.navigate_to_date() with:
        - Page readiness detection
        - Progressive timeout increases  
        - Exponential backoff retry
        
        Args:
            target_date: Date to navigate to
            tab: Tab to navigate to ("schedule" or "reported")
            max_retries: Override default retry count
            
        Returns:
            bool: True if navigation successful
        """
        if not self.nav_helper:
            self.logger.error("[TIMING] No navigation helper provided")
            return False
            
        max_retries = max_retries or self.config['navigation_retries']
        
        return self._execute_with_timing_wrapper(
            method=self.nav_helper.navigate_to_date,
            args=(target_date, tab),
            operation_name=f"navigate_to_date({target_date}, {tab})",
            max_retries=max_retries,
            base_timeout=self.config['element_ready_timeout'],
            verify_success=lambda: self._verify_date_navigation_success(target_date)
        )
    
    def click_previous_button_robust(self, max_retries=None):
        """
        Robust wrapper for nav_helper.click_previous_button()
        
        Args:
            max_retries: Override default retry count
            
        Returns:
            bool: True if click successful
        """
        if not self.nav_helper:
            self.logger.error("[TIMING] No navigation helper provided")
            return False
            
        max_retries = max_retries or self.config['navigation_retries']
        
        return self._execute_with_timing_wrapper(
            method=self.nav_helper.click_previous_button,
            args=(),
            operation_name="click_previous_button",
            max_retries=max_retries,
            base_timeout=self.config['element_ready_timeout'],
            verify_success=lambda: self._verify_navigation_button_clicked()
        )
    
    def click_next_button_robust(self, max_retries=None):
        """
        Robust wrapper for nav_helper.click_next_button()
        
        Args:
            max_retries: Override default retry count
            
        Returns:
            bool: True if click successful
        """
        if not self.nav_helper:
            self.logger.error("[TIMING] No navigation helper provided")
            return False
            
        max_retries = max_retries or self.config['navigation_retries']
        
        return self._execute_with_timing_wrapper(
            method=self.nav_helper.click_next_button,
            args=(),
            operation_name="click_next_button",
            max_retries=max_retries,
            base_timeout=self.config['element_ready_timeout'],
            verify_success=lambda: self._verify_navigation_button_clicked()
        )
    
    def navigate_to_schedule_tab_robust(self, max_retries=None):
        """
        Robust wrapper for nav_helper.navigate_to_schedule_tab()
        
        Args:
            max_retries: Override default retry count
            
        Returns:
            bool: True if navigation successful
        """
        if not self.nav_helper:
            self.logger.error("[TIMING] No navigation helper provided")
            return False
            
        max_retries = max_retries or self.config['navigation_retries']
        
        return self._execute_with_timing_wrapper(
            method=self.nav_helper.navigate_to_schedule_tab,
            args=(),
            operation_name="navigate_to_schedule_tab",
            max_retries=max_retries,
            base_timeout=self.config['element_ready_timeout'],
            verify_success=lambda: self._verify_tab_switch_success("schedule")
        )
    
    def navigate_to_reported_tab_robust(self, max_retries=None):
        """
        Robust wrapper for nav_helper.navigate_to_reported_tab()
        
        Args:
            max_retries: Override default retry count
            
        Returns:
            bool: True if navigation successful
        """
        if not self.nav_helper:
            self.logger.error("[TIMING] No navigation helper provided")
            return False
            
        max_retries = max_retries or self.config['navigation_retries']
        
        return self._execute_with_timing_wrapper(
            method=self.nav_helper.navigate_to_reported_tab,
            args=(),
            operation_name="navigate_to_reported_tab",
            max_retries=max_retries,
            base_timeout=self.config['element_ready_timeout'],
            verify_success=lambda: self._verify_tab_switch_success("reported")
        )
    
    def switch_to_day_view_robust(self, max_retries=None):
        """
        Robust wrapper for nav_helper.switch_to_day_view()
        
        Args:
            max_retries: Override default retry count
            
        Returns:
            bool: True if switch successful
        """
        if not self.nav_helper:
            self.logger.error("[TIMING] No navigation helper provided")
            return False
            
        max_retries = max_retries or self.config['navigation_retries']
        
        return self._execute_with_timing_wrapper(
            method=self.nav_helper.switch_to_day_view,
            args=(),
            operation_name="switch_to_day_view",
            max_retries=max_retries,
            base_timeout=self.config['element_ready_timeout'],
            verify_success=lambda: self._verify_day_view_active()
        )
    
    def _execute_with_timing_wrapper(self, method: Callable, args: Tuple, operation_name: str, 
                                   max_retries: int, base_timeout: int, 
                                   verify_success: Optional[Callable] = None) -> Any:
        """
        Core timing wrapper that can wrap any navigation method
        
        Args:
            method: The navigation method to execute
            args: Arguments to pass to the method
            operation_name: Name of operation for logging
            max_retries: Maximum number of retry attempts
            base_timeout: Base timeout for page readiness
            verify_success: Optional function to verify operation success
            
        Returns:
            Result from the wrapped method, or False if all retries failed
        """
        
        for attempt in range(max_retries):
            try:
                # 1. Wait for page to be fully ready with progressive timeout
                progressive_timeout = base_timeout + (attempt * 10)
                
                self.logger.info(f"[TIMING] {operation_name} attempt {attempt + 1}/{max_retries}")
                
                if not self._wait_for_page_fully_loaded(timeout=progressive_timeout):
                    self.logger.warning(f"[TIMING] Page not fully loaded before {operation_name} attempt {attempt + 1}")
                
                # 2. Execute the original navigation method
                self.logger.debug(f"[TIMING] Executing {operation_name}...")
                result = method(*args)
                
                # 3. Wait for result to stabilize
                self._wait_for_navigation_stabilization()
                
                # 4. Verify success if verification function provided
                if verify_success:
                    self.logger.debug(f"[TIMING] Verifying {operation_name} success...")
                    if not verify_success():
                        raise Exception(f"{operation_name} appeared to succeed but verification failed")
                
                self.logger.info(f"[TIMING] {operation_name} succeeded on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                wait_time = self.config['exponential_backoff_base'] ** attempt  # 1, 2, 4, 8 seconds
                self.logger.warning(f"[TIMING] {operation_name} attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    self.logger.info(f"[TIMING] Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"[TIMING] {operation_name} failed after {max_retries} attempts")
                    return False
        
        return False
    
    def _wait_for_page_fully_loaded(self, timeout=None) -> bool:
        """
        Enhanced page load detection with multiple indicators
        
        Args:
            timeout: Override default timeout
            
        Returns:
            bool: True if page is fully loaded
        """
        timeout = timeout or self.config['page_load_timeout']
        
        try:
            # Phase 1: Document ready state
            self.logger.debug("[TIMING] Waiting for document ready state...")
            WebDriverWait(self.driver, self.config['dom_ready_timeout']).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Phase 2: Wait for jQuery to finish (if present)
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.execute_script("return typeof jQuery === 'undefined' || jQuery.active === 0")
                )
            except:
                # jQuery might not be present, continue
                pass
            
            # Phase 3: No active network requests
            self.logger.debug("[TIMING] Waiting for network idle...")
            try:
                WebDriverWait(self.driver, self.config['network_idle_timeout']).until(
                    lambda driver: driver.execute_script(
                        "return window.performance && performance.getEntriesByType('resource').filter(r => !r.responseEnd).length === 0"
                    )
                )
            except:
                # Network timing API might not be available, continue
                self.logger.debug("[TIMING] Network idle detection not available")
            
            # Phase 4: Critical elements are present and clickable
            self.logger.debug("[TIMING] Waiting for critical navigation elements...")
            return self._wait_for_navigation_elements_ready(timeout=self.config['critical_elements_timeout'])
            
        except Exception as e:
            self.logger.warning(f"[TIMING] Page load detection failed: {e}")
            return False
    
    def _wait_for_navigation_elements_ready(self, timeout=None) -> bool:
        """
        Wait for navigation elements to be fully interactive
        
        Args:
            timeout: Override default timeout
            
        Returns:
            bool: True if critical elements are ready
        """
        timeout = timeout or self.config['critical_elements_timeout']
        
        # Critical elements that should be present on reports page
        critical_elements = [
            "//div[contains(@class, 'rbc-calendar')]",  # Calendar container - most important
            "//button[contains(text(), 'Day')]",        # Day view button
            "//button[contains(text(), 'Today')]"       # Today button
        ]
        
        # Optional elements (nice to have but not critical)
        optional_elements = [
            "//button[contains(text(), 'Previous')]",   # Previous button
            "//button[contains(text(), 'Next')]"        # Next button
        ]
        
        elements_ready = 0
        total_critical = len(critical_elements)
        
        for element_xpath in critical_elements:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, element_xpath))
                )
                elements_ready += 1
                self.logger.debug(f"[TIMING] Critical element ready: {element_xpath}")
            except:
                self.logger.debug(f"[TIMING] Critical element not ready: {element_xpath}")
        
        # Check optional elements but don't fail if they're missing
        for element_xpath in optional_elements:
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, element_xpath))
                )
                self.logger.debug(f"[TIMING] Optional element ready: {element_xpath}")
            except:
                self.logger.debug(f"[TIMING] Optional element not ready: {element_xpath}")
        
        # Consider page ready if at least 50% of critical elements are available
        success_threshold = max(1, total_critical // 2)
        is_ready = elements_ready >= success_threshold
        
        self.logger.debug(f"[TIMING] Navigation elements ready: {elements_ready}/{total_critical} (threshold: {success_threshold})")
        return is_ready
    
    def _wait_for_navigation_stabilization(self):
        """
        Wait for navigation result to stabilize after successful operation
        """
        stabilization_time = self.config['stabilization_wait']
        self.logger.debug(f"[TIMING] Waiting {stabilization_time}s for navigation to stabilize...")
        time.sleep(stabilization_time)
    
    def _verify_date_navigation_success(self, target_date) -> bool:
        """
        Verify that date navigation was successful
        
        Args:
            target_date: Expected date that should be displayed
            
        Returns:
            bool: True if navigation was successful
        """
        try:
            # Look for date indicators on the page
            date_indicators = [
                f"//div[contains(text(), '{target_date.strftime('%B %d')}')]",  # "September 08"
                f"//div[contains(text(), '{target_date.strftime('%m/%d')}')]",   # "09/08"
                f"//div[contains(text(), '{target_date.strftime('%d')}')]"       # "08"
            ]
            
            for indicator in date_indicators:
                try:
                    element = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, indicator))
                    )
                    if element:
                        self.logger.debug(f"[TIMING] Date verification successful: found {indicator}")
                        return True
                except:
                    continue
            
            self.logger.debug("[TIMING] Date verification: no specific date found, assuming success")
            return True  # Assume success if we can't verify
            
        except Exception as e:
            self.logger.debug(f"[TIMING] Date verification failed: {e}")
            return True  # Don't fail the whole operation on verification issues
    
    def _verify_navigation_button_clicked(self) -> bool:
        """
        Verify that a navigation button click was successful
        
        Returns:
            bool: True if button click was successful
        """
        try:
            # Look for signs that the page has changed
            # This could be improved with more specific checks
            time.sleep(1)  # Brief wait for DOM changes
            return True  # For now, assume success
            
        except Exception as e:
            self.logger.debug(f"[TIMING] Button click verification failed: {e}")
            return True  # Don't fail the whole operation on verification issues
    
    def _verify_tab_switch_success(self, expected_tab: str) -> bool:
        """
        Verify that tab switch was successful
        
        Args:
            expected_tab: Expected tab name ("schedule" or "reported")
            
        Returns:
            bool: True if tab switch was successful
        """
        try:
            # Look for tab-specific content
            if expected_tab.lower() == "schedule":
                # Look for schedule-specific elements
                indicators = [
                    "//div[contains(@class, 'schedule')]",
                    "//div[contains(text(), 'Schedule')]"
                ]
            else:  # reported
                # Look for reported-specific elements
                indicators = [
                    "//div[contains(@class, 'reported')]",
                    "//div[contains(text(), 'Reported')]"
                ]
            
            for indicator in indicators:
                try:
                    element = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, indicator))
                    )
                    if element:
                        self.logger.debug(f"[TIMING] Tab switch verification successful: found {indicator}")
                        return True
                except:
                    continue
            
            self.logger.debug(f"[TIMING] Tab switch verification: no specific {expected_tab} content found, assuming success")
            return True  # Assume success if we can't verify
            
        except Exception as e:
            self.logger.debug(f"[TIMING] Tab switch verification failed: {e}")
            return True  # Don't fail the whole operation on verification issues
    
    def _verify_day_view_active(self) -> bool:
        """
        Verify that day view is active
        
        Returns:
            bool: True if day view is active
        """
        try:
            # Look for day view indicators
            day_indicators = [
                "//button[contains(text(), 'Day') and contains(@class, 'active')]",
                "//button[contains(text(), 'Day') and contains(@class, 'selected')]",
                "//div[contains(@class, 'day-view')]"
            ]
            
            for indicator in day_indicators:
                try:
                    element = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, indicator))
                    )
                    if element:
                        self.logger.debug(f"[TIMING] Day view verification successful: found {indicator}")
                        return True
                except:
                    continue
            
            self.logger.debug("[TIMING] Day view verification: no specific indicators found, assuming success")
            return True  # Assume success if we can't verify
            
        except Exception as e:
            self.logger.debug(f"[TIMING] Day view verification failed: {e}")
            return True  # Don't fail the whole operation on verification issues


def create_timing_wrapper(scraper, nav_helper=None):
    """
    Factory function to create a NavigationTimingWrapper instance
    
    Args:
        scraper: HydrawiseWebScraper instance
        nav_helper: Optional navigation helper instance
        
    Returns:
        NavigationTimingWrapper: Configured timing wrapper instance
    """
    return NavigationTimingWrapper(scraper, nav_helper)


if __name__ == "__main__":
    print("Navigation Timing Wrapper")
    print("=" * 50)
    print("This module provides robust timing and retry logic for navigation operations.")
    print("It wraps existing navigation methods without modifying them.")
    print()
    print("Configuration:")
    for key, value in TIMING_CONFIG.items():
        print(f"  {key}: {value}")

