#!/usr/bin/env python3
"""
Hydrawise Web Portal Scraper - Refactored Main Class

Lightweight main class that delegates to specialized modules.
Each module is under 500 lines, maintaining all original functionality.

Key capabilities:
- Login to Hydrawise portal with stored credentials
- Extract complete daily schedules from Schedule tab
- Extract actual runs with failure details from Reported tab  
- Capture hover popup data for water usage amounts
- Compare scheduled vs actual to detect failures requiring alerts
- Rain sensor detection and smart handling of suspended conditions

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

# Import specialized modules
import browser_manager
import popup_extractor
import schedule_collector
import actual_run_collector
import shared_navigation_helper
import sensor_detector

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
    Refactored web scraper for Hydrawise portal.
    Delegates functionality to specialized modules while maintaining all original capabilities.
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
        browser_manager.setup_logging(self)
        
    # ========== BROWSER MANAGEMENT (DELEGATED) ==========
    def start_browser(self):
        """Start the Chrome browser with appropriate settings"""
        return browser_manager.start_browser(self)
    
    def stop_browser(self):
        """Stop the browser and clean up"""
        return browser_manager.stop_browser(self)
    
    def login(self) -> bool:
        """Login to the Hydrawise portal"""
        return browser_manager.login(self)
    
    def navigate_to_reports(self):
        """Navigate to the reports page"""
        return browser_manager.navigate_to_reports(self)
    
    def set_date(self, target_date: datetime):
        """Set the date for data extraction"""
        return browser_manager.set_date(self, target_date)
    
    # ========== POPUP EXTRACTION (DELEGATED) ==========
    def extract_hover_popup_data(self) -> Optional[Dict]:
        """Extract data from hover popup"""
        return popup_extractor.extract_hover_popup_data(self)
    
    def extract_hover_popup_data_with_retry(self, zone_name: str = "", max_retries: int = 3) -> Optional[Dict]:
        """Extract popup data with retry logic for improved reliability"""
        return popup_extractor.extract_hover_popup_data_with_retry(self, zone_name, max_retries)
    
    # ========== SCHEDULE COLLECTION (DELEGATED) ==========
    def extract_scheduled_runs(self, target_date: datetime, limit_zones: int = None, skip_schedule_click: bool = False, skip_day_click: bool = False) -> List[ScheduledRun]:
        """Extract scheduled runs from the Schedule tab"""
        return schedule_collector.extract_scheduled_runs(self, target_date, limit_zones, skip_schedule_click, skip_day_click)
    
    def collect_24_hour_schedule(self, start_date: datetime = None, limit_zones: int = None) -> Dict[str, List]:
        """Collect schedule data for current day and next day (24 hour window)"""
        return schedule_collector.collect_24_hour_schedule(self, start_date, limit_zones)
    
    def extract_previous_day_reported_runs(self, reference_date: datetime = None) -> List:
        """Extract reported runs from the previous day"""
        import reported_run_collector
        return reported_run_collector.extract_previous_day_reported_runs(self, reference_date)
    
    def _setup_schedule_view(self) -> bool:
        """Setup the Schedule view and ensure it's ready for navigation"""
        return schedule_collector._setup_schedule_view(self)
    
    # ========== ACTUAL RUN COLLECTION (DELEGATED) ==========
    def extract_actual_runs(self, target_date: datetime) -> List[ActualRun]:
        """Extract actual runs from the Reported tab"""
        return actual_run_collector.extract_actual_runs(self, target_date)
    
    # ========== NAVIGATION (SHARED HELPER) ==========
    def navigate_to_date(self, target_date: datetime, tab: str = "schedule") -> bool:
        """Navigate to a specific date using intelligent hierarchical navigation"""
        nav_helper = shared_navigation_helper.create_navigation_helper(self)
        return nav_helper.navigate_to_date(target_date, tab)
    
    def get_current_displayed_date(self) -> Optional[str]:
        """Get the currently displayed date from the page"""
        nav_helper = shared_navigation_helper.create_navigation_helper(self)
        return nav_helper.get_current_displayed_date()
    
    def navigate_to_schedule_tab(self) -> bool:
        """Navigate to Schedule tab"""
        nav_helper = shared_navigation_helper.create_navigation_helper(self)
        return nav_helper.navigate_to_schedule_tab()
    
    def navigate_to_reported_tab(self) -> bool:
        """Navigate to Reported tab"""
        nav_helper = shared_navigation_helper.create_navigation_helper(self)
        return nav_helper.navigate_to_reported_tab()
    
    def _debug_available_buttons(self):
        """Debug method to see what buttons are available on the page"""
        nav_helper = shared_navigation_helper.create_navigation_helper(self)
        return nav_helper._debug_available_buttons()
    
    # ========== SENSOR DETECTION (DELEGATED) ==========
    def check_rain_sensor_status(self) -> Dict[str, any]:
        """Check the rain sensor status from dashboard to detect irrigation suspension"""
        return sensor_detector.check_rain_sensor_status(self)
    
    # ========== CORE ANALYSIS METHODS (KEPT IN MAIN CLASS) ==========
    def detect_failures(self, scheduled_runs: List[ScheduledRun], actual_runs: List[ActualRun]) -> List[IrrigationFailure]:
        """
        Compare scheduled vs actual runs to detect irrigation failures.
        
        Args:
            scheduled_runs: List of scheduled irrigation runs
            actual_runs: List of actual irrigation runs
            
        Returns:
            List of detected failures requiring attention
        """
        failures = []
        
        try:
            self.logger.info("Analyzing irrigation data for failures...")
            
            # Create a mapping of actual runs by time window for efficient lookup
            actual_runs_by_time = {}
            for actual_run in actual_runs:
                # Use 30-minute window to account for timing variations
                time_key = actual_run.start_time.replace(minute=0, second=0, microsecond=0)
                if time_key not in actual_runs_by_time:
                    actual_runs_by_time[time_key] = []
                actual_runs_by_time[time_key].append(actual_run)
                
            # Check each scheduled run for problems
            for scheduled_run in scheduled_runs:
                # Look for matching actual run in 30-minute window
                scheduled_time_key = scheduled_run.start_time.replace(minute=0, second=0, microsecond=0)
                
                # Check current hour and adjacent hours for matches
                matching_actual_runs = []
                for time_offset in [-1, 0, 1]:  # Check hour before, same hour, hour after
                    check_time = scheduled_time_key + timedelta(hours=time_offset)
                    if check_time in actual_runs_by_time:
                        for actual_run in actual_runs_by_time[check_time]:
                            # Check if zone names match (fuzzy matching)
                            if self._zones_match(scheduled_run.zone_name, actual_run.zone_name):
                                # Check if times are within 30 minutes
                                time_diff = abs((scheduled_run.start_time - actual_run.start_time).total_seconds())
                                if time_diff <= 1800:  # 30 minutes
                                    matching_actual_runs.append(actual_run)
                
                if not matching_actual_runs:
                    # No matching actual run found - this is a missed run
                    failure = IrrigationFailure(
                        failure_id=f"missed_{scheduled_run.zone_id}_{scheduled_run.start_time.strftime('%H%M')}",
                        timestamp=datetime.now(),
                        zone_id=scheduled_run.zone_id,
                        zone_name=scheduled_run.zone_name,
                        failure_type="missed_run",
                        description=f"Scheduled run at {scheduled_run.start_time.strftime('%I:%M %p')} did not execute",
                        scheduled_run=scheduled_run,
                        actual_run=None,
                        action_required="Check zone and manually run if needed",
                        priority=self._get_failure_priority(scheduled_run.zone_name, "missed_run")
                    )
                    failures.append(failure)
                    
                else:
                    # Found matching run(s) - check for other issues
                    for actual_run in matching_actual_runs:
                        # Check for abnormal status
                        if "aborted" in actual_run.status.lower() or "cancelled" in actual_run.status.lower():
                            failure = IrrigationFailure(
                                failure_id=f"aborted_{actual_run.zone_id}_{actual_run.start_time.strftime('%H%M')}",
                                timestamp=datetime.now(),
                                zone_id=actual_run.zone_id,
                                zone_name=actual_run.zone_name,
                                failure_type="sensor_abort",
                                description=f"Run aborted: {actual_run.status}",
                                scheduled_run=scheduled_run,
                                actual_run=actual_run,
                                action_required="Check sensor conditions and manually run if safe",
                                priority=self._get_failure_priority(actual_run.zone_name, "sensor_abort")
                            )
                            failures.append(failure)
                            
                        # Check for duration issues
                        if scheduled_run.duration_minutes > 0 and actual_run.duration_minutes > 0:
                            duration_ratio = actual_run.duration_minutes / scheduled_run.duration_minutes
                            if duration_ratio < 0.5:  # Ran for less than 50% of scheduled time
                                failure = IrrigationFailure(
                                    failure_id=f"short_{actual_run.zone_id}_{actual_run.start_time.strftime('%H%M')}",
                                    timestamp=datetime.now(),
                                    zone_id=actual_run.zone_id,
                                    zone_name=actual_run.zone_name,
                                    failure_type="short_run",
                                    description=f"Ran {actual_run.duration_minutes} min instead of {scheduled_run.duration_minutes} min",
                                    scheduled_run=scheduled_run,
                                    actual_run=actual_run,
                                    action_required="Check for flow issues and consider additional watering",
                                    priority=self._get_failure_priority(actual_run.zone_name, "short_run")
                                )
                                failures.append(failure)
                        
        except Exception as e:
            self.logger.error(f"Failed to detect failures: {e}")
            
        self.logger.info(f"Detected {len(failures)} irrigation failures")
        return failures
    
    def _zones_match(self, zone1: str, zone2: str) -> bool:
        """Check if two zone names refer to the same zone (fuzzy matching)"""
        # Simple fuzzy matching - can be enhanced
        zone1_clean = zone1.lower().strip()
        zone2_clean = zone2.lower().strip()
        
        # Exact match
        if zone1_clean == zone2_clean:
            return True
            
        # Check if one is contained in the other
        if zone1_clean in zone2_clean or zone2_clean in zone1_clean:
            return True
            
        # Check key words match
        zone1_words = set(zone1_clean.split())
        zone2_words = set(zone2_clean.split())
        common_words = zone1_words.intersection(zone2_words)
        
        # If they share 2+ significant words, consider them matching
        significant_words = common_words - {'the', 'and', 'or', 'at', 'in', 'on'}
        return len(significant_words) >= 2
    
    def _get_failure_priority(self, zone_name: str, failure_type: str) -> str:
        """Determine failure priority based on zone type and failure severity"""
        zone_lower = zone_name.lower()
        
        # HIGH priority zones (plants that die quickly without water)
        if any(keyword in zone_lower for keyword in ['planter', 'pot', 'basket', 'flower', 'bed']):
            if failure_type == "missed_run":
                return "CRITICAL"
            else:
                return "WARNING"
                
        # MEDIUM priority zones (turf, established plantings)
        elif any(keyword in zone_lower for keyword in ['turf', 'lawn', 'grass']):
            if failure_type == "missed_run":
                return "WARNING"
            else:
                return "INFO"
                
        # Default priority
        return "WARNING"
    
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
        """Save extracted data to JSON files for analysis"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            
            # Save scheduled runs
            scheduled_data = [asdict(run) for run in scheduled]
            with open(f'data/scheduled_runs_{timestamp}.json', 'w') as f:
                json.dump(scheduled_data, f, indent=2, default=str)
                
            # Save actual runs
            actual_data = [asdict(run) for run in actual]
            with open(f'data/actual_runs_{timestamp}.json', 'w') as f:
                json.dump(actual_data, f, indent=2, default=str)
                
            # Save failures
            failure_data = [asdict(failure) for failure in failures]
            with open(f'data/failures_{timestamp}.json', 'w') as f:
                json.dump(failure_data, f, indent=2, default=str)
                
            self.logger.info(f"Saved data files for {date.date()} at {timestamp}")
            
        except Exception as e:
            self.logger.error(f"Failed to save data files: {e}")
