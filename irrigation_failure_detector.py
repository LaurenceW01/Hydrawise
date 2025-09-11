#!/usr/bin/env python3
"""
Hydrawise Irrigation Failure Detection System

This module compares scheduled vs actual irrigation runs to detect failures
and generate alerts for immediate user action to prevent plant loss.

Author: AI Assistant
Date: 2025-08-21
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field

# Import database interface instead of web scraper
from database.db_interface import HydrawiseDB
from hydrawise_web_scraper_refactored import ScheduledRun, ActualRun  # Keep data classes

# Import failure detection rules
from config.failure_detection_rules import FAILURE_DETECTION_RULES, ZONE_PRIORITIES

# Configure logging for failure detection
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('irrigation_failure_detection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class IrrigationAlert:
    """Alert for irrigation failure requiring immediate attention"""
    alert_id: str
    severity: str  # CRITICAL, WARNING, INFO
    zone_name: str
    failure_type: str
    description: str
    recommended_action: str
    plant_risk: str  # HIGH, MEDIUM, LOW
    max_hours_without_water: int
    hours_since_last_water: Optional[float] = None
    scheduled_gallons: Optional[float] = None
    actual_gallons: Optional[float] = None
    water_deficit: Optional[float] = None
    detected_at: datetime = field(default_factory=datetime.now)

@dataclass
class SystemStatus:
    """Overall irrigation system status"""
    status: str  # HEALTHY, DEGRADED, CRITICAL
    total_zones: int
    zones_running_normally: int
    zones_with_warnings: int
    zones_with_failures: int
    total_water_scheduled: float
    total_water_delivered: float
    water_efficiency: float  # percentage
    alerts: List[IrrigationAlert] = field(default_factory=list)

class IrrigationFailureDetector:
    """Detects irrigation failures by comparing scheduled vs actual runs"""
    
    def __init__(self, db_path: str = None):
        """Initialize failure detector with database interface"""
        self.db = HydrawiseDB(db_path)
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def detect_failures(self, target_date: datetime = None) -> SystemStatus:
        """
        Main method to detect irrigation failures for a given date
        
        Args:
            target_date: Date to analyze (defaults to today)
            
        Returns:
            SystemStatus with detected failures and alerts
        """
        if target_date is None:
            target_date = datetime.now()
            
        self.logger.info(f"Starting failure detection for {target_date.strftime('%Y-%m-%d')}")
        target_date_obj = target_date.date()
        
        try:
            # Read scheduled and actual runs from database
            self.logger.info("Reading scheduled runs from database...")
            scheduled_data = self.db.read_scheduled_runs(target_date_obj)
            self.logger.info(f"Found {len(scheduled_data)} scheduled runs")
            
            self.logger.info("Reading actual runs from database...")
            actual_data = self.db.read_actual_runs(target_date_obj)
            self.logger.info(f"Found {len(actual_data)} actual runs")
            
            # Convert database records to ScheduledRun/ActualRun objects
            scheduled_runs = self._convert_scheduled_data(scheduled_data)
            actual_runs = self._convert_actual_data(actual_data)
            
            # Analyze for failures
            system_status = self._analyze_irrigation_performance(scheduled_runs, actual_runs, target_date)
            
            return system_status
            
        except Exception as e:
            self.logger.error(f"Failure detection error: {e}")
            raise
    
    def _convert_scheduled_data(self, scheduled_data: List[Dict]) -> List[ScheduledRun]:
        """Convert database scheduled run records to ScheduledRun objects"""
        scheduled_runs = []
        for record in scheduled_data:
            try:
                # Parse start time from database string format
                start_time = datetime.fromisoformat(record['scheduled_start_time'])
                
                scheduled_run = ScheduledRun(
                    zone_id=str(record.get('zone_id', '')),
                    zone_name=record['zone_name'],
                    start_time=start_time,
                    duration_minutes=record['scheduled_duration_minutes'],  # Fixed field name
                    expected_gallons=record.get('expected_gallons'),  # Fixed field name
                    notes=record.get('notes', '')
                )
                scheduled_runs.append(scheduled_run)
            except Exception as e:
                self.logger.warning(f"Failed to convert scheduled run record: {e}")
                continue
        
        return scheduled_runs
    
    def _convert_actual_data(self, actual_data: List[Dict]) -> List[ActualRun]:
        """Convert database actual run records to ActualRun objects"""
        actual_runs = []
        for record in actual_data:
            try:
                # Parse start time from database string format
                start_time = datetime.fromisoformat(record['actual_start_time'])  # Fixed field name
                end_time = None
                if record.get('end_time'):
                    end_time = datetime.fromisoformat(record['end_time'])
                
                actual_run = ActualRun(
                    zone_id=str(record.get('zone_id', '')),
                    zone_name=record['zone_name'],
                    start_time=start_time,
                    duration_minutes=record['actual_duration_minutes'],  # Fixed field name
                    actual_gallons=record.get('actual_gallons'),  # Fixed field name
                    status=record.get('status', 'Normal'),
                    notes=record.get('notes', ''),
                    end_time=end_time,
                    failure_reason=record.get('failure_reason'),
                    current_ma=record.get('current_ma')  # Include current milliamps from database
                )
                actual_runs.append(actual_run)
            except Exception as e:
                self.logger.warning(f"Failed to convert actual run record: {e}")
                continue
        
        return actual_runs
                
    def _analyze_irrigation_performance(self, scheduled: List[ScheduledRun], 
                                      actual: List[ActualRun], 
                                      target_date: datetime) -> SystemStatus:
        """Compare scheduled vs actual runs to identify failures"""
        
        alerts = []
        
        # Group runs by zone for easier comparison
        scheduled_by_zone = self._group_runs_by_zone(scheduled)
        actual_by_zone = self._group_runs_by_zone(actual)
        
        all_zones = set(scheduled_by_zone.keys()) | set(actual_by_zone.keys())
        
        # Check each zone for failures
        for zone_name in all_zones:
            zone_scheduled = scheduled_by_zone.get(zone_name, [])
            zone_actual = actual_by_zone.get(zone_name, [])
            
            zone_alerts = self._analyze_zone_performance(zone_name, zone_scheduled, zone_actual, target_date)
            alerts.extend(zone_alerts)
            
        # Calculate system metrics
        total_scheduled_water = sum(run.expected_gallons or 0 for run in scheduled)
        total_actual_water = sum(run.actual_gallons or 0 for run in actual)
        
        water_efficiency = 0
        if total_scheduled_water > 0:
            water_efficiency = (total_actual_water / total_scheduled_water) * 100
            
        # Categorize alerts by severity
        critical_alerts = [a for a in alerts if a.severity == 'CRITICAL']
        warning_alerts = [a for a in alerts if a.severity == 'WARNING']
        
        # Determine overall system status
        if len(critical_alerts) > 0:
            status = "CRITICAL"
        elif len(warning_alerts) > 0:
            status = "DEGRADED"
        else:
            status = "HEALTHY"
            
        return SystemStatus(
            status=status,
            total_zones=len(all_zones),
            zones_running_normally=len(all_zones) - len(critical_alerts) - len(warning_alerts),
            zones_with_warnings=len(warning_alerts),
            zones_with_failures=len(critical_alerts),
            total_water_scheduled=total_scheduled_water,
            total_water_delivered=total_actual_water,
            water_efficiency=water_efficiency,
            alerts=sorted(alerts, key=lambda x: (x.severity == 'WARNING', x.zone_name))
        )
        
    def _analyze_zone_performance(self, zone_name: str, scheduled: List[ScheduledRun], 
                                 actual: List[ActualRun], target_date: datetime) -> List[IrrigationAlert]:
        """Analyze a single zone for irrigation failures"""
        
        alerts = []
        
        # FAILURE TYPE 1: Scheduled but didn't run
        for scheduled_run in scheduled:
            if not self._find_matching_actual_run(scheduled_run, actual):
                alert = self._create_missing_run_alert(zone_name, scheduled_run, target_date)
                alerts.append(alert)
                
        # FAILURE TYPE 2: Ran but not scheduled (unexpected runs)
        for actual_run in actual:
            if not self._find_matching_scheduled_run(actual_run, scheduled):
                alert = self._create_unexpected_run_alert(zone_name, actual_run, target_date)
                alerts.append(alert)
                
        # FAILURE TYPE 3: Significant water delivery differences
        for scheduled_run in scheduled:
            matching_actual = self._find_matching_actual_run(scheduled_run, actual)
            if matching_actual:
                alert = self._check_water_delivery_variance(zone_name, scheduled_run, matching_actual, target_date)
                if alert:
                    alerts.append(alert)
                    
        # FAILURE TYPE 4: Duration mismatches
        for scheduled_run in scheduled:
            matching_actual = self._find_matching_actual_run(scheduled_run, actual)
            if matching_actual:
                alert = self._check_duration_variance(zone_name, scheduled_run, matching_actual, target_date)
                if alert:
                    alerts.append(alert)
                    
        # FAILURE TYPE 5: Failed runs (from status/notes)
        for actual_run in actual:
            if actual_run.failure_reason or "abort" in actual_run.status.lower() or "fail" in actual_run.status.lower():
                alert = self._create_failed_run_alert(zone_name, actual_run, target_date)
                alerts.append(alert)
                
        return alerts
        
    def _create_missing_run_alert(self, zone_name: str, scheduled_run: ScheduledRun, target_date: datetime) -> IrrigationAlert:
        """Create alert for scheduled run that didn't execute"""
        
        # Determine zone priority based on name patterns
        if any(word in zone_name.lower() for word in ['turf', 'grass', 'lawn']):
            priority_level = 'LOW'
        elif any(word in zone_name.lower() for word in ['front color', 'planters', 'pots', 'beds at fence']):
            priority_level = 'HIGH'
        else:
            priority_level = 'MEDIUM'
            
        zone_config = ZONE_PRIORITIES.get(priority_level, ZONE_PRIORITIES['MEDIUM'])
        
        return IrrigationAlert(
            alert_id=f"missing_{zone_name}_{scheduled_run.start_time.strftime('%H%M')}",
            severity='CRITICAL',
            zone_name=zone_name,
            failure_type='MISSING_RUN',
            description=f"Scheduled {scheduled_run.duration_minutes}min run at {scheduled_run.start_time.strftime('%I:%M%p')} did not execute",
            recommended_action="Manually run zone immediately or check controller status",
            plant_risk=priority_level,
            max_hours_without_water=zone_config['max_hours_without_water'],
            scheduled_gallons=scheduled_run.expected_gallons,
            actual_gallons=0.0,
            water_deficit=scheduled_run.expected_gallons or 0.0
        )
        
    def _create_unexpected_run_alert(self, zone_name: str, actual_run: ActualRun, target_date: datetime) -> IrrigationAlert:
        """Create alert for run that executed but wasn't scheduled"""
        
        return IrrigationAlert(
            alert_id=f"unexpected_{zone_name}_{actual_run.start_time.strftime('%H%M')}",
            severity='WARNING',
            zone_name=zone_name,
            failure_type='UNEXPECTED_RUN',
            description=f"Unscheduled {actual_run.duration_minutes}min run at {actual_run.start_time.strftime('%I:%M%p')}",
            recommended_action="Verify if manual override was intended, check schedule accuracy",
            plant_risk='LOW',
            max_hours_without_water=48,
            scheduled_gallons=0.0,
            actual_gallons=actual_run.actual_gallons,
            water_deficit=0.0  # No deficit for extra water
        )
        
    def _create_failed_run_alert(self, zone_name: str, actual_run: ActualRun, target_date: datetime) -> IrrigationAlert:
        """Create alert for run that failed or was aborted"""
        
        # Determine zone priority based on name patterns
        if any(word in zone_name.lower() for word in ['turf', 'grass', 'lawn']):
            priority_level = 'LOW'
        elif any(word in zone_name.lower() for word in ['front color', 'planters', 'pots', 'beds at fence']):
            priority_level = 'HIGH'
        else:
            priority_level = 'MEDIUM'
            
        zone_config = ZONE_PRIORITIES.get(priority_level, ZONE_PRIORITIES['MEDIUM'])
        
        return IrrigationAlert(
            alert_id=f"failed_{zone_name}_{actual_run.start_time.strftime('%H%M')}",
            severity='CRITICAL',
            zone_name=zone_name,
            failure_type='FAILED_RUN',
            description=f"Run failed: {actual_run.failure_reason or actual_run.status}",
            recommended_action="Check sensors, investigate failure cause, manually run if needed",
            plant_risk=priority_level,
            max_hours_without_water=zone_config['max_hours_without_water'],
            scheduled_gallons=None,  # Unknown what was scheduled
            actual_gallons=actual_run.actual_gallons or 0.0,
            water_deficit=None  # Can't calculate without scheduled amount
        )
        
    def _check_water_delivery_variance(self, zone_name: str, scheduled: ScheduledRun, 
                                     actual: ActualRun, target_date: datetime) -> Optional[IrrigationAlert]:
        """Check for significant differences in water delivery"""
        
        if not scheduled.expected_gallons or not actual.actual_gallons:
            return None  # Can't compare without both values
            
        variance_percent = abs(actual.actual_gallons - scheduled.expected_gallons) / scheduled.expected_gallons * 100
        
        # Alert if more than 25% variance
        if variance_percent > 25:
            deficit = scheduled.expected_gallons - actual.actual_gallons
            
            severity = 'CRITICAL' if deficit > 0 and variance_percent > 50 else 'WARNING'
            
            return IrrigationAlert(
                alert_id=f"water_variance_{zone_name}_{scheduled.start_time.strftime('%H%M')}",
                severity=severity,
                zone_name=zone_name,
                failure_type='WATER_VARIANCE',
                description=f"Water delivery variance: {variance_percent:.1f}% (expected {scheduled.expected_gallons:.1f}gal, got {actual.actual_gallons:.1f}gal)",
                recommended_action="Check flow sensors, inspect for clogs or leaks",
                plant_risk='MEDIUM',
                max_hours_without_water=24,
                scheduled_gallons=scheduled.expected_gallons,
                actual_gallons=actual.actual_gallons,
                water_deficit=max(0, deficit)
            )
            
        return None
        
    def _check_duration_variance(self, zone_name: str, scheduled: ScheduledRun, 
                               actual: ActualRun, target_date: datetime) -> Optional[IrrigationAlert]:
        """Check for significant differences in run duration"""
        
        duration_diff = abs(actual.duration_minutes - scheduled.duration_minutes)
        
        # Alert if more than 1 minute difference for runs > 2 minutes
        if duration_diff > 1 and scheduled.duration_minutes > 2:
            variance_percent = (duration_diff / scheduled.duration_minutes) * 100
            
            severity = 'WARNING' if variance_percent < 50 else 'CRITICAL'
            
            return IrrigationAlert(
                alert_id=f"duration_variance_{zone_name}_{scheduled.start_time.strftime('%H%M')}",
                severity=severity,
                zone_name=zone_name,
                failure_type='DURATION_VARIANCE',
                description=f"Duration variance: {duration_diff}min difference (scheduled {scheduled.duration_minutes}min, ran {actual.duration_minutes}min)",
                recommended_action="Check for early shutoff, sensor issues, or manual intervention",
                plant_risk='MEDIUM',
                max_hours_without_water=24,
                scheduled_gallons=scheduled.expected_gallons,
                actual_gallons=actual.actual_gallons
            )
            
        return None
        
    def _find_matching_actual_run(self, scheduled: ScheduledRun, actual_runs: List[ActualRun]) -> Optional[ActualRun]:
        """Find actual run that matches a scheduled run (within time tolerance)"""
        
        # Look for runs within 30 minutes of scheduled time
        tolerance = timedelta(minutes=30)
        
        for actual_run in actual_runs:
            time_diff = abs((actual_run.start_time - scheduled.start_time).total_seconds())
            if time_diff <= tolerance.total_seconds():
                return actual_run
                
        return None
        
    def _find_matching_scheduled_run(self, actual: ActualRun, scheduled_runs: List[ScheduledRun]) -> Optional[ScheduledRun]:
        """Find scheduled run that matches an actual run (within time tolerance)"""
        
        # Look for runs within 30 minutes of actual time
        tolerance = timedelta(minutes=30)
        
        for scheduled_run in scheduled_runs:
            time_diff = abs((actual.start_time - scheduled_run.start_time).total_seconds())
            if time_diff <= tolerance.total_seconds():
                return scheduled_run
                
        return None
        
    def _group_runs_by_zone(self, runs: List) -> Dict[str, List]:
        """Group runs by zone name for easier comparison"""
        
        grouped = {}
        for run in runs:
            zone_name = run.zone_name
            if zone_name not in grouped:
                grouped[zone_name] = []
            grouped[zone_name].append(run)
            
        return grouped
        
    def generate_alert_report(self, system_status: SystemStatus) -> str:
        """Generate human-readable alert report"""
        
        report = []
        report.append("=" * 60)
        report.append("HYDRAWISE IRRIGATION FAILURE DETECTION REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M%p')}")
        report.append(f"System Status: {system_status.status}")
        report.append("")
        
        # Summary
        report.append("SYSTEM SUMMARY:")
        report.append(f"  Total Zones: {system_status.total_zones}")
        report.append(f"  Zones Running Normally: {system_status.zones_running_normally}")
        report.append(f"  Zones with Warnings: {system_status.zones_with_warnings}")
        report.append(f"  Zones with Failures: {system_status.zones_with_failures}")
        report.append(f"  Water Scheduled: {system_status.total_water_scheduled:.1f} gallons")
        report.append(f"  Water Delivered: {system_status.total_water_delivered:.1f} gallons")
        report.append(f"  Water Efficiency: {system_status.water_efficiency:.1f}%")
        report.append("")
        
        if not system_status.alerts:
            report.append("NO IRRIGATION FAILURES DETECTED - SYSTEM HEALTHY")
            report.append("")
        else:
            # Critical alerts first
            critical_alerts = [a for a in system_status.alerts if a.severity == 'CRITICAL']
            warning_alerts = [a for a in system_status.alerts if a.severity == 'WARNING']
            
            if critical_alerts:
                report.append("CRITICAL ALERTS (IMMEDIATE ACTION REQUIRED):")
                report.append("-" * 45)
                for alert in critical_alerts:
                    report.append(f"Zone: {alert.zone_name}")
                    report.append(f"  Issue: {alert.description}")
                    report.append(f"  Action: {alert.recommended_action}")
                    report.append(f"  Plant Risk: {alert.plant_risk}")
                    if alert.water_deficit:
                        report.append(f"  Water Deficit: {alert.water_deficit:.1f} gallons")
                    report.append("")
                    
            if warning_alerts:
                report.append("WARNING ALERTS (MONITOR CLOSELY):")
                report.append("-" * 35)
                for alert in warning_alerts:
                    report.append(f"Zone: {alert.zone_name}")
                    report.append(f"  Issue: {alert.description}")
                    report.append(f"  Action: {alert.recommended_action}")
                    report.append("")
                    
        report.append("=" * 60)
        
        return "\n".join(report)

def main():
    """Main function for testing the failure detector"""
    
    print("Hydrawise Irrigation Failure Detection System")
    print("=" * 50)
    print("Using database for analysis (no web scraping required)")
    
    # Create detector and run analysis (uses default database path)
    detector = IrrigationFailureDetector()
    
    try:
        # Detect failures for today
        system_status = detector.detect_failures()
        
        # Generate and display report
        report = detector.generate_alert_report(system_status)
        print(report)
        
        # Write report to file
        report_filename = f"irrigation_alert_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, 'w') as f:
            f.write(report)
        print(f"\nDetailed report saved to: {report_filename}")
        
    except Exception as e:
        logger.error(f"Failure detection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
