#!/usr/bin/env python3
"""
Comprehensive Status Monitor for Hydrawise

Provides both change detection AND current status monitoring:
1. Tracks changes over time for historical analysis
2. Reports current critical status regardless of recent changes
3. Sends appropriate alerts based on both change and current state

Author: AI Assistant
Date: 2025-08-31
"""

import logging
import sqlite3
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from utils.timezone_utils import get_houston_now, get_database_timestamp

logger = logging.getLogger(__name__)

@dataclass
class CurrentStatusAlert:
    """Represents a current status that needs immediate attention"""
    alert_type: str  # 'sensor_active', 'zones_aborted', 'zones_suspended'
    severity: str    # 'critical', 'warning', 'info'
    message: str
    affected_zones: List[str]
    expected_gallons_lost: float
    sensor_status: str = ""
    
@dataclass
class ChangeDetectionResult:
    """Results from change detection analysis"""
    changes_detected: int
    changes_by_type: Dict[str, int]
    affected_zones: List[str]
    total_gallons_lost: float
    requires_immediate_alert: bool

class ComprehensiveStatusMonitor:
    """
    Monitors both status changes AND current critical conditions
    
    Provides:
    - Historical change tracking for analysis
    - Current status alerts for immediate action
    - Intelligent alerting that combines both perspectives
    """
    
    def __init__(self, db_path: str = "database/irrigation_data.db"):
        self.db_path = db_path
        self.logger = logger
    
    def analyze_comprehensive_status(self, target_date: date, 
                                   current_runs: List = None,
                                   sensor_info: Dict = None) -> Tuple[ChangeDetectionResult, List[CurrentStatusAlert]]:
        """
        Perform comprehensive status analysis
        
        Args:
            target_date: Date being analyzed
            current_runs: Current scheduled runs from collection
            sensor_info: Current sensor status information
            
        Returns:
            Tuple of (change_detection_results, current_status_alerts)
        """
        # 1. Run change detection analysis
        change_results = self._analyze_status_changes(target_date, current_runs, collection_run_id=None)
        
        # 2. Analyze current critical status
        current_alerts = self._analyze_current_status(target_date, current_runs, sensor_info)
        
        # 3. Log comprehensive findings
        self._log_comprehensive_findings(change_results, current_alerts, target_date)
        
        return change_results, current_alerts
    
    def _analyze_status_changes(self, target_date: date, current_runs: List = None, collection_run_id: str = None) -> ChangeDetectionResult:
        """Analyze status changes from historical perspective"""
        try:
            if not current_runs:
                return ChangeDetectionResult(
                    changes_detected=0, changes_by_type={}, affected_zones=[],
                    total_gallons_lost=0, requires_immediate_alert=False
                )
            
            # Use existing change detection logic
            from utils.status_change_detector import StatusChangeDetector
            detector = StatusChangeDetector(self.db_path)
            
            status_changes = detector.detect_changes_for_collection(current_runs, target_date)
            
            # CRITICAL: Store the detected changes in the database
            if status_changes:
                self.logger.info(f"[CHANGE DETECTION] Storing {len(status_changes)} status changes in database")
                success = detector.store_status_changes(status_changes, collection_run_id)
                if success:
                    self.logger.info(f"[CHANGE DETECTION] Successfully stored status changes")
                else:
                    self.logger.error(f"[CHANGE DETECTION] Failed to store status changes")
            
            # Analyze change patterns
            changes_by_type = {}
            affected_zones = []
            total_gallons_lost = 0
            
            for change in status_changes:
                change_type = change.change_type
                changes_by_type[change_type] = changes_by_type.get(change_type, 0) + 1
                
                if change.zone_name not in affected_zones:
                    affected_zones.append(change.zone_name)
                
                total_gallons_lost += change.expected_gallons_lost
            
            # Determine if immediate alert needed based on change types
            critical_change_types = ['rainfall_abort', 'sensor_abort', 'user_suspended']
            requires_immediate_alert = any(ct in changes_by_type for ct in critical_change_types)
            
            return ChangeDetectionResult(
                changes_detected=len(status_changes),
                changes_by_type=changes_by_type,
                affected_zones=affected_zones,
                total_gallons_lost=total_gallons_lost,
                requires_immediate_alert=requires_immediate_alert
            )
            
        except Exception as e:
            self.logger.error(f"Error in change detection analysis: {e}")
            return ChangeDetectionResult(
                changes_detected=0, changes_by_type={}, affected_zones=[],
                total_gallons_lost=0, requires_immediate_alert=False
            )
    
    def _analyze_current_status(self, target_date: date, 
                               current_runs: List = None,
                               sensor_info: Dict = None) -> List[CurrentStatusAlert]:
        """Analyze current status for immediate alerts"""
        alerts = []
        
        try:
            # 1. Check sensor status (CRITICAL - affects all irrigation)
            # Only create sensor alerts for current day (sensor status is real-time only)
            from utils.timezone_utils import get_houston_now
            today = get_houston_now().date()
            
            if sensor_info and sensor_info.get('irrigation_suspended', False):
                # Determine alert message based on whether this is current or historical data
                is_historical = sensor_info.get('historical', False)
                if target_date == today and not is_historical:
                    # Current day with real-time sensor data
                    message = f"Rain sensor is actively stopping ALL irrigation: {sensor_info.get('sensor_status', 'Unknown status')}"
                    severity = 'critical'
                elif is_historical:
                    # Historical sensor data
                    message = f"Rain sensor was stopping irrigation on {target_date}: {sensor_info.get('sensor_status', 'Unknown status')}"
                    severity = 'warning'  # Less urgent since it's historical
                else:
                    # Skip if no appropriate sensor data
                    return alerts
                
                sensor_alert = CurrentStatusAlert(
                    alert_type='sensor_active',
                    severity=severity,
                    message=message,
                    affected_zones=['ALL_ZONES'],
                    expected_gallons_lost=self._calculate_total_daily_gallons(target_date),
                    sensor_status=sensor_info.get('sensor_status', '')
                )
                alerts.append(sensor_alert)
                
                if severity == 'critical':
                    self.logger.warning(f"[CRITICAL] {sensor_alert.message}")
                else:
                    self.logger.info(f"[HISTORICAL] {sensor_alert.message}")
            
            # 2. Check currently aborted zones
            if current_runs:
                aborted_zones = self._find_currently_aborted_zones(current_runs)
                if aborted_zones:
                    total_gallons = sum(zone['expected_gallons'] for zone in aborted_zones)
                    zone_names = [zone['zone_name'] for zone in aborted_zones]
                    
                    abort_alert = CurrentStatusAlert(
                        alert_type='zones_aborted',
                        severity='warning',
                        message=f"{len(aborted_zones)} zone runs have aborted irrigation",
                        affected_zones=zone_names,
                        expected_gallons_lost=total_gallons
                    )
                    alerts.append(abort_alert)
                    self.logger.warning(f"[WARNING] {abort_alert.message}: {', '.join(set(zone_names))} zones affected")
                
                # 3. Check currently suspended zones
                suspended_zones = self._find_currently_suspended_zones(current_runs)
                if suspended_zones:
                    total_gallons = sum(zone['expected_gallons'] for zone in suspended_zones)
                    zone_names = [zone['zone_name'] for zone in suspended_zones]
                    
                    suspend_alert = CurrentStatusAlert(
                        alert_type='zones_suspended',
                        severity='warning',
                        message=f"{len(suspended_zones)} zones currently manually suspended",
                        affected_zones=zone_names,
                        expected_gallons_lost=total_gallons
                    )
                    alerts.append(suspend_alert)
                    self.logger.warning(f"[WARNING] {suspend_alert.message}: {', '.join(zone_names)}")
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error in current status analysis: {e}")
            return []
    
    def _find_currently_aborted_zones(self, current_runs: List) -> List[Dict]:
        """Find zones that currently have aborted irrigation"""
        aborted_zones = []
        
        for run in current_runs:
            if hasattr(run, 'raw_popup_text') and run.raw_popup_text:
                popup_lower = run.raw_popup_text.lower()
                
                if any(abort_phrase in popup_lower for abort_phrase in [
                    'aborted due to high daily rainfall',
                    'aborted due to sensor input',
                    'not scheduled to run'
                ]):
                    aborted_zones.append({
                        'zone_name': run.zone_name,
                        'zone_id': run.zone_id,
                        'expected_gallons': getattr(run, 'expected_gallons', 0) or 0,
                        'abort_reason': self._extract_abort_reason(run.raw_popup_text)
                    })
        
        return aborted_zones
    
    def _find_currently_suspended_zones(self, current_runs: List) -> List[Dict]:
        """Find zones that are currently manually suspended"""
        suspended_zones = []
        
        for run in current_runs:
            if hasattr(run, 'raw_popup_text') and run.raw_popup_text:
                popup_lower = run.raw_popup_text.lower()
                
                if 'water cycle suspended' in popup_lower:
                    suspended_zones.append({
                        'zone_name': run.zone_name,
                        'zone_id': run.zone_id,
                        'expected_gallons': getattr(run, 'expected_gallons', 0) or 0
                    })
        
        return suspended_zones
    
    def _extract_abort_reason(self, popup_text: str) -> str:
        """Extract specific abort reason from popup text"""
        if not popup_text:
            return "Unknown"
        
        popup_lower = popup_text.lower()
        
        if 'aborted due to high daily rainfall' in popup_lower:
            return "High daily rainfall"
        elif 'aborted due to sensor input' in popup_lower:
            return "Sensor input"
        elif 'not scheduled to run' in popup_lower:
            return "Not scheduled"
        else:
            return "Other"
    
    def _calculate_total_daily_gallons(self, target_date: date) -> float:
        """Calculate total expected gallons for the day"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT SUM(expected_gallons) 
                    FROM scheduled_runs 
                    WHERE schedule_date = ? AND expected_gallons IS NOT NULL
                """, (target_date.isoformat(),))
                
                result = cursor.fetchone()[0]
                return result or 0
                
        except Exception as e:
            self.logger.error(f"Error calculating daily gallons: {e}")
            return 0
    
    def _log_comprehensive_findings(self, change_results: ChangeDetectionResult, 
                                  current_alerts: List[CurrentStatusAlert], 
                                  target_date: date):
        """Log comprehensive analysis findings"""
        
        self.logger.info(f"[COMPREHENSIVE ANALYSIS] {target_date}")
        
        # Log change detection results
        if change_results.changes_detected > 0:
            self.logger.info(f"   Status Changes: {change_results.changes_detected} detected")
            for change_type, count in change_results.changes_by_type.items():
                self.logger.info(f"     {change_type}: {count}")
            self.logger.info(f"   Affected zones: {', '.join(change_results.affected_zones)}")
            self.logger.info(f"   Water impact: {change_results.total_gallons_lost:.1f} gallons")
        else:
            self.logger.info("   Status Changes: None detected")
        
        # Log current status alerts
        if current_alerts:
            self.logger.info(f"   Current Alerts: {len(current_alerts)}")
            for alert in current_alerts:
                self.logger.info(f"     {alert.severity.upper()}: {alert.message}")
        else:
            self.logger.info("   Current Alerts: None - all systems normal")
    
    def should_send_immediate_email(self, change_results: ChangeDetectionResult, 
                                  current_alerts: List[CurrentStatusAlert],
                                  sensor_status_changed: bool = False) -> bool:
        """
        Determine if immediate email should be sent based on CHANGES, not current status
        
        Args:
            change_results: Results from change detection
            current_alerts: Current status alerts
            sensor_status_changed: Whether rain sensor status actually changed
        """
        
        # CRITICAL FIX: Only send email for critical alerts if sensor status CHANGED
        critical_alerts = [a for a in current_alerts if a.severity == 'critical']
        if critical_alerts and sensor_status_changed:
            self.logger.info("[EMAIL DECISION] Sending email: Rain sensor status CHANGED")
            return True
        elif critical_alerts and not sensor_status_changed:
            self.logger.info("[EMAIL DECISION] NOT sending email: Rain sensor status unchanged (already reported)")
            return False
        
        # Send if there are significant changes
        if change_results.requires_immediate_alert:
            self.logger.info("[EMAIL DECISION] Sending email: Significant changes detected")
            return True
        
        # Send if multiple zones affected by ACTUAL changes
        if len(change_results.affected_zones) >= 3:
            self.logger.info(f"[EMAIL DECISION] Sending email: {len(change_results.affected_zones)} zones with ACTUAL changes")
            return True
        
        # REMOVED: No longer send emails just for current status without changes
        # Old logic was: if many zones currently have problems, send email
        # New logic: only send emails for actual changes, not ongoing conditions
        
        self.logger.info("[EMAIL DECISION] No email needed: No actual changes detected")
        return False
    
    def should_suppress_daily_email(self, current_alerts: List[CurrentStatusAlert]) -> bool:
        """Determine if daily status email should be suppressed due to comprehensive email being sent"""
        # Suppress daily email if critical comprehensive email was sent
        critical_alerts = [a for a in current_alerts if a.severity == 'critical']
        return len(critical_alerts) > 0
    
    def generate_comprehensive_email_content(self, change_results: ChangeDetectionResult,
                                           current_alerts: List[CurrentStatusAlert],
                                           target_date: date, 
                                           sensor_status_changed: bool = False) -> Dict[str, str]:
        """Generate email content focusing on CHANGES, not repetitive current status"""
        
        # Determine email urgency and subject
        critical_alerts = [a for a in current_alerts if a.severity == 'critical']
        has_changes = change_results.changes_detected > 0
        
        if critical_alerts and sensor_status_changed:
            subject = f"CRITICAL: Hydrawise - Rain sensor status CHANGED"
            urgency = "CRITICAL"
        elif has_changes:
            affected_count = len(change_results.affected_zones)
            subject = f"Hydrawise Alert - {affected_count} zones affected by irrigation changes"
            urgency = "WARNING"
        else:
            subject = f"Hydrawise Update - Status changes detected"
            urgency = "INFO"
        
        # Build email body
        body = f"""Hydrawise Status Change Report - {target_date.strftime('%B %d, %Y')}
URGENCY: {urgency}

"""
        
        # CRITICAL FIX: Only include sensor status if it actually CHANGED
        if critical_alerts and sensor_status_changed:
            body += "RAIN SENSOR STATUS CHANGE:\n"
            for alert in critical_alerts:
                body += f"🔴 {alert.message}\n"
                if alert.expected_gallons_lost > 0:
                    body += f"   Water impact: {alert.expected_gallons_lost:.1f} gallons\n"
            body += "\n"
        
        # Current non-critical alerts (ongoing issues with zones)
        non_critical_alerts = [a for a in current_alerts if a.severity != 'critical']
        if non_critical_alerts:
            body += "ZONES WITH ONGOING IRRIGATION ISSUES:\n"
            for alert in non_critical_alerts:
                icon = "🟡" if alert.severity == 'warning' else "🔵"
                body += f"{icon} {alert.message}\n"
                
                if alert.affected_zones and alert.affected_zones[0] != 'ALL_ZONES':
                    unique_zones = list(set(alert.affected_zones))
                    if len(unique_zones) <= 5:
                        body += f"   Affected zones: {', '.join(unique_zones)}\n"
                    else:
                        body += f"   Affected zones: {len(unique_zones)} zones ({', '.join(unique_zones[:3])}, and {len(unique_zones)-3} more)\n"
                
                if alert.expected_gallons_lost > 0:
                    body += f"   Water impact: {alert.expected_gallons_lost:.1f} gallons\n"
            body += "\n"
        
        # Changes detected
        if has_changes:
            body += "📊 STATUS CHANGES DETECTED:\n\n"
            
            for change_type, count in change_results.changes_by_type.items():
                if change_type == 'rainfall_abort':
                    body += f"🌧️ HIGH RAINFALL ABORTS: {count} zones\n"
                elif change_type == 'sensor_abort':
                    body += f"🔧 SENSOR INPUT ABORTS: {count} zones\n"
                elif change_type == 'user_suspended':
                    body += f"⏸️ USER SUSPENSIONS: {count} zones\n"
                elif change_type == 'normal_restored':
                    body += f"✅ NORMAL OPERATION RESTORED: {count} zones\n"
                else:
                    body += f"📝 OTHER CHANGES: {count} zones\n"
            
            body += f"\nZones with changes: {', '.join(change_results.affected_zones)}\n"
            body += f"Total water impact: {change_results.total_gallons_lost:.1f} gallons\n\n"
        
        # Summary and next steps
        body += "SUMMARY:\n"
        if critical_alerts:
            body += "🌱 PLANT MONITORING REQUIRED: Rain sensor has stopped all automatic irrigation\n"
            body += "   Monitor plants carefully for water stress until sensor re-enables\n"
        elif current_alerts:
            body += f"⚠️ {len(current_alerts)} zone runs not receiving irrigation\n"
        
        if has_changes:
            body += f"📈 {change_results.changes_detected} status changes detected for historical analysis\n"
        
        body += f"\nReport generated: {get_houston_now().strftime('%B %d, %Y %I:%M %p')} Houston time\n"
        body += "This comprehensive report tracks both changes and current status.\n"
        
        return {'subject': subject, 'body': body}


def integrate_comprehensive_monitoring(tracking_system, target_date: date, 
                                     collection_type: str, current_runs: List = None,
                                     sensor_info: Dict = None) -> Dict[str, Any]:
    """
    Integrate comprehensive monitoring with existing tracking system
    
    Returns enhanced results with both change detection and current status
    """
    try:
        monitor = ComprehensiveStatusMonitor(tracking_system.config.db_path)
        
        # Run comprehensive analysis
        change_results, current_alerts = monitor.analyze_comprehensive_status(
            target_date, current_runs, sensor_info
        )
        
        # Check if sensor status actually changed
        sensor_status_changed = False
        if sensor_info and hasattr(tracking_system, '_check_sensor_status_change'):
            sensor_status_changed = tracking_system._check_sensor_status_change(sensor_info)
        
        # CRITICAL FIX: Only send emails for TODAY's analysis, not historical analysis
        from utils.timezone_utils import get_houston_now
        today = get_houston_now().date()
        if target_date != today:
            # This is historical analysis - don't send emails about past data
            should_email = False
            tracking_system.logger.info(f"[EMAIL DECISION] Skipping email for historical date {target_date} (not today)")
        else:
            # Determine if email should be sent (based on actual changes, not current status)
            should_email = monitor.should_send_immediate_email(change_results, current_alerts, sensor_status_changed)
        
        # Generate email content if needed
        email_content = None
        if should_email and tracking_system.email_manager:
            email_content = monitor.generate_comprehensive_email_content(
                change_results, current_alerts, target_date, sensor_status_changed
            )
        
        return {
            'collection_type': collection_type,
            'target_date': target_date.isoformat(),
            'change_detection': {
                'changes_detected': change_results.changes_detected,
                'changes_by_type': change_results.changes_by_type,
                'affected_zones': change_results.affected_zones,
                'total_gallons_lost': change_results.total_gallons_lost
            },
            'current_status': {
                'alerts_count': len(current_alerts),
                'critical_alerts': len([a for a in current_alerts if a.severity == 'critical']),
                'alerts': [
                    {
                        'type': alert.alert_type,
                        'severity': alert.severity,
                        'message': alert.message,
                        'affected_zones': alert.affected_zones,
                        'gallons_lost': alert.expected_gallons_lost
                    }
                    for alert in current_alerts
                ]
            },
            'email_needed': should_email,
            'email_content': email_content,
            'suppress_daily_email': monitor.should_suppress_daily_email(current_alerts)
        }
        
    except Exception as e:
        logger.error(f"Error in comprehensive monitoring: {e}")
        return {
            'collection_type': collection_type,
            'target_date': target_date.isoformat(),
            'error': str(e)
        }
