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
                'failure_id': f"anomaly_{anomaly.zone_name}_{anomaly.run_date}_{anomaly.anomaly_type.value}",
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
                    'failure_id': f"usage_flag_{row['zone_name']}_{target_date}_{row['actual_start_time']}",
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
                    SELECT id, severity, description, actual_gallons, resolved
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
                        existing_record['actual_gallons'] != event['actual_gallons'] or
                        existing_record['resolved'] != event['resolved']
                    )
                    
                    if needs_update:
                        update_query = """
                            UPDATE events SET
                                severity = %s, description = %s, recommended_action = %s,
                                plant_risk = %s, actual_gallons = %s, water_deficit = %s,
                                resolved = %s, detected_at = %s
                            WHERE failure_id = %s
                        """
                        
                        self.db_manager.adapter.execute_update(update_query, (
                            event['severity'], event['description'], event['recommended_action'],
                            event['plant_risk'], event['actual_gallons'], event['water_deficit'],
                            event['resolved'], event['detected_at'], event['failure_id']
                        ))
                        
                        updated_count += 1
                        logger.debug(f"[EVENT DETECTION] Updated event: {event['failure_id']}")
                    
                else:
                    # Insert new record
                    insert_query = """
                        INSERT INTO events (
                            failure_id, zone_id, zone_name, failure_date, failure_type,
                            severity, description, recommended_action, plant_risk,
                            max_hours_without_water, scheduled_run_id, actual_run_id,
                            scheduled_gallons, actual_gallons, water_deficit,
                            hours_since_last_water, resolved, detected_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    self.db_manager.adapter.execute_update(insert_query, (
                        event['failure_id'], event['zone_id'], event['zone_name'],
                        event['failure_date'], event['failure_type'], event['severity'],
                        event['description'], event['recommended_action'], event['plant_risk'],
                        event['max_hours_without_water'], event['scheduled_run_id'],
                        event['actual_run_id'], event['scheduled_gallons'], event['actual_gallons'],
                        event['water_deficit'], event['hours_since_last_water'],
                        event['resolved'], event['detected_at']
                    ))
                    
                    new_count += 1
                    logger.debug(f"[EVENT DETECTION] Recorded new event: {event['failure_id']}")
                    
        except Exception as e:
            logger.error(f"[EVENT DETECTION] Failed to record events: {e}")
            
        return new_count, updated_count
    
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
        if target_date is None:
            target_date = get_houston_now().date()
            
        log.info(f"[DAILY COLLECTION] Running water usage event detection for {target_date}...")
        results = detector.detect_and_record_events(target_date)
        
        if results['success']:
            total_events = results['events_recorded'] + results['events_updated']
            log.info(f"[DAILY COLLECTION] Event detection completed: {total_events} events processed")
            log.info(f"[DAILY COLLECTION]   - Usage anomalies: {results['usage_anomalies']}")
            log.info(f"[DAILY COLLECTION]   - Irrigation failures: {results['irrigation_failures']}")
            log.info(f"[DAILY COLLECTION]   - Usage flag events: {results['usage_flag_events']}")
            
            if results['errors']:
                log.warning(f"[DAILY COLLECTION] Event detection had {len(results['errors'])} errors")
                for error in results['errors']:
                    log.warning(f"[DAILY COLLECTION]   - {error}")
        else:
            log.error(f"[DAILY COLLECTION] Event detection failed: {results.get('error', 'Unknown error')}")
        
        return results['success']
            
    except Exception as e:
        log.error(f"[DAILY COLLECTION] Error running event detection: {e}")
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

