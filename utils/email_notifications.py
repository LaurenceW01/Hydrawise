#!/usr/bin/env python3
"""
Email Notification System for Hydrawise Status Changes

Handles email notifications for rain sensor changes and scheduled run status changes.
Implements rate limiting to send maximum 1 email per day when changes are detected.

Author: AI Assistant
Date: 2025-08-26
"""

import smtplib
import ssl
import logging
import json
import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass

from utils.timezone_utils import get_houston_now, get_display_timestamp, get_database_timestamp

logger = logging.getLogger(__name__)

@dataclass
class EmailConfig:
    """Configuration for email notifications"""
    enabled: bool = True
    recipients: List[str] = None
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""
    max_emails_per_day: int = 1
    
    def __post_init__(self):
        """Initialize default recipients if None"""
        if self.recipients is None:
            self.recipients = []
        if not self.from_address and self.username:
            self.from_address = self.username

class EmailNotificationManager:
    """
    Manages email notifications for Hydrawise status changes
    
    Provides functionality for:
    - Daily status change summaries
    - Rain sensor change notifications  
    - Rate limiting to prevent email spam
    - Email delivery tracking and error handling
    """
    
    def __init__(self, config: EmailConfig, db_path: str = "database/irrigation_data.db"):
        """
        Initialize email notification manager
        
        Args:
            config: Email configuration settings
            db_path: Path to SQLite database
        """
        self.config = config
        self.db_path = db_path
        self.logger = logger
        
        # Validate configuration
        if self.config.enabled:
            self._validate_config()
    
    def _validate_config(self):
        """Validate email configuration"""
        if not self.config.recipients:
            self.logger.warning("Email notifications enabled but no recipients configured")
        if not self.config.username or not self.config.password:
            self.logger.warning("Email notifications enabled but SMTP credentials not configured")
        if not self.config.from_address:
            self.logger.warning("Email notifications enabled but from_address not configured")
    
    def should_send_daily_email(self, target_date: date) -> bool:
        """
        Check if daily email should be sent - FIXED to only send for actual changes
        
        Args:
            target_date: Date to check for email eligibility
            
        Returns:
            True if email should be sent (ACTUAL changes detected and not already sent)
        """
        if not self.config.enabled:
            return False
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if email already sent today
                cursor.execute("""
                    SELECT email_notification_sent 
                    FROM daily_status_summary 
                    WHERE summary_date = ?
                """, (target_date.isoformat(),))
                
                result = cursor.fetchone()
                if result and result[0]:  # email_notification_sent = True
                    self.logger.debug(f"Daily email already sent for {target_date}")
                    return False
                
                # CRITICAL FIX: Only check for ACTUAL status changes, not just any records
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM scheduled_run_status_changes 
                    WHERE change_detected_date = ?
                """, (target_date.isoformat(),))
                
                changes_count = cursor.fetchone()[0]
                
                # CRITICAL FIX: Check if rain sensor status ACTUALLY CHANGED today
                # Don't just count records - check if status is different from yesterday
                cursor.execute("""
                    SELECT COUNT(DISTINCT is_stopping_irrigation) 
                    FROM rain_sensor_status_history 
                    WHERE status_date = ?
                """, (target_date.isoformat(),))
                
                sensor_status_variations = cursor.fetchone()[0]
                sensor_actually_changed = sensor_status_variations > 1  # Changed if we see both True and False
                
                # CRITICAL FIX: Disable daily email system entirely
                # The comprehensive monitoring system handles all emails now
                self.logger.info(f"[DAILY EMAIL] Disabled - using comprehensive monitoring system instead")
                self.logger.debug(f"Email eligibility for {target_date}: {changes_count} status changes, sensor_changed: {sensor_actually_changed}, but daily emails disabled")
                
                return False  # Always return False - comprehensive system handles emails
                
        except Exception as e:
            self.logger.error(f"Error checking daily email eligibility: {e}")
            return False
    
    def get_daily_status_changes(self, target_date: date) -> Dict[str, Any]:
        """
        Get all status changes for a specific date
        
        Args:
            target_date: Date to get changes for
            
        Returns:
            Dictionary with categorized status changes
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all status changes for the date
                cursor.execute("""
                    SELECT 
                        zone_name, change_type, current_scheduled_start_time,
                        expected_gallons_lost, current_popup_text, previous_popup_text,
                        change_detected_time
                    FROM scheduled_run_status_changes 
                    WHERE change_detected_date = ?
                    ORDER BY change_detected_time
                """, (target_date.isoformat(),))
                
                changes = cursor.fetchall()
                
                # Get rain sensor changes for the date
                cursor.execute("""
                    SELECT 
                        status_time, sensor_status, is_stopping_irrigation,
                        irrigation_suspended, sensor_text_raw
                    FROM rain_sensor_status_history 
                    WHERE status_date = ?
                    ORDER BY status_time
                """, (target_date.isoformat(),))
                
                sensor_changes = cursor.fetchall()
                
                # Categorize status changes
                categorized = {
                    'rainfall_aborts': [],
                    'sensor_aborts': [],
                    'user_suspensions': [],
                    'normal_restorations': [],
                    'other_changes': [],
                    'sensor_changes': [],
                    'total_gallons_lost': 0,
                    'zones_affected': set(),
                    'detection_count': len(changes)
                }
                
                for change in changes:
                    zone_name, change_type, start_time, gallons_lost, current_popup, previous_popup, detected_time = change
                    
                    change_data = {
                        'zone_name': zone_name,
                        'scheduled_start_time': datetime.fromisoformat(start_time) if start_time else None,
                        'expected_gallons_lost': gallons_lost or 0,
                        'current_popup': current_popup,
                        'previous_popup': previous_popup,
                        'detected_time': datetime.fromisoformat(detected_time) if detected_time else None
                    }
                    
                    categorized[f'{change_type}s'].append(change_data)
                    categorized['total_gallons_lost'] += (gallons_lost or 0)
                    categorized['zones_affected'].add(zone_name)
                
                # Process sensor changes (deduplicate by status to avoid repeating same message)
                last_sensor_status = None
                for sensor_change in sensor_changes:
                    status_time, sensor_status, stopping, suspended, raw_text = sensor_change
                    
                    # Only add if different from last status to avoid duplicates
                    current_stopping = bool(stopping)
                    if last_sensor_status != current_stopping:
                        categorized['sensor_changes'].append({
                            'status_time': datetime.fromisoformat(status_time) if status_time else None,
                            'sensor_status': sensor_status,
                            'is_stopping_irrigation': current_stopping,
                            'irrigation_suspended': bool(suspended),
                            'raw_text': raw_text
                        })
                        last_sensor_status = current_stopping
                
                categorized['zones_affected'] = list(categorized['zones_affected'])
                
                return categorized
                
        except Exception as e:
            self.logger.error(f"Error getting daily status changes: {e}")
            return {
                'rainfall_aborts': [], 'sensor_aborts': [], 'user_suspensions': [],
                'normal_restorations': [], 'other_changes': [], 'sensor_changes': [],
                'total_gallons_lost': 0, 'zones_affected': [], 'detection_count': 0
            }
    
    def generate_daily_email_content(self, changes: Dict[str, Any], target_date: date) -> Dict[str, str]:
        """
        Generate email subject and body for daily status changes
        
        Args:
            changes: Dictionary of categorized status changes
            target_date: Date the changes occurred
            
        Returns:
            Dictionary with 'subject' and 'body' keys
        """
        zones_affected_count = len(changes['zones_affected'])
        total_changes = changes['detection_count']
        
        # Generate subject
        if zones_affected_count > 0:
            subject = f"Hydrawise Alert - {zones_affected_count} zones affected by irrigation changes"
        else:
            subject = f"Hydrawise Status Update - {target_date.strftime('%B %d, %Y')}"
        
        # Generate body
        body = f"""Hydrawise Status Changes - {target_date.strftime('%B %d, %Y')}

STATUS CHANGES DETECTED:
"""
        
        # Rainfall aborts
        if changes['rainfall_aborts']:
            body += f"""
🌧️ HIGH RAINFALL ABORTS ({len(changes['rainfall_aborts'])} zones):
"""
            for change in changes['rainfall_aborts']:
                start_time_str = change['scheduled_start_time'].strftime('%I:%M %p') if change['scheduled_start_time'] else 'Unknown time'
                body += f"- {change['zone_name']}: {start_time_str} ({change['expected_gallons_lost']:.1f} gallons prevented)\n"
                body += f"  Status: \"Aborted due to high daily rainfall\"\n"
        
        # Sensor aborts
        if changes['sensor_aborts']:
            body += f"""
🔧 SENSOR INPUT ABORTS ({len(changes['sensor_aborts'])} zones):
"""
            for change in changes['sensor_aborts']:
                start_time_str = change['scheduled_start_time'].strftime('%I:%M %p') if change['scheduled_start_time'] else 'Unknown time'
                body += f"- {change['zone_name']}: {start_time_str} ({change['expected_gallons_lost']:.1f} gallons prevented)\n"
                body += f"  Status: \"Aborted due to sensor input\"\n"
        
        # User suspensions
        if changes['user_suspensions']:
            body += f"""
⏸️ USER SUSPENSIONS ({len(changes['user_suspensions'])} zones):
"""
            for change in changes['user_suspensions']:
                start_time_str = change['scheduled_start_time'].strftime('%I:%M %p') if change['scheduled_start_time'] else 'Unknown time'
                body += f"- {change['zone_name']}: {start_time_str} ({change['expected_gallons_lost']:.1f} gallons prevented)\n"
                body += f"  Status: \"Water cycle suspended\"\n"
        
        # Normal restorations
        if changes['normal_restorations']:
            body += f"""
✅ NORMAL OPERATION RESTORED ({len(changes['normal_restorations'])} zones):
"""
            for change in changes['normal_restorations']:
                body += f"- {change['zone_name']}: Back to normal watering cycle\n"
        
        # Rain sensor changes
        if changes['sensor_changes']:
            body += f"""
🌦️ RAIN SENSOR ACTIVITY:
"""
            for sensor_change in changes['sensor_changes']:
                time_str = sensor_change['status_time'].strftime('%I:%M %p') if sensor_change['status_time'] else 'Unknown time'
                status = "STOPPING irrigation" if sensor_change['is_stopping_irrigation'] else "NOT stopping irrigation"
                body += f"- {time_str}: Sensor is {status}\n"
        
        # Summary with improved logic for sensor status
        total_zones_affected = zones_affected_count
        
        # If sensor is stopping irrigation, ALL zones are affected regardless of specific zone changes
        sensor_stopping = any(change['is_stopping_irrigation'] for change in changes.get('sensor_changes', []))
        if sensor_stopping:
            total_zones_affected = "ALL ZONES"
            water_impact_note = " (sensor stopping all irrigation)"
        else:
            water_impact_note = ""
        
        body += f"""
SUMMARY:
- Total zones affected: {total_zones_affected}
- Total water prevented: {changes['total_gallons_lost']:.1f} gallons{water_impact_note}
- Total changes detected: {total_changes}
- Detection date: {target_date.strftime('%B %d, %Y')}
- Report generated: {get_display_timestamp(get_houston_now())}

This is an automated notification sent once daily when changes are detected.
Next collection: {(target_date + timedelta(days=1)).strftime('%B %d')} 6:00 AM Houston time.
"""
        
        return {'subject': subject, 'body': body}
    
    def send_daily_status_email(self, target_date: date) -> bool:
        """
        Send daily status change email if changes detected and not already sent
        
        Args:
            target_date: Date to send status email for
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.should_send_daily_email(target_date):
            return False
        
        try:
            # Get status changes for the date
            changes = self.get_daily_status_changes(target_date)
            
            if changes['detection_count'] == 0 and len(changes['sensor_changes']) == 0:
                self.logger.info(f"No status changes to report for {target_date}")
                return False
            
            # Generate email content
            email_content = self.generate_daily_email_content(changes, target_date)
            
            # Send email
            success = self._send_email(
                subject=email_content['subject'],
                body=email_content['body'],
                notification_type='daily_summary',
                affected_zones=changes['zones_affected'],
                target_date=target_date
            )
            
            if success:
                # Mark email as sent in daily summary
                self._mark_daily_email_sent(target_date, changes)
                self.logger.info(f"Daily status email sent successfully for {target_date}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending daily status email: {e}")
            return False
    
    def _send_email(self, subject: str, body: str, notification_type: str, 
                   affected_zones: List[str] = None, target_date: date = None) -> bool:
        """
        Send email using SMTP configuration
        
        Args:
            subject: Email subject
            body: Email body
            notification_type: Type of notification
            affected_zones: List of affected zone names
            target_date: Date for the notification
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.config.enabled or not self.config.recipients:
            self.logger.debug("Email notifications disabled or no recipients configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.config.from_address
            msg['To'] = ', '.join(self.config.recipients)
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.username, self.config.password)
                server.send_message(msg)
            
            # Log successful email
            self._log_email_notification(
                notification_date=target_date or date.today(),
                notification_type=notification_type,
                subject=subject,
                body_preview=body[:200],
                affected_zones=affected_zones or [],
                email_sent=True,
                sent_at=get_houston_now()
            )
            
            self.logger.info(f"Email sent successfully to {len(self.config.recipients)} recipients")
            return True
            
        except Exception as e:
            # Log failed email
            self._log_email_notification(
                notification_date=target_date or date.today(),
                notification_type=notification_type,
                subject=subject,
                body_preview=body[:200],
                affected_zones=affected_zones or [],
                email_sent=False,
                error_message=str(e)
            )
            
            self.logger.error(f"Failed to send email: {e}")
            return False
    
    def _mark_daily_email_sent(self, target_date: date, changes: Dict[str, Any]):
        """Mark daily email as sent in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert or update daily status summary
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_status_summary (
                        summary_date, rainfall_aborts_count, sensor_aborts_count,
                        user_suspensions_count, normal_restorations_count, total_changes_count,
                        zones_affected_count, total_gallons_lost, email_notification_sent,
                        email_sent_at, email_recipients, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_date.isoformat(),
                    len(changes['rainfall_aborts']),
                    len(changes['sensor_aborts']),
                    len(changes['user_suspensions']),
                    len(changes['normal_restorations']),
                    changes['detection_count'],
                    len(changes['zones_affected']),
                    changes['total_gallons_lost'],
                    True,  # email_notification_sent
                    get_database_timestamp(),  # email_sent_at
                    json.dumps(self.config.recipients),  # email_recipients
                    get_database_timestamp()  # last_updated
                ))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error marking daily email as sent: {e}")
    
    def _log_email_notification(self, notification_date: date, notification_type: str,
                               subject: str, body_preview: str, affected_zones: List[str],
                               email_sent: bool, sent_at: datetime = None, error_message: str = None):
        """Log email notification attempt to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO email_notifications_log (
                        notification_date, notification_type, trigger_event, recipients,
                        subject, body_preview, affected_zones, runs_affected_count,
                        email_sent, sent_at, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    notification_date.isoformat(),
                    notification_type,
                    f"Status changes detected for {notification_date}",
                    json.dumps(self.config.recipients),
                    subject,
                    body_preview,
                    json.dumps(affected_zones),
                    len(affected_zones),
                    email_sent,
                    sent_at.isoformat() if sent_at else None,
                    error_message
                ))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error logging email notification: {e}")
