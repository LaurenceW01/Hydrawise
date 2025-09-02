#!/usr/bin/env python3
"""
Irrigation Tracking System for Hydrawise

Comprehensive tracking system for rain sensor status and scheduled run changes.
Integrates with existing automated collector with minimal modifications.

Features:
- Rain sensor status monitoring and history tracking
- Scheduled run status change detection 
- Email notifications for critical irrigation events
- Database integration with existing schema
- Rate-limited daily email summaries

Author: AI Assistant  
Date: 2025-08-26
"""

import os
import sys
import logging
import sqlite3
import subprocess
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.timezone_utils import get_houston_now, get_display_timestamp, get_database_timestamp
from utils.email_notifications import EmailNotificationManager, EmailConfig
from utils.status_change_detector import StatusChangeDetector
import sensor_detector

logger = logging.getLogger(__name__)

@dataclass
class TrackingConfig:
    """Configuration for irrigation tracking system"""
    # Email notification settings [[memory:7332534]]
    email_notifications_enabled: bool = False       # Enable email notifications (disabled by default)
    notification_recipients: List[str] = field(default_factory=list)  # Email recipients
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""                          # SMTP username
    smtp_password: str = ""                          # SMTP app password
    smtp_from_address: str = ""                      # From email address (defaults to username)
    
    # Notification types
    sensor_change_notifications: bool = True         # Rain sensor status change alerts
    status_change_notifications: bool = True         # Scheduled run status change alerts
    daily_summary_notifications: bool = True         # Daily summary if changes detected
    
    # Timing and limits
    daily_summary_time: str = "19:00"                # 7:00 PM Houston time for daily emails
    max_emails_per_day: int = 1                      # Maximum emails per day
    
    # Sensor and status tracking
    track_sensor_status: bool = True                 # Enable rain sensor tracking
    track_status_changes: bool = True                # Enable status change detection
    
    # Integration settings
    headless_mode: bool = True                       # Run browser in headless mode
    db_path: str = "database/irrigation_data.db"     # Database path

class IrrigationTrackingSystem:
    """
    Comprehensive irrigation tracking system that integrates with existing automated collector
    
    Provides:
    - Rain sensor status monitoring with change detection
    - Scheduled run status change detection and classification
    - Email notifications with rate limiting
    - Database integration for historical tracking
    """
    
    def __init__(self, config: TrackingConfig = None):
        """
        Initialize irrigation tracking system
        
        Args:
            config: Tracking configuration (uses defaults if None)
        """
        self.config = config or TrackingConfig()
        self.logger = logger
        
        # Initialize tracking components
        self.status_detector = StatusChangeDetector(self.config.db_path)
        
        # Initialize email notifications if enabled
        if self.config.email_notifications_enabled:
            email_config = EmailConfig(
                enabled=self.config.email_notifications_enabled,
                recipients=self.config.notification_recipients,
                smtp_server=self.config.smtp_server,
                smtp_port=self.config.smtp_port,
                username=self.config.smtp_username,
                password=self.config.smtp_password,
                from_address=self.config.smtp_from_address or self.config.smtp_username,
                max_emails_per_day=self.config.max_emails_per_day
            )
            self.email_manager = EmailNotificationManager(email_config, self.config.db_path)
            self.logger.info(f"   Email notifications: Enabled ({len(self.config.notification_recipients)} recipients)")
        else:
            self.email_manager = None
            self.logger.info("   Email notifications: Disabled")
        
        # Track last sensor status to detect changes
        self.last_sensor_status = None
        
        self.logger.info("IrrigationTrackingSystem initialized")
        if self.config.track_status_changes:
            self.logger.info("   Status change detection: Enabled")
        if self.config.track_sensor_status:
            self.logger.info("   Rain sensor tracking: Enabled")
        if self.config.email_notifications_enabled:
            self.logger.info(f"   Email notifications: Enabled ({len(self.config.notification_recipients)} recipients)")
        else:
            self.logger.info("   Email notifications: Disabled")
    
    def collect_sensor_status(self, collection_run_id: str = None) -> Dict[str, Any]:
        """
        Collect current rain sensor status from dashboard
        
        Args:
            collection_run_id: Identifier for the collection run
            
        Returns:
            Dictionary with sensor status information
        """
        if not self.config.track_sensor_status:
            return {'sensor_status': 'Tracking disabled', 'rain_sensor_active': False, 'irrigation_suspended': False}
        
        try:
            self.logger.info("[SENSOR] Collecting rain sensor status...")
            
            # Use the existing working HydrawiseWebScraper with sensor detection
            from hydrawise_web_scraper_refactored import HydrawiseWebScraper
            import os
            
            # Get credentials from environment
            username = os.getenv('HYDRAWISE_USER')
            password = os.getenv('HYDRAWISE_PASSWORD')
            
            if not username or not password:
                self.logger.error("[SENSOR ERROR] Missing Hydrawise credentials in environment")
                return {'sensor_status': 'Missing credentials', 'rain_sensor_active': False, 'irrigation_suspended': False}
            
            # Create scraper instance for sensor detection only
            scraper = HydrawiseWebScraper(username, password, headless=self.config.headless_mode)
            
            try:
                # Start browser and login
                scraper.start_browser()
                if not scraper.login():
                    raise Exception("Failed to login to Hydrawise portal")
                
                # Use the working sensor detection code
                sensor_info = scraper.check_rain_sensor_status()
                
                # Store sensor status in database
                self._store_sensor_status(sensor_info, collection_run_id)
                
                # Check for sensor status changes
                if self._check_sensor_status_change(sensor_info):
                    self.logger.warning(f"[SENSOR CHANGE] Rain sensor status changed: {sensor_info['sensor_status']}")
                
                self.logger.info(f"[SENSOR] Status collected: {sensor_info['sensor_status']}")
                return sensor_info
                
            finally:
                # Always cleanup browser
                try:
                    scraper.stop_browser()
                except:
                    pass
        except Exception as e:
            self.logger.error(f"[SENSOR ERROR] Error collecting sensor status: {e}")
            return {'sensor_status': f'Error: {e}', 'rain_sensor_active': False, 'irrigation_suspended': False}
    
    def process_scheduled_runs_with_tracking(self, target_date: date, collection_type: str = "unknown", sensor_info: Dict = None) -> Tuple[int, int]:
        """
        Process scheduled run collection with comprehensive status monitoring
        
        This method provides both change detection AND current status monitoring.
        
        Args:
            target_date: Date being collected
            collection_type: Type of collection run (daily, interval, startup)
            sensor_info: Pre-collected sensor information (to avoid redundant checks)
            
        Returns:
            Tuple of (total_runs_processed, status_changes_detected)
        """
        if not self.config.track_status_changes:
            return 0, 0
        
        try:
            self.logger.info(f"[COMPREHENSIVE] Analyzing status for {target_date}")
            
            # Get scheduled runs that were just collected for this date
            current_runs = self._get_recent_scheduled_runs(target_date)
            
            if not current_runs:
                self.logger.info(f"[COMPREHENSIVE] No scheduled runs found for {target_date}")
                return 0, 0
            
            # Use provided sensor info or collect if not provided
            # IMPORTANT: Only collect current sensor if not provided AND analyzing today's data
            # For historical dates, sensor_info should come from database (via _get_historical_sensor_status)
            if sensor_info is None and self.config.track_sensor_status:
                from utils.timezone_utils import get_houston_now
                today = get_houston_now().date()
                if target_date == today:
                    sensor_info = self.collect_sensor_status(collection_run_id)
                    self.logger.info("[SENSOR] Collected CURRENT sensor status for comprehensive analysis")
                else:
                    self.logger.warning(f"[SENSOR] No sensor info provided for historical date {target_date} - should use database")
            elif sensor_info:
                is_historical = sensor_info.get('historical', False)
                if is_historical:
                    self.logger.info(f"[SENSOR] Using HISTORICAL sensor status from database (sensor may be different now)")
                else:
                    self.logger.info(f"[SENSOR] Using CURRENT sensor status (avoiding redundant check)")
            
            # Run comprehensive analysis
            from utils.comprehensive_status_monitor import integrate_comprehensive_monitoring
            results = integrate_comprehensive_monitoring(
                self, target_date, collection_type, current_runs, sensor_info
            )
            
            # Log comprehensive results
            change_detection = results.get('change_detection', {})
            current_status = results.get('current_status', {})
            
            changes_detected = change_detection.get('changes_detected', 0)
            critical_alerts = current_status.get('critical_alerts', 0)
            
            if changes_detected > 0:
                self.logger.warning(f"[CHANGES] {changes_detected} status changes detected")
                for change_type, count in change_detection.get('changes_by_type', {}).items():
                    self.logger.warning(f"   {change_type}: {count}")
            
            if critical_alerts > 0:
                self.logger.error(f"[CRITICAL] {critical_alerts} critical irrigation alerts!")
                for alert in current_status.get('alerts', []):
                    if alert['severity'] == 'critical':
                        self.logger.error(f"   {alert['message']}")
            
            # Send email if needed
            if results.get('email_needed', False):
                if self.email_manager:
                    email_content = results.get('email_content')
                    if email_content:
                        self.logger.info(f"[EMAIL] Sending comprehensive email: {email_content['subject']}")
                        self._send_comprehensive_email(email_content, target_date)
                    else:
                        self.logger.warning("[EMAIL] Email needed but no content generated")
                else:
                    self.logger.warning("[EMAIL] Email needed but email manager not initialized")
            
            return len(current_runs), changes_detected
            
        except Exception as e:
            self.logger.error(f"[COMPREHENSIVE ERROR] Error in comprehensive monitoring: {e}")
            return 0, 0
    
    def send_daily_summary_if_needed(self, target_date: date) -> bool:
        """
        Send daily summary email if changes were detected and email hasn't been sent
        
        Args:
            target_date: Date to send summary for
            
        Returns:
            True if email was sent, False otherwise
        """
        if not self.email_manager:
            return False
        
        try:
            return self.email_manager.send_daily_status_email(target_date)
        except Exception as e:
            self.logger.error(f"[EMAIL ERROR] Error sending daily summary: {e}")
            return False
    
    def _get_historical_sensor_status(self, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Get historical sensor status for a specific date from database
        
        CRITICAL: Rain sensor can be enabled/disabled at different times.
        Current sensor reading is only valid RIGHT NOW.
        Any historical analysis MUST use previously recorded values.
        
        Args:
            target_date: Date to get sensor status for
            
        Returns:
            Dictionary with sensor status information, or None if not found
        """
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                # Get the most recent sensor status for the target date
                cursor.execute("""
                    SELECT sensor_status, is_stopping_irrigation, irrigation_suspended, 
                           sensor_text_raw, status_time
                    FROM rain_sensor_status_history 
                    WHERE status_date = ?
                    ORDER BY status_time DESC 
                    LIMIT 1
                """, (target_date.isoformat(),))
                
                record = cursor.fetchone()
                if record:
                    sensor_status, stopping, suspended, raw_text, status_time = record
                    return {
                        'sensor_status': sensor_status,
                        'rain_sensor_active': bool(stopping),
                        'irrigation_suspended': bool(suspended),
                        'sensor_text_raw': raw_text,
                        'status_time': status_time,
                        'historical': True  # Flag to indicate this is historical data
                    }
                
                return None
                
        except Exception as e:
            self.logger.error(f"Error retrieving historical sensor status for {target_date}: {e}")
            return None
    
    def _get_recent_scheduled_runs(self, target_date: date, hours_back: int = 24):
        """
        Get the most recent scheduled runs for the target date
        
        Args:
            target_date: Date to get runs for
            hours_back: How many hours back to look (default 24 for full day coverage)
            
        Returns:
            List of ScheduledRun objects for the target date
        """
        try:
            # Import ScheduledRun here to avoid circular imports
            from hydrawise_web_scraper_refactored import ScheduledRun
            
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                # Get ALL scheduled runs for the target date (no time window restriction)
                # This gives us the current state of all zones for this date
                cursor.execute("""
                    SELECT 
                        zone_id, zone_name, schedule_date, scheduled_start_time,
                        scheduled_duration_minutes, expected_gallons, program_name,
                        notes, raw_popup_text, popup_lines_json, parsed_summary,
                        is_rain_cancelled, rain_sensor_status, popup_status,
                        scraped_at
                    FROM scheduled_runs 
                    WHERE schedule_date = ?
                    ORDER BY zone_id, scheduled_start_time
                """, (target_date.isoformat(),))
                
                runs = []
                for row in cursor.fetchall():
                    # Create a ScheduledRun with the basic parameters it expects
                    run = ScheduledRun(
                        zone_id=str(row[0]),
                        zone_name=row[1],
                        start_time=datetime.fromisoformat(row[3]),
                        duration_minutes=row[4],
                        expected_gallons=row[5],
                        notes=row[7] or ""
                    )
                    
                    # Add additional attributes that aren't in the constructor
                    run.schedule_date = datetime.fromisoformat(row[2]).date()
                    run.program_name = row[6]
                    run.raw_popup_text = row[8]
                    run.popup_lines_json = row[9]
                    run.parsed_summary = row[10]
                    run.is_rain_cancelled = bool(row[11]) if row[11] is not None else False
                    run.rain_sensor_status = row[12]
                    run.popup_status = row[13]
                    
                    runs.append(run)
                
                return runs
                
        except Exception as e:
            self.logger.error(f"Error getting recent scheduled runs: {e}")
            return []
    
    def _store_sensor_status(self, sensor_info: Dict[str, Any], collection_run_id: str = None):
        """Store sensor status in database"""
        try:
            now = get_houston_now()
            
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR IGNORE INTO rain_sensor_status_history (
                        status_date, status_time, sensor_status, is_stopping_irrigation,
                        irrigation_suspended, sensor_text_raw, collection_run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    now.date().isoformat(),
                    now.isoformat(),
                    sensor_info['sensor_status'],
                    sensor_info['rain_sensor_active'],
                    sensor_info['irrigation_suspended'],
                    sensor_info['sensor_status'],  # Use sensor_status as raw text
                    collection_run_id
                ))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error storing sensor status: {e}")
    
    def _check_sensor_status_change(self, current_sensor_info: Dict[str, Any]) -> bool:
        """
        Check if sensor status has changed since last check
        
        Args:
            current_sensor_info: Current sensor status information
            
        Returns:
            True if status changed, False otherwise
        """
        try:
            # Get last sensor status from database
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT is_stopping_irrigation, irrigation_suspended 
                    FROM rain_sensor_status_history 
                    ORDER BY status_time DESC 
                    LIMIT 2
                """)
                
                results = cursor.fetchall()
                
                if len(results) >= 2:
                    # Compare current with previous
                    current_stopping = current_sensor_info['rain_sensor_active']
                    current_suspended = current_sensor_info['irrigation_suspended']
                    
                    prev_stopping = bool(results[1][0])
                    prev_suspended = bool(results[1][1])
                    
                    return (current_stopping != prev_stopping or 
                           current_suspended != prev_suspended)
                
                return False  # No previous status to compare
                
        except Exception as e:
            self.logger.error(f"Error checking sensor status change: {e}")
            return False
    
    def _send_daily_status_email(self, target_date: date):
        """Send daily status email in background thread to avoid blocking collection"""
        if not self.email_manager:
            return
        
        try:
            import threading
            
            def send_email():
                try:
                    success = self.email_manager.send_daily_status_email(target_date)
                    if success:
                        self.logger.info(f"[EMAIL] Daily status email sent for {target_date}")
                    else:
                        self.logger.warning(f"[EMAIL] Failed to send daily status email for {target_date}")
                except Exception as e:
                    self.logger.error(f"[EMAIL ERROR] Error in email thread: {e}")
            
            # Send email in background thread to not block collection
            # Use non-daemon thread with timeout to ensure completion
            email_thread = threading.Thread(target=send_email, daemon=False)
            email_thread.start()
            
            # Wait up to 15 seconds for email to send (ensures completion)
            email_thread.join(timeout=15)
            if email_thread.is_alive():
                self.logger.warning("[EMAIL] Daily email thread still running after 15 seconds, but continuing main process...")
            else:
                self.logger.debug("[EMAIL] Daily email thread completed successfully")
            
        except Exception as e:
            self.logger.error(f"[EMAIL ERROR] Error starting email thread: {e}")
    
    def _send_comprehensive_email(self, email_content: dict, target_date: date):
        """Send comprehensive status email with both changes and current alerts"""
        if not self.email_manager:
            return
        
        try:
            import threading
            
            def send_email():
                try:
                    success = self.email_manager._send_email(
                        subject=email_content['subject'],
                        body=email_content['body'],
                        notification_type='comprehensive_status',
                        target_date=target_date
                    )
                    if success:
                        self.logger.info(f"[EMAIL] Comprehensive status email sent for {target_date}")
                    else:
                        self.logger.warning(f"[EMAIL] Failed to send comprehensive status email for {target_date}")
                except Exception as e:
                    self.logger.error(f"[EMAIL ERROR] Error in comprehensive email thread: {e}")
            
            # Send email in background thread to not block collection
            # Use non-daemon thread with timeout to ensure completion
            email_thread = threading.Thread(target=send_email, daemon=False)
            email_thread.start()
            
            # Wait up to 15 seconds for email to send (ensures completion)
            email_thread.join(timeout=15)
            if email_thread.is_alive():
                self.logger.warning("[EMAIL] Comprehensive email thread still running after 15 seconds, but continuing main process...")
            else:
                self.logger.debug("[EMAIL] Comprehensive email thread completed successfully")
            
        except Exception as e:
            self.logger.error(f"[EMAIL ERROR] Error starting comprehensive email thread: {e}")
    
    def get_tracking_status(self) -> Dict[str, Any]:
        """
        Get current tracking system status
        
        Returns:
            Dictionary with tracking system status information
        """
        status = {
            "tracking_enabled": True,
            "sensor_tracking": self.config.track_sensor_status,
            "status_change_tracking": self.config.track_status_changes,
            "email_notifications": self.config.email_notifications_enabled,
            "email_recipients_count": len(self.config.notification_recipients),
            "database_path": self.config.db_path
        }
        
        # Get recent activity
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                # Get recent sensor status
                cursor.execute("""
                    SELECT status_time, sensor_status, is_stopping_irrigation 
                    FROM rain_sensor_status_history 
                    ORDER BY status_time DESC 
                    LIMIT 1
                """)
                
                sensor_result = cursor.fetchone()
                if sensor_result:
                    status["last_sensor_check"] = sensor_result[0]
                    status["current_sensor_status"] = sensor_result[1]
                    status["sensor_stopping_irrigation"] = bool(sensor_result[2])
                
                # Get recent status changes
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM scheduled_run_status_changes 
                    WHERE change_detected_date = ?
                """, (date.today().isoformat(),))
                
                status["today_status_changes"] = cursor.fetchone()[0]
                
        except Exception as e:
            self.logger.error(f"Error getting tracking status: {e}")
            status["error"] = str(e)
        
        return status


# Convenience functions for integration with existing automated collector

def create_default_tracking_system() -> IrrigationTrackingSystem:
    """Create tracking system with default configuration"""
    return IrrigationTrackingSystem()

def integrate_tracking_with_collection(tracking_system: IrrigationTrackingSystem, 
                                     target_date: date, 
                                     collection_type: str = "unknown") -> Dict[str, Any]:
    """
    Integrate tracking with existing collection process
    
    CRITICAL SENSOR LOGIC:
    - Rain sensor can be enabled/disabled at different times
    - Current sensor reading is ONLY valid RIGHT NOW
    - Historical analysis MUST use previously recorded database values
    - TODAY: Collect current sensor status via web scraping
    - PAST DATES: Query rain_sensor_status_history table for that date's data
    
    Args:
        tracking_system: Initialized tracking system
        target_date: Date being collected
        collection_type: Type of collection (startup, daily, interval)
        
    Returns:
        Dictionary with tracking results
    """
    collection_run_id = f"{collection_type}_{target_date.isoformat()}_{int(get_houston_now().timestamp())}"
    
    results = {
        "collection_run_id": collection_run_id,
        "sensor_status": {},
        "scheduled_runs_processed": 0,
        "status_changes_detected": 0,
        "email_sent": False
    }
    
    try:
        # Handle sensor status: current for today, historical from database for past dates
        # CRITICAL: Rain sensor can be enabled/disabled at different times.
        # Current reading is ONLY valid RIGHT NOW. Historical analysis MUST use recorded values.
        today = get_houston_now().date()
        sensor_info_for_analysis = None
        
        if tracking_system.config.track_sensor_status:
            if target_date == today:
                # Collect current sensor status for TODAY ONLY (valid right now)
                sensor_info_for_analysis = tracking_system.collect_sensor_status(collection_run_id)
                results["sensor_status"] = sensor_info_for_analysis
                tracking_system.logger.info(f"[SENSOR] Collected CURRENT sensor status for today ({target_date}) - valid RIGHT NOW")
            else:
                # MUST use historical data from database for ANY past date (sensor may have changed)
                sensor_info_for_analysis = tracking_system._get_historical_sensor_status(target_date)
                if sensor_info_for_analysis:
                    results["sensor_status"] = sensor_info_for_analysis
                    tracking_system.logger.info(f"[SENSOR] Retrieved HISTORICAL sensor status for {target_date} from database (sensor may be different now)")
                else:
                    tracking_system.logger.info(f"[SENSOR] No historical sensor data found for {target_date} in database")
        
        # Process scheduled runs for status changes (after they've been collected)
        if tracking_system.config.track_status_changes:
            # Pass the appropriate sensor info (current for today, historical for past dates)
            
            runs_processed, changes_detected = tracking_system.process_scheduled_runs_with_tracking(
                target_date, collection_type, sensor_info_for_analysis
            )
            results["scheduled_runs_processed"] = runs_processed
            results["status_changes_detected"] = changes_detected
        
        # REMOVED: Old daily email system - now using comprehensive monitoring only
        # The comprehensive monitoring system in process_scheduled_runs_with_tracking handles emails
        results["email_sent"] = False  # Daily email system disabled
        
    except Exception as e:
        logger.error(f"Error in tracking integration: {e}")
        results["error"] = str(e)
    
    return results
