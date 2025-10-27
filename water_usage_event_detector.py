#!/usr/bin/env python3
"""
Water Usage Event Detection Integration

Integrates existing anomaly detection systems to populate the events table
after admin_reported_runs.py completes scraping. Leverages existing functionality:
- IrrigationAnalytics.detect_anomalies()
- IrrigationFailureDetector.detect_failures() 
- WaterUsageEstimator usage flags from actual_runs table

Follows the same integration pattern as integrate_daily_usage_analytics.py

Author: AI Assistant
Date: 2025-01-27
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager
from database.irrigation_analytics import IrrigationAnalytics, UsageAnomaly, AnomalyType
from irrigation_failure_detector import IrrigationFailureDetector, IrrigationAlert
from utils.timezone_utils import get_houston_now, get_display_timestamp
from config.water_usage_config import get_water_usage_thresholds

logger = logging.getLogger(__name__)

@dataclass
class EventDetectionConfig:
    """Configuration for event detection integration"""
    enabled: bool = True
    detect_usage_anomalies: bool = True      # Use IrrigationAnalytics
    detect_irrigation_failures: bool = True  # Use IrrigationFailureDetector  
    detect_usage_flags: bool = True          # Use WaterUsageEstimator flags from actual_runs
    days_back_for_analysis: int = 1          # How many days to analyze
    min_severity_level: str = "INFO"         # Minimum severity to record: INFO, WARNING, CRITICAL

class WaterUsageEventDetector:
    """
    Integrates existing anomaly detection systems to populate events table
    """
    
    def __init__(self, config: EventDetectionConfig = None):
        """Initialize event detector with configuration"""
        self.config = config or EventDetectionConfig()
        self.db_manager = get_universal_database_manager()
        
        # Initialize existing detection systems
        if self.config.detect_usage_anomalies:
            # Get configurable thresholds for IrrigationAnalytics
            high_threshold, low_threshold = get_water_usage_thresholds()
            self.analytics = IrrigationAnalytics(
                too_high_multiplier=high_threshold,
                too_low_multiplier=low_threshold
            )
        else:
            self.analytics = None
            
        if self.config.detect_irrigation_failures:
            self.failure_detector = IrrigationFailureDetector()
        else:
            self.failure_detector = None
    
    def is_enabled(self) -> bool:
        """Check if event detection is enabled"""
        return self.config.enabled
    
    def detect_and_record_events_for_runs(self, run_identifiers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main method to detect and record events for specific newly collected runs
        
        Args:
            run_identifiers: List of dicts with 'zone_id' and 'actual_start_time' to identify runs
            
        Returns:
            Dictionary with detection results and statistics
        """
        if not self.is_enabled():
            return {'success': True, 'message': 'Event detection disabled', 'events_recorded': 0}
        
        if not run_identifiers:
            return {'success': True, 'message': 'No runs to analyze', 'events_recorded': 0}
            
        logger.info(f"[EVENT DETECTION] Starting event detection for {len(run_identifiers)} specific runs")
        
        try:
            results = {
                'success': False,
                'runs_analyzed': len(run_identifiers),
                'events_recorded': 0,
                'events_updated': 0,
                'usage_anomalies': 0,
                'irrigation_failures': 0,
                'usage_flag_events': 0,
                'errors': []
            }
            
            # Get the actual run data for these identifiers
            actual_runs = self._get_runs_by_identifiers(run_identifiers)
            if not actual_runs:
                return {'success': True, 'message': 'No matching runs found in database', 'events_recorded': 0}
            
            logger.info(f"[EVENT DETECTION] Found {len(actual_runs)} matching runs in database")
            
            # Step 1: Detect usage anomalies using IrrigationAnalytics (for specific runs)
            if self.config.detect_usage_anomalies and self.analytics:
                try:
                    logger.info("[EVENT DETECTION] Detecting usage anomalies for specific runs...")
                    anomaly_events = self._detect_anomalies_for_runs(actual_runs)
                    results['usage_anomalies'] = len(anomaly_events)
                    
                    # Record events in database
                    recorded, updated = self._record_events(anomaly_events)
                    results['events_recorded'] += recorded
                    results['events_updated'] += updated
                    
                    logger.info(f"[EVENT DETECTION] Processed {len(anomaly_events)} usage anomalies")
                    
                except Exception as e:
                    error_msg = f"Usage anomaly detection failed: {e}"
                    logger.error(f"[EVENT DETECTION] {error_msg}")
                    results['errors'].append(error_msg)
            
            # Step 2: Detect irrigation failures using IrrigationFailureDetector (for specific runs)
            if self.config.detect_irrigation_failures and self.failure_detector:
                try:
                    logger.info("[EVENT DETECTION] Detecting irrigation failures for specific runs...")
                    failure_events = self._detect_failures_for_runs(actual_runs)
                    results['irrigation_failures'] = len(failure_events)
                    
                    # Record events in database
                    recorded, updated = self._record_events(failure_events)
                    results['events_recorded'] += recorded
                    results['events_updated'] += updated
                    
                    logger.info(f"[EVENT DETECTION] Processed {len(failure_events)} irrigation failures")
                    
                except Exception as e:
                    error_msg = f"Irrigation failure detection failed: {e}"
                    logger.error(f"[EVENT DETECTION] {error_msg}")
                    results['errors'].append(error_msg)
            
            # Step 3: Process usage flags from the specific runs
            # Skip usage flag events that would duplicate anomaly events already detected
            if self.config.detect_usage_flags:
                try:
                    logger.info("[EVENT DETECTION] Processing usage flags for specific runs...")
                    flag_events = self._extract_usage_flag_events_for_runs(actual_runs)
                    
                    # Filter out usage flag events that duplicate anomaly events
                    if self.config.detect_usage_anomalies and self.analytics:
                        flag_events = self._filter_duplicate_usage_flag_events(flag_events)
                    
                    results['usage_flag_events'] = len(flag_events)
                    
                    # Record events in database
                    recorded, updated = self._record_events(flag_events)
                    results['events_recorded'] += recorded
                    results['events_updated'] += updated
                    
                    logger.info(f"[EVENT DETECTION] Processed {len(flag_events)} usage flag events")
                    
                except Exception as e:
                    error_msg = f"Usage flag processing failed: {e}"
                    logger.error(f"[EVENT DETECTION] {error_msg}")
                    results['errors'].append(error_msg)
            
            results['success'] = True
            total_events = results['events_recorded'] + results['events_updated']
            logger.info(f"[EVENT DETECTION] Completed: {total_events} total events processed ({results['events_recorded']} new, {results['events_updated']} updated)")
            
            return results
            
        except Exception as e:
            logger.error(f"[EVENT DETECTION] Event detection failed: {e}")
            return {
                'success': False,
                'runs_analyzed': len(run_identifiers),
                'error': str(e),
                'events_recorded': 0
            }

    def detect_and_record_events(self, target_date: date = None) -> Dict[str, Any]:
        """
        Main method to detect and record events for a target date
        
        Args:
            target_date: Date to analyze (defaults to today)
            
        Returns:
            Dictionary with detection results and statistics
        """
        if not self.is_enabled():
            return {'success': True, 'message': 'Event detection disabled', 'events_recorded': 0}
        
        if target_date is None:
            target_date = get_houston_now().date()
            
        logger.info(f"[EVENT DETECTION] Starting event detection for {target_date}")
        
        try:
            results = {
                'success': False,
                'target_date': target_date,
                'events_recorded': 0,
                'events_updated': 0,
                'usage_anomalies': 0,
                'irrigation_failures': 0,
                'usage_flag_events': 0,
                'errors': []
            }
            
            # Step 1: Detect usage anomalies using IrrigationAnalytics
            if self.config.detect_usage_anomalies and self.analytics:
                try:
                    logger.info("[EVENT DETECTION] Detecting usage anomalies...")
                    anomalies = self.analytics.detect_anomalies(
                        analysis_date=target_date,
                        days_back=self.config.days_back_for_analysis
                    )
                    anomaly_events = self._convert_anomalies_to_events(anomalies, target_date)
                    results['usage_anomalies'] = len(anomaly_events)
                    
                    # Record events in database
                    recorded, updated = self._record_events(anomaly_events)
                    results['events_recorded'] += recorded
                    results['events_updated'] += updated
                    
                    logger.info(f"[EVENT DETECTION] Processed {len(anomaly_events)} usage anomalies")
                    
                except Exception as e:
                    error_msg = f"Usage anomaly detection failed: {e}"
                    logger.error(f"[EVENT DETECTION] {error_msg}")
                    results['errors'].append(error_msg)
            
            # Step 2: Detect irrigation failures using IrrigationFailureDetector
            if self.config.detect_irrigation_failures and self.failure_detector:
                try:
                    logger.info("[EVENT DETECTION] Detecting irrigation failures...")
                    system_status = self.failure_detector.detect_failures(
                        target_date=datetime.combine(target_date, datetime.min.time())
                    )
                    failure_events = self._convert_alerts_to_events(system_status.alerts, target_date)
                    results['irrigation_failures'] = len(failure_events)
                    
                    # Record events in database
                    recorded, updated = self._record_events(failure_events)
                    results['events_recorded'] += recorded
                    results['events_updated'] += updated
                    
                    logger.info(f"[EVENT DETECTION] Processed {len(failure_events)} irrigation failures")
                    
                except Exception as e:
                    error_msg = f"Irrigation failure detection failed: {e}"
                    logger.error(f"[EVENT DETECTION] {error_msg}")
                    results['errors'].append(error_msg)
            
            # Step 3: Convert usage flags from actual_runs to events
            if self.config.detect_usage_flags:
                try:
                    logger.info("[EVENT DETECTION] Processing usage flags from actual_runs...")
                    flag_events = self._extract_usage_flag_events(target_date)
                    results['usage_flag_events'] = len(flag_events)
                    
                    # Record events in database
                    recorded, updated = self._record_events(flag_events)
                    results['events_recorded'] += recorded
                    results['events_updated'] += updated
                    
                    logger.info(f"[EVENT DETECTION] Processed {len(flag_events)} usage flag events")
                    
                except Exception as e:
                    error_msg = f"Usage flag processing failed: {e}"
                    logger.error(f"[EVENT DETECTION] {error_msg}")
                    results['errors'].append(error_msg)
            
            results['success'] = True
            total_events = results['events_recorded'] + results['events_updated']
            logger.info(f"[EVENT DETECTION] Completed: {total_events} total events processed ({results['events_recorded']} new, {results['events_updated']} updated)")
            
            return results
            
        except Exception as e:
            logger.error(f"[EVENT DETECTION] Event detection failed: {e}")
            return {
                'success': False,
                'target_date': target_date,
                'error': str(e),
                'events_recorded': 0
            }
    
    def _get_runs_by_identifiers(self, run_identifiers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get actual run data for specific run identifiers"""
        if not run_identifiers:
            return []
        
        # Build query to get runs by zone_id and actual_start_time
        placeholders = []
        params = []
        
        for identifier in run_identifiers:
            placeholders.append("(ar.zone_id = %s AND ar.actual_start_time = %s)")
            params.extend([identifier['zone_id'], identifier['actual_start_time']])
        
        query = f"""
            SELECT 
                ar.id, ar.zone_id, ar.zone_name, ar.run_date, ar.actual_start_time,
                ar.actual_gallons, ar.actual_duration_minutes, ar.usage_flag, 
                ar.usage_type, ar.usage, ar.scraped_at,
                z.average_flow_rate
            FROM actual_runs ar
            JOIN zones z ON ar.zone_id = z.zone_id
            WHERE ({' OR '.join(placeholders)})
            ORDER BY ar.actual_start_time
        """
        
        try:
            return self.db_manager.adapter.execute_query(query, params)
        except Exception as e:
            logger.error(f"Failed to get runs by identifiers: {e}")
            return []
    
    def _detect_anomalies_for_runs(self, actual_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect usage anomalies for specific runs using IrrigationAnalytics"""
        events = []
        
        for run in actual_runs:
            try:
                # Get baseline for this zone using the correct method name
                baseline = self.analytics.calculate_baseline(run['zone_name'])
                if not baseline:
                    logger.debug(f"No baseline available for zone {run['zone_name']}, skipping anomaly detection")
                    continue
                
                # Check for anomalies in this specific run
                run_anomalies = self.analytics._check_run_anomalies(
                    zone_name=run['zone_name'],
                    run_date=run['run_date'],
                    actual_gallons=float(run['actual_gallons'] or 0),
                    actual_duration=int(run['actual_duration_minutes'] or 0),
                    avg_gallons=baseline.avg_gallons,
                    avg_duration=baseline.avg_duration_minutes,
                    avg_gpm=baseline.avg_gpm,
                    std_dev_gallons=baseline.std_dev_gallons,
                    std_dev_duration=baseline.std_dev_duration
                )
                
                # Convert anomalies to events with enhanced data
                for anomaly in run_anomalies:
                    # Skip runtime anomalies as requested
                    if anomaly.anomaly_type in [AnomalyType.RUNTIME_INCREASE, AnomalyType.RUNTIME_DECREASE]:
                        continue
                    
                    event = self._create_enhanced_event_from_anomaly(anomaly, run)
                    events.append(event)
                    
            except Exception as e:
                logger.warning(f"Failed to detect anomalies for run {run.get('id', 'unknown')}: {e}")
        
        return events
    
    def _detect_failures_for_runs(self, actual_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect irrigation failures for specific runs using IrrigationFailureDetector"""
        events = []
        
        # Group runs by date for failure detection (IrrigationFailureDetector works by date)
        runs_by_date = {}
        for run in actual_runs:
            run_date = run['run_date']
            if run_date not in runs_by_date:
                runs_by_date[run_date] = []
            runs_by_date[run_date].append(run)
        
        # Detect failures for each date, but only process events for our specific runs
        for run_date, date_runs in runs_by_date.items():
            try:
                # Get all alerts for this date
                target_datetime = datetime.combine(run_date, datetime.min.time())
                system_status = self.failure_detector.detect_failures(target_date=target_datetime)
                
                # Filter alerts to only those related to our specific runs
                for alert in system_status.alerts:
                    # Check if this alert is for one of our specific runs
                    matching_run = None
                    for run in date_runs:
                        if (alert.zone_name == run['zone_name'] and 
                            abs((alert.detected_at - run['actual_start_time']).total_seconds()) < 1800):  # Within 30 minutes
                            matching_run = run
                            break
                    
                    if matching_run:
                        event = self._create_enhanced_event_from_alert(alert, matching_run)
                        events.append(event)
                        
            except Exception as e:
                logger.warning(f"Failed to detect failures for date {run_date}: {e}")
        
        return events
    
    def _extract_usage_flag_events_for_runs(self, actual_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract events from usage_flag column for specific runs"""
        events = []
        
        for run in actual_runs:
            usage_flag = run.get('usage_flag')
            if usage_flag in ['too_high', 'too_low', 'zero_reported']:
                try:
                    event = self._create_enhanced_event_from_usage_flag(run)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to create usage flag event for run {run.get('id', 'unknown')}: {e}")
        
        return events
    
    def _get_all_runs_for_date(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Get all runs for a specific date (regardless of when they were scraped).
        This ensures we process all runs for the date that admin_reported_runs.py just processed.
        
        Args:
            target_date: The date to get all runs for
            
        Returns:
            List of run identifiers with zone_id and actual_start_time
        """
        try:
            query = """
                SELECT DISTINCT ar.zone_id, ar.actual_start_time
                FROM actual_runs ar
                WHERE ar.run_date = %s
                AND ar.actual_start_time IS NOT NULL
                ORDER BY ar.actual_start_time
            """
            
            results = self.db_manager.adapter.execute_query(query, (target_date,))
            
            # Convert to the format expected by detect_and_record_events_for_runs
            run_identifiers = []
            for result in results:
                run_identifiers.append({
                    'zone_id': result['zone_id'],
                    'actual_start_time': result['actual_start_time']
                })
            
            logger.debug(f"Found {len(run_identifiers)} runs for date {target_date}")
            return run_identifiers
            
        except Exception as e:
            logger.error(f"Failed to get runs for date {target_date}: {e}")
            return []
    
    def _get_recently_collected_runs(self, minutes_back: int = 60) -> List[Dict[str, Any]]:
        """
        Get runs that were recently collected (scraped) by detecting recent scraped_at timestamps.
        
        Args:
            minutes_back: How many minutes back to look for recently collected runs
            
        Returns:
            List of run identifiers with zone_id and actual_start_time
        """
        try:
            # Look for runs that were scraped in the last N minutes
            cutoff_time = get_houston_now() - timedelta(minutes=minutes_back)
            
            query = """
                SELECT DISTINCT ar.zone_id, ar.actual_start_time, ar.scraped_at
                FROM actual_runs ar
                WHERE ar.scraped_at >= %s
                AND ar.actual_start_time IS NOT NULL
                ORDER BY ar.scraped_at DESC, ar.actual_start_time DESC
                LIMIT 50
            """
            
            results = self.db_manager.adapter.execute_query(query, (cutoff_time,))
            
            # Convert to the format expected by detect_and_record_events_for_runs
            run_identifiers = []
            for result in results:
                run_identifiers.append({
                    'zone_id': result['zone_id'],
                    'actual_start_time': result['actual_start_time']
                })
            
            logger.debug(f"Found {len(run_identifiers)} recently collected runs (scraped since {cutoff_time})")
            return run_identifiers
            
        except Exception as e:
            logger.error(f"Failed to get recently collected runs: {e}")
            return []
    
    def _create_enhanced_event_from_anomaly(self, anomaly: UsageAnomaly, run: Dict[str, Any]) -> Dict[str, Any]:
        """Create an enhanced event from a usage anomaly with flow rate and timing data"""
        
        # Calculate flow rates
        actual_gallons = float(run['actual_gallons'] or 0)
        actual_duration = float(run['actual_duration_minutes'] or 0)
        actual_flow_rate = actual_gallons / actual_duration if actual_duration > 0 else 0
        expected_flow_rate = float(run['average_flow_rate'] or 0)
        
        # Map anomaly types to event failure types (excluding runtime anomalies)
        failure_type_map = {
            AnomalyType.ZERO_USAGE: 'WATER_VARIANCE',
            AnomalyType.HIGH_USAGE: 'WATER_VARIANCE', 
            AnomalyType.LOW_USAGE: 'WATER_VARIANCE',
            AnomalyType.EFFICIENCY_DROP: 'WATER_VARIANCE',
            AnomalyType.EFFICIENCY_SPIKE: 'WATER_VARIANCE'
        }
        
        # Map severity levels
        severity_map = {
            'HIGH': 'CRITICAL',
            'MEDIUM': 'WARNING', 
            'LOW': 'INFO'
        }
        
        # Create unique event ID using run-specific information
        event_id = f"anomaly_{anomaly.anomaly_type.value}_{run['zone_id']}_{run['actual_start_time'].strftime('%Y%m%d_%H%M%S')}"
        
        return {
            'failure_id': event_id,
            'zone_id': run['zone_id'],
            'zone_name': run['zone_name'],
            'failure_date': run['run_date'],
            'failure_type': failure_type_map.get(anomaly.anomaly_type, 'WATER_VARIANCE'),
            'severity': severity_map.get(anomaly.severity, anomaly.severity),
            'description': anomaly.description,
            'recommended_action': self._get_recommended_action_for_anomaly(anomaly),
            'plant_risk': self._get_plant_risk_for_anomaly(anomaly),
            'actual_run_id': run['id'],
            
            # Enhanced timing information
            'event_time': run['actual_start_time'],  # When the irrigation actually started
            
            # Enhanced usage information
            'actual_gallons': actual_gallons,
            'estimated_gallons': anomaly.expected_value,  # Expected gallons from baseline
            'scheduled_gallons': None,  # Not available from anomaly detection
            'water_deficit': max(0, anomaly.expected_value - actual_gallons) if anomaly.expected_value else 0,
            
            # Enhanced flow rate information
            'actual_flow_rate': actual_flow_rate,
            'expected_flow_rate': expected_flow_rate,
            
            # Audit timestamps
            'detected_at': get_houston_now(),
            'last_updated': get_houston_now()
        }
    
    def _create_enhanced_event_from_alert(self, alert: IrrigationAlert, run: Dict[str, Any]) -> Dict[str, Any]:
        """Create an enhanced event from an irrigation alert with flow rate and timing data"""
        
        # Calculate flow rates
        actual_gallons = float(run['actual_gallons'] or 0)
        actual_duration = float(run['actual_duration_minutes'] or 0)
        actual_flow_rate = actual_gallons / actual_duration if actual_duration > 0 else 0
        expected_flow_rate = float(run['average_flow_rate'] or 0)
        
        return {
            'failure_id': alert.alert_id,
            'zone_id': run['zone_id'],
            'zone_name': run['zone_name'],
            'failure_date': run['run_date'],
            'failure_type': alert.failure_type,
            'severity': alert.severity,
            'description': alert.description,
            'recommended_action': alert.recommended_action,
            'plant_risk': alert.plant_risk,
            'max_hours_without_water': alert.max_hours_without_water,
            'actual_run_id': run['id'],
            
            # Enhanced timing information
            'event_time': run['actual_start_time'],  # When the irrigation actually started
            
            # Enhanced usage information
            'actual_gallons': actual_gallons,
            'estimated_gallons': alert.scheduled_gallons,  # From alert
            'scheduled_gallons': alert.scheduled_gallons,
            'water_deficit': alert.water_deficit or 0,
            'hours_since_last_water': alert.hours_since_last_water,
            
            # Enhanced flow rate information
            'actual_flow_rate': actual_flow_rate,
            'expected_flow_rate': expected_flow_rate,
            
            # Audit timestamps
            'detected_at': get_houston_now(),
            'last_updated': get_houston_now()
        }
    
    def _create_enhanced_event_from_usage_flag(self, run: Dict[str, Any]) -> Dict[str, Any]:
        """Create an enhanced event from a usage flag with flow rate and timing data"""
        
        usage_flag = run['usage_flag']
        if usage_flag not in ['too_high', 'too_low', 'zero_reported']:
            return None
        
        # Calculate flow rates
        actual_gallons = float(run['actual_gallons'] or 0)
        actual_duration = float(run['actual_duration_minutes'] or 0)
        actual_flow_rate = actual_gallons / actual_duration if actual_duration > 0 else 0
        expected_flow_rate = float(run['average_flow_rate'] or 0)
        
        # Calculate estimated gallons using zone average flow rate
        estimated_gallons = expected_flow_rate * actual_duration if expected_flow_rate and actual_duration else 0
        
        # Map usage_flag to severity
        severity_map = {
            'too_high': 'WARNING',
            'too_low': 'WARNING',
            'zero_reported': 'CRITICAL'  # Zero reported is often a critical issue
        }
        
        # Create description with flow rate information
        if usage_flag == 'too_high':
            if estimated_gallons > 0:
                ratio = actual_gallons / estimated_gallons
                description = f"High water usage: {actual_gallons:.1f}g vs {estimated_gallons:.1f}g expected ({ratio:.1f}x), flow rate: {actual_flow_rate:.2f} vs {expected_flow_rate:.2f} GPM expected"
            else:
                description = f"High water usage: {actual_gallons:.1f}g, flow rate: {actual_flow_rate:.2f} GPM"
        elif usage_flag == 'too_low':
            if estimated_gallons > 0:
                ratio = actual_gallons / estimated_gallons
                description = f"Low water usage: {actual_gallons:.1f}g vs {estimated_gallons:.1f}g expected ({ratio:.1f}x), flow rate: {actual_flow_rate:.2f} vs {expected_flow_rate:.2f} GPM expected"
            else:
                description = f"Low water usage: {actual_gallons:.1f}g, flow rate: {actual_flow_rate:.2f} GPM"
        else:  # zero_reported
            description = f"Zero water reported: Zone ran for {actual_duration:.0f} minutes but reported 0 gallons (estimated {estimated_gallons:.1f}g at {expected_flow_rate:.2f} GPM)"
        
        # Create unique event ID using run-specific information
        event_id = f"usage_flag_{usage_flag}_{run['zone_id']}_{run['actual_start_time'].strftime('%Y%m%d_%H%M%S')}"
        
        return {
            'failure_id': event_id,
            'zone_id': run['zone_id'],
            'zone_name': run['zone_name'],
            'failure_date': run['run_date'],
            'failure_type': 'WATER_VARIANCE',
            'severity': severity_map.get(usage_flag, 'INFO'),
            'description': description,
            'recommended_action': self._get_recommended_action_for_usage_flag(usage_flag),
            'plant_risk': 'HIGH' if usage_flag == 'zero_reported' else 'MEDIUM',
            'actual_run_id': run['id'],
            
            # Enhanced timing information
            'event_time': run['actual_start_time'],  # When the irrigation actually started
            
            # Enhanced usage information
            'actual_gallons': actual_gallons,
            'estimated_gallons': estimated_gallons,
            'scheduled_gallons': None,  # Not available from usage flag
            'water_deficit': max(0, estimated_gallons - actual_gallons) if estimated_gallons else 0,
            
            # Enhanced flow rate information
            'actual_flow_rate': actual_flow_rate,
            'expected_flow_rate': expected_flow_rate,
            
            # Audit timestamps
            'detected_at': get_houston_now(),
            'last_updated': get_houston_now()
        }
    
    def _get_recommended_action_for_anomaly(self, anomaly: UsageAnomaly) -> str:
        """Get recommended action for a usage anomaly"""
        if anomaly.anomaly_type == AnomalyType.ZERO_USAGE:
            return "Check irrigation system for blockages or controller issues"
        elif anomaly.anomaly_type == AnomalyType.HIGH_USAGE:
            return "Check for leaks, broken sprinkler heads, or controller malfunction"
        elif anomaly.anomaly_type == AnomalyType.LOW_USAGE:
            return "Check for partial blockages, low water pressure, or controller issues"
        elif anomaly.anomaly_type in [AnomalyType.EFFICIENCY_DROP, AnomalyType.EFFICIENCY_SPIKE]:
            return "Check irrigation system components and flow rate calibration"
        else:
            return "Investigate irrigation system performance"
    
    def _get_plant_risk_for_anomaly(self, anomaly: UsageAnomaly) -> str:
        """Get plant risk level for a usage anomaly"""
        if anomaly.anomaly_type == AnomalyType.ZERO_USAGE:
            return 'HIGH'
        elif anomaly.anomaly_type == AnomalyType.LOW_USAGE:
            return 'MEDIUM' if anomaly.severity == 'HIGH' else 'LOW'
        else:
            return 'LOW'
    
    def _get_recommended_action_for_usage_flag(self, usage_flag: str) -> str:
        """Get recommended action for a usage flag"""
        if usage_flag == 'zero_reported':
            return "Check irrigation system immediately - no water delivery detected"
        elif usage_flag == 'too_high':
            return "Check for leaks or system malfunction causing excess water usage"
        elif usage_flag == 'too_low':
            return "Check for blockages or system issues causing reduced water delivery"
        else:
            return "Investigate irrigation system performance"
    
    def _convert_anomalies_to_events(self, anomalies: List[UsageAnomaly], target_date: date) -> List[Dict[str, Any]]:
        """Convert IrrigationAnalytics anomalies to events table format"""
        events = []
        
        for anomaly in anomalies:
            # Skip runtime anomalies - we don't want runtime events for event detection
            if anomaly.anomaly_type in [AnomalyType.RUNTIME_INCREASE, AnomalyType.RUNTIME_DECREASE]:
                continue
                
            # Map anomaly types to event failure types (excluding runtime anomalies)
            failure_type_map = {
                AnomalyType.ZERO_USAGE: 'WATER_VARIANCE',
                AnomalyType.HIGH_USAGE: 'WATER_VARIANCE', 
                AnomalyType.LOW_USAGE: 'WATER_VARIANCE',
                AnomalyType.EFFICIENCY_DROP: 'WATER_VARIANCE',
                AnomalyType.EFFICIENCY_SPIKE: 'WATER_VARIANCE'
            }
            
            # Map severity levels
            severity_map = {
                'HIGH': 'CRITICAL',
                'MEDIUM': 'WARNING', 
                'LOW': 'INFO'
            }
            
            failure_type = failure_type_map.get(anomaly.anomaly_type, 'WATER_VARIANCE')
            severity = severity_map.get(anomaly.severity, 'WARNING')
            
            # Skip if below minimum severity
            if not self._meets_severity_threshold(severity):
                continue
            
            # Get actual_run_id if available
            actual_run_id = self._get_actual_run_id(anomaly.zone_name, anomaly.run_date)
            
            event = {
                'failure_id': f"anomaly_{anomaly.anomaly_type.value}_{self._get_zone_id(anomaly.zone_name)}_{anomaly.run_date.strftime('%Y%m%d')}",
                'zone_id': self._get_zone_id(anomaly.zone_name),
                'zone_name': anomaly.zone_name,
                'failure_date': anomaly.run_date,
                'failure_type': failure_type,
                'severity': severity,
                'description': anomaly.description,
                'recommended_action': self._get_anomaly_recommendation(anomaly),
                'plant_risk': self._assess_plant_risk(anomaly),
                'max_hours_without_water': self._calculate_max_hours_without_water(anomaly),
                'scheduled_run_id': None,  # Not available from anomaly data
                'actual_run_id': actual_run_id,
                'scheduled_gallons': anomaly.expected_value,
                'actual_gallons': anomaly.actual_value,
                'water_deficit': max(0, anomaly.expected_value - anomaly.actual_value) if anomaly.expected_value and anomaly.actual_value else None,
                'hours_since_last_water': None,  # Would need additional query
                'resolved': False,
                'detected_at': anomaly.detected_at if hasattr(anomaly, 'detected_at') else get_houston_now()
            }
            
            events.append(event)
        
        return events
    
    def _convert_alerts_to_events(self, alerts: List[IrrigationAlert], target_date: date) -> List[Dict[str, Any]]:
        """Convert IrrigationFailureDetector alerts to events table format"""
        events = []
        
        for alert in alerts:
            # Skip if below minimum severity
            if not self._meets_severity_threshold(alert.severity):
                continue
                
            # Map failure types
            failure_type_map = {
                'MISSING_RUN': 'MISSING_RUN',
                'UNEXPECTED_RUN': 'UNEXPECTED_RUN', 
                'FAILED_RUN': 'FAILED_RUN',
                'WATER_VARIANCE': 'WATER_VARIANCE',
                'DURATION_VARIANCE': 'DURATION_VARIANCE',
                'SENSOR_ABORT': 'SENSOR_ABORT'
            }
            
            failure_type = failure_type_map.get(alert.failure_type, alert.failure_type)
            
            event = {
                'failure_id': alert.alert_id,
                'zone_id': self._get_zone_id(alert.zone_name),
                'zone_name': alert.zone_name,
                'failure_date': target_date,
                'failure_type': failure_type,
                'severity': alert.severity,
                'description': alert.description,
                'recommended_action': alert.recommended_action,
                'plant_risk': alert.plant_risk,
                'max_hours_without_water': alert.max_hours_without_water,
                'scheduled_run_id': None,  # Would need additional query
                'actual_run_id': None,     # Would need additional query
                'scheduled_gallons': alert.scheduled_gallons,
                'actual_gallons': alert.actual_gallons,
                'water_deficit': alert.water_deficit,
                'hours_since_last_water': alert.hours_since_last_water,
                'resolved': False,
                'detected_at': alert.detected_at
            }
            
            events.append(event)
        
        return events
    
    def _extract_usage_flag_events(self, target_date: date) -> List[Dict[str, Any]]:
        """Extract events from usage_flag column in actual_runs table"""
        events = []
        
        try:
            # Query actual_runs for anomalous usage flags
            query = """
                SELECT id, zone_id, zone_name, run_date, actual_start_time,
                       actual_duration_minutes, actual_gallons, usage_flag, usage_type,
                       usage, raw_popup_text
                FROM actual_runs 
                WHERE run_date = %s 
                AND usage_flag IN ('zero_reported', 'too_high', 'too_low')
                ORDER BY zone_id, actual_start_time
            """
            
            results = self.db_manager.adapter.execute_query(query, (target_date,))
            
            for row in results:
                usage_flag = row['usage_flag']
                
                # Skip normal usage
                if usage_flag == 'normal':
                    continue
                
                # Map usage flags to event data
                flag_mapping = {
                    'zero_reported': {
                        'failure_type': 'WATER_VARIANCE',
                        'severity': 'CRITICAL',
                        'description': f"Zone ran for {row['actual_duration_minutes']} minutes but reported 0 gallons",
                        'plant_risk': 'HIGH',
                        'max_hours_without_water': 24
                    },
                    'too_high': {
                        'failure_type': 'WATER_VARIANCE', 
                        'severity': 'WARNING',
                        'description': f"Water usage significantly higher than expected ({row['actual_gallons']:.1f}g vs expected based on flow rate)",
                        'plant_risk': 'LOW',
                        'max_hours_without_water': 48
                    },
                    'too_low': {
                        'failure_type': 'WATER_VARIANCE',
                        'severity': 'WARNING', 
                        'description': f"Water usage significantly lower than expected ({row['actual_gallons']:.1f}g vs expected based on flow rate)",
                        'plant_risk': 'MEDIUM',
                        'max_hours_without_water': 36
                    }
                }
                
                mapping = flag_mapping.get(usage_flag, flag_mapping['too_low'])
                
                # Skip if below minimum severity
                if not self._meets_severity_threshold(mapping['severity']):
                    continue
                
                event = {
                    'failure_id': f"usage_flag_{row['usage_flag']}_{row['zone_id']}_{row['actual_start_time'].strftime('%Y%m%d_%H%M%S')}",
                    'zone_id': row['zone_id'],
                    'zone_name': row['zone_name'],
                    'failure_date': target_date,
                    'failure_type': mapping['failure_type'],
                    'severity': mapping['severity'],
                    'description': mapping['description'],
                    'recommended_action': self._get_usage_flag_recommendation(usage_flag),
                    'plant_risk': mapping['plant_risk'],
                    'max_hours_without_water': mapping['max_hours_without_water'],
                    'scheduled_run_id': None,  # Would need additional query
                    'actual_run_id': row['id'],
                    'scheduled_gallons': None,  # Would need flow rate calculation
                    'actual_gallons': row['actual_gallons'],
                    'water_deficit': None,  # Would need expected value calculation
                    'hours_since_last_water': None,  # Would need additional query
                    'resolved': False,
                    'detected_at': get_houston_now()
                }
                
                events.append(event)
                
        except Exception as e:
            logger.error(f"[EVENT DETECTION] Failed to extract usage flag events: {e}")
            
        return events
    
    def _record_events(self, events: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Record events in the events table with upsert logic
        
        Returns:
            Tuple of (new_records, updated_records)
        """
        if not events:
            return 0, 0
            
        new_count = 0
        updated_count = 0
        
        try:
            for event in events:
                # Check if event already exists
                existing_query = """
                    SELECT id, severity, description, actual_gallons, estimated_gallons, 
                           actual_flow_rate, expected_flow_rate, resolved
                    FROM events 
                    WHERE failure_id = %s
                """
                
                existing = self.db_manager.adapter.execute_query(existing_query, (event['failure_id'],))
                
                if existing:
                    # Update existing record if data has changed
                    existing_record = existing[0]
                    needs_update = (
                        existing_record['severity'] != event['severity'] or
                        existing_record['description'] != event['description'] or
                        existing_record['actual_gallons'] != event.get('actual_gallons') or
                        existing_record['estimated_gallons'] != event.get('estimated_gallons') or
                        existing_record['actual_flow_rate'] != event.get('actual_flow_rate') or
                        existing_record['expected_flow_rate'] != event.get('expected_flow_rate') or
                        existing_record['resolved'] != event.get('resolved', False)
                    )
                    
                    if needs_update:
                        update_query = """
                            UPDATE events SET
                                severity = %s, description = %s, recommended_action = %s,
                                plant_risk = %s, actual_gallons = %s, estimated_gallons = %s,
                                water_deficit = %s, actual_flow_rate = %s, expected_flow_rate = %s,
                                resolved = %s, last_updated = %s
                            WHERE failure_id = %s
                        """
                        
                        self.db_manager.adapter.execute_update(update_query, (
                            event['severity'], event['description'], event.get('recommended_action'),
                            event.get('plant_risk'), event.get('actual_gallons'), event.get('estimated_gallons'),
                            event.get('water_deficit'), event.get('actual_flow_rate'), event.get('expected_flow_rate'),
                            event.get('resolved', False), event.get('last_updated'), event['failure_id']
                        ))
                        
                        updated_count += 1
                        logger.debug(f"[EVENT DETECTION] Updated event: {event['failure_id']}")
                    
                else:
                    # Insert new record with enhanced columns
                    insert_query = """
                        INSERT INTO events (
                            failure_id, zone_id, zone_name, failure_date, failure_type,
                            severity, description, recommended_action, plant_risk,
                            max_hours_without_water, scheduled_run_id, actual_run_id,
                            event_time, scheduled_gallons, actual_gallons, estimated_gallons,
                            water_deficit, hours_since_last_water, actual_flow_rate, expected_flow_rate,
                            resolved, detected_at, last_updated
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    self.db_manager.adapter.execute_update(insert_query, (
                        event['failure_id'], event['zone_id'], event['zone_name'],
                        event['failure_date'], event['failure_type'], event['severity'],
                        event['description'], event.get('recommended_action'), event.get('plant_risk'),
                        event.get('max_hours_without_water'), event.get('scheduled_run_id'),
                        event.get('actual_run_id'), event.get('event_time'), event.get('scheduled_gallons'),
                        event.get('actual_gallons'), event.get('estimated_gallons'), event.get('water_deficit'),
                        event.get('hours_since_last_water'), event.get('actual_flow_rate'), event.get('expected_flow_rate'),
                        event.get('resolved', False), event.get('detected_at'), event.get('last_updated')
                    ))
                    
                    new_count += 1
                    logger.debug(f"[EVENT DETECTION] Recorded new event: {event['failure_id']}")
                    
        except Exception as e:
            logger.error(f"[EVENT DETECTION] Failed to record events: {e}")
            
        return new_count, updated_count
    
    def _filter_duplicate_usage_flag_events(self, usage_flag_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out usage flag events that would duplicate anomaly events already detected.
        
        Since both anomaly events and usage flag events use the same failure_type ('WATER_VARIANCE'),
        we need to check if the same run was already detected by IrrigationAnalytics.
        
        We filter based on the failure_id pattern:
        - Usage flag events have failure_id like: "usage_flag_{flag}_{zone_id}_{timestamp}"
        - Anomaly events have failure_id like: "anomaly_{type}_{zone_id}_{timestamp}"
        
        For the same run, if an anomaly event exists, skip the usage flag event.
        
        Args:
            usage_flag_events: List of usage flag events to filter
            
        Returns:
            Filtered list with duplicates removed
        """
        filtered_events = []
        
        for event in usage_flag_events:
            failure_id = event.get('failure_id', '')
            
            # Check if this is a usage flag event that might have an anomaly duplicate
            if failure_id.startswith('usage_flag_'):
                # Extract zone_id and timestamp from usage flag event
                try:
                    # Handle the fact that usage flags can contain underscores (too_high, too_low, zero_reported)
                    # Pattern: usage_flag_{flag}_{zone_id}_{date}_{time}
                    # Example: usage_flag_too_high_1_20250923_023000
                    parts = failure_id.split('_')
                    if len(parts) >= 6:  # usage, flag, {flag_parts}, zone_id, date, time
                        # The zone_id, date, and time are always the last three parts
                        zone_id = parts[-3]
                        date_part = parts[-2]
                        time_part = parts[-1]
                        timestamp = f"{date_part}_{time_part}"
                        
                        # Reconstruct the usage flag from the middle parts
                        flag_parts = parts[2:-3]  # Everything between 'flag' and the last three parts
                        usage_flag = '_'.join(flag_parts)  # Reconstruct 'too_high', 'too_low', 'zero_reported'
                        
                        # Map usage flags to anomaly types
                        anomaly_type_map = {
                            'zero_reported': 'zero_usage',
                            'too_high': 'efficiency_spike',  # High usage often shows as efficiency spike
                            'too_low': 'efficiency_drop'     # Low usage often shows as efficiency drop
                        }
                        
                        anomaly_type = anomaly_type_map.get(usage_flag)
                        if anomaly_type:
                            # Check if corresponding anomaly event exists in database
                            anomaly_failure_id = f"anomaly_{anomaly_type}_{zone_id}_{timestamp}"
                            
                            existing_query = "SELECT 1 FROM events WHERE failure_id = %s"
                            existing = self.db_manager.adapter.execute_query(existing_query, (anomaly_failure_id,))
                            
                            if existing:
                                logger.debug(f"[EVENT DETECTION] Skipping duplicate usage flag event: {failure_id} (anomaly event {anomaly_failure_id} already exists)")
                                continue
                                
                except Exception as e:
                    logger.warning(f"[EVENT DETECTION] Error parsing failure_id for duplicate check: {failure_id} - {e}")
                    # If we can't parse it, keep the event to be safe
                    pass
                
            # Keep this usage flag event (no duplicate found)
            filtered_events.append(event)
        
        removed_count = len(usage_flag_events) - len(filtered_events)
        if removed_count > 0:
            logger.info(f"[EVENT DETECTION] Filtered usage flag events: {len(usage_flag_events)} -> {len(filtered_events)} (removed {removed_count} duplicates)")
        
        return filtered_events
    
    def _meets_severity_threshold(self, severity: str) -> bool:
        """Check if severity meets minimum threshold"""
        severity_levels = {'INFO': 1, 'WARNING': 2, 'CRITICAL': 3}
        min_level = severity_levels.get(self.config.min_severity_level, 1)
        event_level = severity_levels.get(severity, 1)
        return event_level >= min_level
    
    def _get_zone_id(self, zone_name: str) -> Optional[int]:
        """Get zone_id from zone_name"""
        try:
            query = "SELECT zone_id FROM zones WHERE zone_name = %s"
            result = self.db_manager.adapter.execute_query(query, (zone_name,))
            return result[0]['zone_id'] if result else None
        except:
            return None
    
    def _get_actual_run_id(self, zone_name: str, run_date: date) -> Optional[int]:
        """Get actual_run_id for zone and date"""
        try:
            query = """
                SELECT id FROM actual_runs 
                WHERE zone_name = %s AND run_date = %s 
                ORDER BY actual_start_time DESC LIMIT 1
            """
            result = self.db_manager.adapter.execute_query(query, (zone_name, run_date))
            return result[0]['id'] if result else None
        except:
            return None
    
    def _get_anomaly_recommendation(self, anomaly: UsageAnomaly) -> str:
        """Get recommendation based on anomaly type"""
        recommendations = {
            AnomalyType.ZERO_USAGE: "Check flow sensors and irrigation lines for clogs or breaks",
            AnomalyType.HIGH_USAGE: "Inspect for leaks, check flow sensors, verify zone boundaries", 
            AnomalyType.LOW_USAGE: "Check for partial clogs, flow sensor calibration, or reduced pressure",
            AnomalyType.EFFICIENCY_DROP: "Inspect sprinkler heads and flow sensors for maintenance needs",
            AnomalyType.RUNTIME_INCREASE: "Check schedule settings and flow rate configuration",
            AnomalyType.RUNTIME_DECREASE: "Verify schedule settings and check for early shutoff conditions"
        }
        return recommendations.get(anomaly.anomaly_type, "Review irrigation system performance")
    
    def _get_usage_flag_recommendation(self, usage_flag: str) -> str:
        """Get recommendation based on usage flag"""
        recommendations = {
            'zero_reported': "Check flow sensors, inspect lines for clogs or breaks, verify zone operation",
            'too_high': "Inspect for leaks, check flow sensor accuracy, verify zone boundaries and settings",
            'too_low': "Check for partial clogs, flow sensor calibration, or reduced water pressure"
        }
        return recommendations.get(usage_flag, "Review irrigation system performance")
    
    def _assess_plant_risk(self, anomaly: UsageAnomaly) -> str:
        """Assess plant risk based on anomaly"""
        if anomaly.anomaly_type == AnomalyType.ZERO_USAGE:
            return 'HIGH'
        elif anomaly.anomaly_type in [AnomalyType.LOW_USAGE, AnomalyType.EFFICIENCY_DROP]:
            return 'MEDIUM' 
        else:
            return 'LOW'
    
    def _calculate_max_hours_without_water(self, anomaly: UsageAnomaly) -> int:
        """Calculate maximum hours plants can survive without water"""
        if anomaly.anomaly_type == AnomalyType.ZERO_USAGE:
            return 24  # Critical - plants need water within 24 hours
        elif anomaly.anomaly_type in [AnomalyType.LOW_USAGE, AnomalyType.EFFICIENCY_DROP]:
            return 48  # Medium risk - 48 hours
        else:
            return 72  # Low risk - 72 hours


# Integration functions following the same pattern as integrate_daily_usage_analytics.py

def integrate_with_automated_collector() -> Optional[WaterUsageEventDetector]:
    """
    Function to integrate event detection with automated collector
    
    Returns:
        WaterUsageEventDetector instance or None if disabled
    """
    try:
        # Check if enabled via environment variable
        enabled = os.getenv('WATER_USAGE_EVENT_DETECTION', 'true').lower() in ('true', '1', 'yes', 'on')
        
        if not enabled:
            logger.info("[INTEGRATION] Water usage event detection disabled via environment variable")
            return None
        
        config = EventDetectionConfig(enabled=enabled)
        detector = WaterUsageEventDetector(config)
        
        if detector.is_enabled():
            logger.info("[INTEGRATION] Water usage event detection integration active")
        else:
            logger.info("[INTEGRATION] Water usage event detection integration disabled")
        
        return detector
        
    except Exception as e:
        logger.error(f"[INTEGRATION] Failed to initialize event detection: {e}")
        return None

def add_to_daily_collection(detector: WaterUsageEventDetector, external_logger=None, target_date: date = None) -> bool:
    """
    Add event detection to daily collection process
    
    Args:
        detector: WaterUsageEventDetector instance
        external_logger: Logger to use (optional)
        target_date: Date to analyze (optional, defaults to today)
        
    Returns:
        True if event detection was processed successfully
    """
    # Use external logger if provided
    log = external_logger if external_logger else logger
    
    if not detector or not detector.is_enabled():
        log.info("[DAILY COLLECTION] Event detection not enabled")
        return True  # Not an error if disabled
    
    try:
        # Determine which date to analyze
        if target_date is None:
            target_date = get_houston_now().date()
        
        log.info(f"[DAILY COLLECTION] Running event detection for all runs on {target_date}...")
        
        # Get all runs for the target date (not just recently scraped ones)
        run_identifiers = detector._get_all_runs_for_date(target_date)
        
        if not run_identifiers:
            log.info(f"[DAILY COLLECTION] No runs found for {target_date} for event detection.")
            return True
        
        log.info(f"[DAILY COLLECTION] Found {len(run_identifiers)} runs for {target_date} for event detection.")
        
        # Use the run-specific event detection (with upsert logic to prevent duplicates)
        results = detector.detect_and_record_events_for_runs(run_identifiers)
        
        if results['success']:
            total_events = results['events_recorded'] + results['events_updated']
            log.info(f"[DAILY COLLECTION] Event detection completed for {target_date}: {total_events} events processed from {results['runs_analyzed']} runs")
            log.info(f"[DAILY COLLECTION]   - Usage anomalies: {results['usage_anomalies']}")
            log.info(f"[DAILY COLLECTION]   - Irrigation failures: {results['irrigation_failures']}")
            log.info(f"[DAILY COLLECTION]   - Usage flag events: {results['usage_flag_events']}")
            log.info(f"[DAILY COLLECTION]   - New events: {results['events_recorded']}")
            log.info(f"[DAILY COLLECTION]   - Updated events: {results['events_updated']}")
            
            if results.get('errors'):
                log.warning(f"[DAILY COLLECTION] Event detection had {len(results['errors'])} errors")
                for error in results['errors']:
                    log.warning(f"[DAILY COLLECTION]   - {error}")
        else:
            log.error(f"[DAILY COLLECTION] Event detection failed: {results.get('error', 'Unknown error')}")
        
        return results['success']
            
    except Exception as e:
        log.error(f"[DAILY COLLECTION] Error running event detection: {e}")
        return False


def add_event_detection_for_runs_to_collection(integration: WaterUsageEventDetector, external_logger=None, run_identifiers: List[Dict[str, Any]] = None) -> bool:
    """
    Add event detection for specific newly collected runs to the collection process.
    
    Args:
        integration: WaterUsageEventDetector instance
        external_logger: Logger to use for output
        run_identifiers: List of dicts with 'zone_id' and 'actual_start_time' for runs to analyze
        
    Returns:
        bool: True if successful, False otherwise
    """
    log = external_logger if external_logger else logger
    log.info("[EVENT DETECTION] Entered add_event_detection_for_runs_to_collection.")

    if not integration or not integration.is_enabled():
        log.info("[EVENT DETECTION] Event detection integration object problem or disabled.")
        return True

    if not run_identifiers:
        log.info("[EVENT DETECTION] No run identifiers provided for event detection.")
        return True

    try:
        results = integration.detect_and_record_events_for_runs(run_identifiers)
        if results['success']:
            log.info(f"[EVENT DETECTION] Completed for {results['runs_analyzed']} runs. New: {results['events_recorded']}, Updated: {results['events_updated']}")
            return True
        else:
            log.warning(f"[EVENT DETECTION] Failed: {results.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        log.error(f"[EVENT DETECTION] Error processing event detection for runs: {e}")
        return False


if __name__ == "__main__":
    """Test the event detection system"""
    import argparse
    from datetime import date, timedelta
    
    parser = argparse.ArgumentParser(description="Test Water Usage Event Detection")
    parser.add_argument('--date', type=str, help='Date to analyze (YYYY-MM-DD)', 
                       default=None)
    parser.add_argument('--days-back', type=int, help='Days back to analyze', default=1)
    
    args = parser.parse_args()
    
    # Parse target date
    if args.date:
        target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    else:
        target_date = date.today()
    
    print(f"Testing Water Usage Event Detection for {target_date}")
    print("=" * 60)
    
    # Test integration
    detector = integrate_with_automated_collector()
    if detector:
        print(f"Event detector initialized: enabled={detector.is_enabled()}")
        
        # Test detection
        results = detector.detect_and_record_events(target_date)
        
        print(f"\nResults:")
        print(f"  Success: {results['success']}")
        print(f"  Events recorded: {results.get('events_recorded', 0)}")
        print(f"  Events updated: {results.get('events_updated', 0)}")
        print(f"  Usage anomalies: {results.get('usage_anomalies', 0)}")
        print(f"  Irrigation failures: {results.get('irrigation_failures', 0)}")
        print(f"  Usage flag events: {results.get('usage_flag_events', 0)}")
        
        if results.get('errors'):
            print(f"  Errors: {len(results['errors'])}")
            for error in results['errors']:
                print(f"    - {error}")
    else:
        print("Event detector not initialized (disabled or error)")

