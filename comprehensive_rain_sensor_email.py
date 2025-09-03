#!/usr/bin/env python3
"""
Comprehensive Rain Sensor Status Change Email Generator

Uses the existing comprehensive monitoring system to generate a complete email
that includes:
1. Actual status changes from scheduled_run_status_changes table
2. Current status of ALL zones, including those still affected by high rainfall
3. Proper comprehensive summary with accurate zone counts

This script simulates the email that would have been sent by the system
when the rain sensor status changed, providing complete information about
which zones are actually running vs. which remain turned off.

Author: AI Assistant
Date: 2025-09-02
"""

import sqlite3
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
import os
from dataclasses import dataclass

# Add the project root to the Python path for imports
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.timezone_utils import get_houston_now
from utils.email_notifications import EmailNotificationManager, EmailConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ZoneStatusSummary:
    """Summary of zone status for comprehensive reporting"""
    zone_name: str
    zone_id: int
    current_status: str
    expected_gallons: float
    abort_reason: Optional[str] = None
    is_running_normally: bool = False

class ComprehensiveEmailGenerator:
    """Generate comprehensive email using actual database data and monitoring system"""
    
    def __init__(self, db_path: str = "database/irrigation_data.db"):
        """Initialize with database path"""
        self.db_path = db_path
        self.logger = logger
        
    def get_recent_status_changes(self, target_date: date = None) -> List[Dict[str, Any]]:
        """Get recent status changes from the scheduled_run_status_changes table"""
        if target_date is None:
            target_date = get_houston_now().date()
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all status changes for the target date
                cursor.execute("""
                    SELECT 
                        zone_id, zone_name, change_detected_time,
                        current_status_type, current_popup_text,
                        previous_status_type, previous_popup_text,
                        change_type, expected_gallons_lost,
                        time_since_last_record_hours
                    FROM scheduled_run_status_changes 
                    WHERE change_detected_date = ?
                    ORDER BY change_detected_time DESC
                """, (target_date.isoformat(),))
                
                changes = []
                for row in cursor.fetchall():
                    zone_id, zone_name, detected_time, current_status, current_popup, \
                    previous_status, previous_popup, change_type, gallons_lost, hours_since = row
                    
                    changes.append({
                        'zone_id': zone_id,
                        'zone_name': zone_name,
                        'detected_time': datetime.fromisoformat(detected_time) if detected_time else None,
                        'current_status_type': current_status,
                        'current_popup_text': current_popup,
                        'previous_status_type': previous_status,
                        'previous_popup_text': previous_popup,
                        'change_type': change_type,
                        'expected_gallons_lost': gallons_lost or 0,
                        'time_since_last_record_hours': hours_since
                    })
                
                return changes
                
        except Exception as e:
            self.logger.error(f"Error getting recent status changes: {e}")
            return []
    
    def get_current_zone_status(self, target_date: date = None) -> List[ZoneStatusSummary]:
        """Get current status of all zones from scheduled_runs table"""
        if target_date is None:
            target_date = get_houston_now().date()
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get the most recent scheduled runs for each zone for the target date
                cursor.execute("""
                    SELECT 
                        sr.zone_id, sr.zone_name, sr.raw_popup_text, 
                        sr.expected_gallons, sr.scheduled_start_time,
                        sr.popup_status, sr.is_rain_cancelled
                    FROM scheduled_runs sr
                    WHERE sr.schedule_date = ?
                    AND sr.scraped_at = (
                        SELECT MAX(scraped_at) 
                        FROM scheduled_runs sr2 
                        WHERE sr2.zone_id = sr.zone_id 
                        AND sr2.schedule_date = sr.schedule_date
                    )
                    ORDER BY sr.zone_name, sr.scheduled_start_time
                """, (target_date.isoformat(),))
                
                zone_summaries = []
                processed_zones = set()
                
                for row in cursor.fetchall():
                    zone_id, zone_name, popup_text, expected_gallons, start_time, popup_status, is_rain_cancelled = row
                    
                    # Avoid duplicate zones (take first occurrence for each zone)
                    if zone_id not in processed_zones:
                        processed_zones.add(zone_id)
                        
                        # Classify current status
                        current_status = self._classify_zone_status(popup_text)
                        is_running_normally = current_status == 'normal_cycle'
                        abort_reason = self._extract_abort_reason(popup_text) if not is_running_normally else None
                        
                        zone_summaries.append(ZoneStatusSummary(
                            zone_name=zone_name,
                            zone_id=zone_id,
                            current_status=current_status,
                            expected_gallons=expected_gallons or 0,
                            abort_reason=abort_reason,
                            is_running_normally=is_running_normally
                        ))
                
                return zone_summaries
                
        except Exception as e:
            self.logger.error(f"Error getting current zone status: {e}")
            return []
    
    def _classify_zone_status(self, popup_text: str) -> str:
        """Classify zone status based on popup text"""
        if not popup_text:
            return "unknown"
        
        popup_lower = popup_text.lower()
        
        if "aborted due to high daily rainfall" in popup_lower:
            return "rainfall_abort"
        elif "aborted due to sensor input" in popup_lower:
            return "sensor_abort"
        elif "water cycle suspended" in popup_lower:
            return "user_suspended"
        elif "not scheduled to run" in popup_lower:
            return "not_scheduled"
        elif "normal watering cycle" in popup_lower:
            return "normal_cycle"
        else:
            return "other"
    
    def _extract_abort_reason(self, popup_text: str) -> str:
        """Extract specific abort reason from popup text"""
        if not popup_text:
            return "Unknown"
        
        popup_lower = popup_text.lower()
        
        if "aborted due to high daily rainfall" in popup_lower:
            return "High daily rainfall"
        elif "aborted due to sensor input" in popup_lower:
            return "Sensor input"
        elif "water cycle suspended" in popup_lower:
            return "User suspended"
        elif "not scheduled to run" in popup_lower:
            return "Not scheduled"
        else:
            return "Other"
    
    def generate_comprehensive_email_content(self, target_date: date = None) -> Dict[str, str]:
        """Generate comprehensive email content using actual database data"""
        if target_date is None:
            target_date = get_houston_now().date()
            
        current_time = get_houston_now()
        
        # Get recent status changes
        recent_changes = self.get_recent_status_changes(target_date)
        
        # Get current status of all zones
        all_zones = self.get_current_zone_status(target_date)
        
        # Categorize zones by current status
        normal_zones = [z for z in all_zones if z.is_running_normally]
        rainfall_aborted = [z for z in all_zones if z.current_status == 'rainfall_abort']
        sensor_aborted = [z for z in all_zones if z.current_status == 'sensor_abort']
        user_suspended = [z for z in all_zones if z.current_status == 'user_suspended']
        not_scheduled = [z for z in all_zones if z.current_status == 'not_scheduled']
        other_status = [z for z in all_zones if z.current_status not in ['normal_cycle', 'rainfall_abort', 'sensor_abort', 'user_suspended', 'not_scheduled']]
        
        # Categorize recent changes
        changes_by_type = {}
        for change in recent_changes:
            change_type = change['change_type']
            if change_type not in changes_by_type:
                changes_by_type[change_type] = []
            changes_by_type[change_type].append(change)
        
        # Generate subject - use unique zones count for changes
        total_normal = len(normal_zones)
        total_affected = len(all_zones) - total_normal
        
        if recent_changes:
            # Count unique zones that changed (not individual run changes)
            unique_changed_zones = len(set(change['zone_name'] for change in recent_changes))
            subject = f"Hydrawise Status Update - {unique_changed_zones} zones changed, {total_normal} running normally"
        else:
            subject = f"Hydrawise Status Report - {total_normal} zones running normally, {total_affected} zones affected"
        
        # Generate comprehensive email body
        body = f"""HYDRAWISE IRRIGATION STATUS REPORT
{'=' * 45}

Report Date: {target_date.strftime('%A, %B %d, %Y')}
Generated: {current_time.strftime('%I:%M %p')} Houston Time

"""
        
        # RECENT STATUS CHANGES SECTION - Summarized by unique zones
        if recent_changes:
            # Group changes by zone to eliminate duplicates
            zones_with_changes = {}
            for change in recent_changes:
                zone_name = change['zone_name']
                if zone_name not in zones_with_changes:
                    zones_with_changes[zone_name] = []
                zones_with_changes[zone_name].append(change)
            
            # Count unique zones by change type
            unique_zones_by_type = {}
            for zone_name, zone_changes in zones_with_changes.items():
                # Get the most recent change for this zone
                latest_change = max(zone_changes, key=lambda x: x['detected_time'] if x['detected_time'] else datetime.min)
                change_type = latest_change['change_type']
                if change_type not in unique_zones_by_type:
                    unique_zones_by_type[change_type] = []
                unique_zones_by_type[change_type].append((zone_name, latest_change))
            
            body += f"""STATUS CHANGES SUMMARY:
{'=' * 25}

{len(zones_with_changes)} zones had status changes on {target_date.strftime('%B %d, %Y')}:

"""
            
            # Show unique zone changes by type
            for change_type, zone_changes in unique_zones_by_type.items():
                if change_type == 'normal_restored':
                    icon = "✅"
                    type_name = "ZONES RESTORED TO NORMAL OPERATION"
                elif change_type == 'rainfall_abort':
                    icon = "🌧️"
                    type_name = "ZONES STOPPED DUE TO HIGH RAINFALL"
                elif change_type == 'sensor_abort':
                    icon = "🔧"
                    type_name = "ZONES STOPPED DUE TO SENSOR INPUT"
                elif change_type == 'user_suspended':
                    icon = "⏸️"
                    type_name = "ZONES MANUALLY SUSPENDED"
                else:
                    icon = "📝"
                    type_name = f"OTHER CHANGES ({change_type.upper()})"
                
                body += f"{icon} {type_name}: {len(zone_changes)} zones\n"
                
                # List zones concisely
                zone_names = [zone_name for zone_name, _ in zone_changes]
                if len(zone_names) <= 6:
                    body += f"   {', '.join(zone_names)}\n"
                else:
                    body += f"   {', '.join(zone_names[:4])}, and {len(zone_names)-4} more\n"
                body += "\n"
        else:
            body += f"""STATUS CHANGES:
{'=' * 15}

No status changes detected on {target_date.strftime('%B %d, %Y')}.

"""
        
        # CURRENT SYSTEM STATUS SECTION
        body += f"""CURRENT SYSTEM STATUS:
{'=' * 25}

"""
        
        # Show status summary first
        body += f"Total Zones: {len(all_zones)}\n"
        body += f"• Running Normally: {len(normal_zones)} zones\n"
        body += f"• Affected by Conditions: {total_affected} zones\n\n"
        
        # Normal zones - concise list
        if normal_zones:
            zone_names = [z.zone_name for z in normal_zones]
            body += f"✅ ZONES RUNNING NORMALLY ({len(normal_zones)} zones):\n"
            body += f"   {', '.join(zone_names)}\n\n"
        
        # Affected zones - grouped by reason, concise lists
        affected_groups = []
        
        if rainfall_aborted:
            zone_names = [z.zone_name for z in rainfall_aborted]
            affected_groups.append((f"🌧️ HIGH RAINFALL", len(rainfall_aborted), zone_names))
        
        if sensor_aborted:
            zone_names = [z.zone_name for z in sensor_aborted]
            affected_groups.append((f"🔧 SENSOR INPUT", len(sensor_aborted), zone_names))
        
        if user_suspended:
            zone_names = [z.zone_name for z in user_suspended]
            affected_groups.append((f"⏸️ USER SUSPENDED", len(user_suspended), zone_names))
        
        if not_scheduled:
            zone_names = [z.zone_name for z in not_scheduled]
            affected_groups.append((f"📅 NOT SCHEDULED", len(not_scheduled), zone_names))
        
        if other_status:
            zone_names = [z.zone_name for z in other_status]
            affected_groups.append((f"❓ OTHER STATUS", len(other_status), zone_names))
        
        # Display affected zones concisely
        if affected_groups:
            body += f"ZONES NOT RUNNING ({total_affected} zones):\n"
            for icon_reason, count, zone_names in affected_groups:
                if len(zone_names) <= 4:
                    body += f"• {icon_reason}: {', '.join(zone_names)}\n"
                else:
                    body += f"• {icon_reason}: {', '.join(zone_names[:3])}, and {len(zone_names)-3} more\n"
            body += "\n"
        
        # SUMMARY SECTION
        body += f"""SUMMARY:
{'=' * 10}

"""
        
        # Key status summary
        if recent_changes:
            unique_changed_zones = len(set(change['zone_name'] for change in recent_changes))
            body += f"• {unique_changed_zones} zones had status changes today\n"
        
        body += f"• {len(normal_zones)} zones running normally ({len(normal_zones)/len(all_zones)*100:.0f}% of total)\n"
        body += f"• {total_affected} zones affected by conditions ({total_affected/len(all_zones)*100:.0f}% of total)\n"
        
        # Key insight if most zones are affected
        if total_affected > len(normal_zones):
            body += f"\nKEY INSIGHT: Most zones ({total_affected}/{len(all_zones)}) are currently not running due to environmental conditions.\n"
        
        body += f"""
Generated: {current_time.strftime('%Y-%m-%d %H:%M:%S')} Houston Time
System: Hydrawise Status Monitor
"""
        
        return {
            'subject': subject,
            'body': body
        }
    
    def _format_status_for_display(self, status_type: str) -> str:
        """Format status type for human-readable display"""
        status_map = {
            'normal_cycle': 'Normal watering cycle',
            'rainfall_abort': 'Aborted due to high daily rainfall',
            'sensor_abort': 'Aborted due to sensor input',
            'user_suspended': 'Water cycle suspended',
            'not_scheduled': 'Not scheduled to run',
            'other': 'Other status'
        }
        return status_map.get(status_type, status_type)

def send_comprehensive_email(email_content: Dict[str, str]):
    """Send the comprehensive email using the existing email system"""
    try:
        # Load email configuration from environment
        from dotenv import load_dotenv
        load_dotenv()
        
        email_config = EmailConfig(
            enabled=True,
            recipients=[os.getenv('EMAIL_TO', '')],
            smtp_server=os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com'),
            smtp_port=int(os.getenv('EMAIL_SMTP_PORT', '587')),
            username=os.getenv('EMAIL_USERNAME', ''),
            password=os.getenv('EMAIL_PASSWORD', ''),
            from_address=os.getenv('EMAIL_FROM', '')
        )
        
        if not email_config.recipients[0]:
            print("❌ Email configuration incomplete - EMAIL_TO not set")
            return False
        
        # Create email manager
        email_manager = EmailNotificationManager(email_config, "database/irrigation_data.db")
        
        # Send email in a separate thread (non-daemon to ensure delivery)
        import threading
        
        def send_email():
            try:
                success = email_manager._send_email(
                    email_content['subject'], 
                    email_content['body'], 
                    email_config.recipients
                )
                if success:
                    print("✅ Comprehensive status email sent successfully!")
                else:
                    print("❌ Failed to send comprehensive status email")
            except Exception as e:
                print(f"❌ Error sending email: {e}")
        
        email_thread = threading.Thread(target=send_email, daemon=False)
        email_thread.start()
        
        # Wait for email to complete
        email_thread.join(timeout=15)
        if email_thread.is_alive():
            print("⚠️ Email thread still running after 15 seconds, but continuing...")
        else:
            print("✅ Email thread completed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up email: {e}")
        return False

def main():
    """Main function to generate and send comprehensive rain sensor status email"""
    print("🔍 Generating Comprehensive Rain Sensor Status Change Email...")
    print("=" * 60)
    
    # Initialize email generator
    generator = ComprehensiveEmailGenerator()
    
    # Use today's date (or specify a different date if needed)
    target_date = get_houston_now().date()
    print(f"📅 Analyzing irrigation status for: {target_date.strftime('%A, %B %d, %Y')}")
    
    # Generate comprehensive email content
    email_content = generator.generate_comprehensive_email_content(target_date)
    
    # Display email preview
    print("\n📧 Email Content Preview:")
    print("-" * 30)
    print(f"Subject: {email_content['subject']}")
    print(f"Body Length: {len(email_content['body'])} characters")
    print("-" * 30)
    print()
    
    # Show first part of body for preview
    body_lines = email_content['body'].split('\n')
    preview_lines = body_lines[:50]  # Show first 50 lines
    print('\n'.join(preview_lines))
    
    if len(body_lines) > 50:
        print(f"\n... ({len(body_lines) - 50} more lines in full email)")
    
    print("\n" + "=" * 60)
    
    # Ask if user wants to send the email
    while True:
        choice = input("📤 Send this comprehensive email? (y/n/f for full preview): ").lower().strip()
        if choice == 'y':
            print("\n📤 Sending comprehensive email...")
            success = send_comprehensive_email(email_content)
            break
        elif choice == 'n':
            print("📝 Email generated but not sent.")
            break
        elif choice == 'f':
            print("\n" + "=" * 60)
            print("FULL EMAIL CONTENT:")
            print("=" * 60)
            print(f"Subject: {email_content['subject']}\n")
            print(email_content['body'])
            print("=" * 60)
        else:
            print("Please enter 'y' for yes, 'n' for no, or 'f' for full preview.")

if __name__ == "__main__":
    main()
