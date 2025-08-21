#!/usr/bin/env python3
"""
Irrigation Failure Monitor

Real-time monitoring system that detects irrigation failures and alerts user
when zones are not running as expected, requiring manual intervention to protect plants.

This system:
1. Continuously monitors zone schedules and status via API
2. Detects failures using the rules from failure_detection_rules.py
3. Generates alerts for plant protection
4. Provides manual override capabilities via existing API

Author: AI Assistant
Date: 2025
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from threading import Thread, Event

# Import existing API functionality
from hydrawise_api_explorer import HydrawiseAPIExplorer

# Import configuration
sys.path.append(os.path.join(os.path.dirname(__file__), 'config'))
from failure_detection_rules import (
    FailureType, AlertLevel, FAILURE_DETECTION_RULES, 
    ZONE_FLOW_RATES, get_zone_priority, calculate_water_needed,
    should_alert_for_zone
)

@dataclass
class ZoneStatus:
    """Current status of an irrigation zone"""
    zone_id: int
    name: str
    running: bool
    time_left: str
    last_successful_run: Optional[datetime]
    last_check: datetime
    expected_next_run: Optional[datetime]
    priority: str
    flow_rate_gpm: float
    
@dataclass
class FailureAlert:
    """Alert for detected irrigation failure"""
    alert_id: str
    timestamp: datetime
    zone_id: int
    zone_name: str
    failure_type: FailureType
    alert_level: AlertLevel
    description: str
    action_required: str
    plant_risk: str
    hours_since_last_water: float
    estimated_water_missed: float
    acknowledged: bool = False

class IrrigationMonitor:
    """
    Main monitoring class that detects irrigation failures and generates alerts.
    """
    
    def __init__(self, api_key: str, check_interval_minutes: int = 10):
        """
        Initialize the irrigation monitor.
        
        Args:
            api_key (str): Hydrawise API key
            check_interval_minutes (int): How often to check system status
        """
        self.api_explorer = HydrawiseAPIExplorer(api_key)
        self.check_interval = timedelta(minutes=check_interval_minutes)
        self.zone_status: Dict[int, ZoneStatus] = {}
        self.active_alerts: Dict[str, FailureAlert] = {}
        self.alert_history: List[FailureAlert] = []
        self.running = False
        self.stop_event = Event()
        
        # Setup logging for monitoring
        self.setup_logging()
        
        # Initialize zone information
        self.initialize_zones()
        
    def setup_logging(self):
        """Setup logging for the monitoring system"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('data/irrigation_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def initialize_zones(self):
        """Initialize zone information from API and flow rate data"""
        try:
            self.logger.info("Initializing zone information...")
            
            # Get current status to identify available zones
            status_data = self.api_explorer.get_status_schedule()
            
            if 'relays' in status_data:
                for relay in status_data['relays']:
                    zone_id = relay.get('relay_id')
                    if zone_id:
                        # Get flow rate data if available
                        flow_data = ZONE_FLOW_RATES.get(zone_id, {})
                        
                        self.zone_status[zone_id] = ZoneStatus(
                            zone_id=zone_id,
                            name=relay.get('name', flow_data.get('name', f'Zone {zone_id}')),
                            running=relay.get('running', False),
                            time_left=relay.get('timestr', ''),
                            last_successful_run=None,
                            last_check=datetime.now(),
                            expected_next_run=None,
                            priority=get_zone_priority(zone_id),
                            flow_rate_gpm=flow_data.get('gpm', 0.0)
                        )
                        
            self.logger.info(f"Initialized {len(self.zone_status)} zones")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize zones: {e}")
            
    def parse_next_run_time(self, timestr: str) -> Optional[datetime]:
        """
        Parse next run time from API time string.
        
        Args:
            timestr: Time string from API (e.g., "07:05", "Fri", etc.)
            
        Returns:
            datetime: Estimated next run time or None
        """
        try:
            now = datetime.now()
            
            # If it's a day name, assume it's later this week
            if timestr in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
                return None  # Can't determine exact time
                
            # If it's a time format like "07:05"
            if ':' in timestr:
                time_parts = timestr.split(':')
                if len(time_parts) == 2:
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    
                    # Assume today if time hasn't passed, tomorrow if it has
                    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if next_run <= now:
                        next_run += timedelta(days=1)
                    
                    return next_run
                    
        except Exception as e:
            self.logger.debug(f"Could not parse time string '{timestr}': {e}")
            
        return None
        
    def check_zone_status(self) -> Dict[int, ZoneStatus]:
        """
        Check current status of all zones via API.
        
        Returns:
            dict: Updated zone status information
        """
        try:
            status_data = self.api_explorer.get_status_schedule()
            current_time = datetime.now()
            
            if 'relays' in status_data:
                for relay in status_data['relays']:
                    zone_id = relay.get('relay_id')
                    if zone_id in self.zone_status:
                        zone = self.zone_status[zone_id]
                        
                        # Update current status
                        currently_running = relay.get('running', False)
                        time_left = relay.get('timestr', '')
                        
                        # If zone was running and now stopped, record successful run
                        if zone.running and not currently_running:
                            zone.last_successful_run = current_time
                            self.logger.info(f"Zone {zone_id} ({zone.name}) completed watering")
                            
                        # Update status
                        zone.running = currently_running
                        zone.time_left = time_left
                        zone.last_check = current_time
                        
                        # Parse expected next run
                        if not currently_running and time_left:
                            zone.expected_next_run = self.parse_next_run_time(time_left)
                            
            return self.zone_status
            
        except Exception as e:
            self.logger.error(f"Failed to check zone status: {e}")
            # Generate system offline alert
            self.generate_system_offline_alert()
            return self.zone_status
            
    def detect_failures(self) -> List[FailureAlert]:
        """
        Analyze current zone status to detect failures requiring alerts.
        
        Returns:
            list: New failure alerts generated
        """
        new_alerts = []
        current_time = datetime.now()
        
        for zone_id, zone in self.zone_status.items():
            
            # Skip if we already have active critical alerts for this zone
            existing_critical = any(
                alert.zone_id == zone_id and alert.alert_level == AlertLevel.CRITICAL
                for alert in self.active_alerts.values()
                if not alert.acknowledged
            )
            
            if existing_critical:
                continue
                
            # Check for missed watering window
            if zone.expected_next_run and not zone.running:
                time_since_expected = current_time - zone.expected_next_run
                if time_since_expected > timedelta(hours=2):  # 2 hour grace period
                    
                    hours_since = time_since_expected.total_seconds() / 3600
                    
                    if should_alert_for_zone(zone_id, FailureType.MISSED_WINDOW, hours_since):
                        alert = self.create_alert(
                            zone, FailureType.MISSED_WINDOW, 
                            f"Zone should have run {hours_since:.1f} hours ago"
                        )
                        new_alerts.append(alert)
            
            # Check for extended periods without water
            if zone.last_successful_run:
                time_since_last = current_time - zone.last_successful_run
                hours_since_last = time_since_last.total_seconds() / 3600
                
                # Different thresholds based on priority
                if zone.priority == "HIGH" and hours_since_last > 24:
                    alert = self.create_alert(
                        zone, FailureType.SCHEDULE_GAP,
                        f"High priority zone without water for {hours_since_last:.1f} hours"
                    )
                    new_alerts.append(alert)
                    
                elif zone.priority == "MEDIUM" and hours_since_last > 36:
                    alert = self.create_alert(
                        zone, FailureType.SCHEDULE_GAP,
                        f"Zone without water for {hours_since_last:.1f} hours"
                    )
                    new_alerts.append(alert)
                    
                elif zone.priority == "LOW" and hours_since_last > 48:
                    alert = self.create_alert(
                        zone, FailureType.SCHEDULE_GAP,
                        f"Zone without water for {hours_since_last:.1f} hours"
                    )
                    new_alerts.append(alert)
        
        return new_alerts
        
    def create_alert(self, zone: ZoneStatus, failure_type: FailureType, description: str) -> FailureAlert:
        """
        Create a failure alert for a zone.
        
        Args:
            zone: Zone status information
            failure_type: Type of failure detected
            description: Specific description of the failure
            
        Returns:
            FailureAlert: Generated alert
        """
        rule = FAILURE_DETECTION_RULES[failure_type]
        current_time = datetime.now()
        
        # Calculate hours since last water
        hours_since_last = 0.0
        if zone.last_successful_run:
            hours_since_last = (current_time - zone.last_successful_run).total_seconds() / 3600
            
        # Calculate estimated water missed
        water_missed = calculate_water_needed(zone.zone_id, hours_since_last)
        
        alert_id = f"{zone.zone_id}_{failure_type.value}_{int(current_time.timestamp())}"
        
        return FailureAlert(
            alert_id=alert_id,
            timestamp=current_time,
            zone_id=zone.zone_id,
            zone_name=zone.name,
            failure_type=failure_type,
            alert_level=rule.alert_level,
            description=description,
            action_required=rule.action_required,
            plant_risk=rule.plant_risk,
            hours_since_last_water=hours_since_last,
            estimated_water_missed=water_missed,
            acknowledged=False
        )
        
    def generate_system_offline_alert(self):
        """Generate alert for system connectivity issues"""
        alert_id = f"system_offline_{int(datetime.now().timestamp())}"
        
        alert = FailureAlert(
            alert_id=alert_id,
            timestamp=datetime.now(),
            zone_id=0,  # System-wide alert
            zone_name="SYSTEM",
            failure_type=FailureType.SYSTEM_OFFLINE,
            alert_level=AlertLevel.CRITICAL,
            description="Cannot connect to Hydrawise controller",
            action_required="Check controller power, internet connection, and API status",
            plant_risk="HIGH - Cannot monitor or control irrigation",
            hours_since_last_water=0.0,
            estimated_water_missed=0.0,
            acknowledged=False
        )
        
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
    def process_alerts(self, new_alerts: List[FailureAlert]):
        """
        Process new alerts and add to active alerts.
        
        Args:
            new_alerts: List of newly detected alerts
        """
        for alert in new_alerts:
            self.active_alerts[alert.alert_id] = alert
            self.alert_history.append(alert)
            
            # Log the alert
            self.logger.warning(
                f"{alert.alert_level.value} ALERT: {alert.zone_name} - {alert.description}"
            )
            
            # Save alert to file for external processing
            self.save_alert_to_file(alert)
            
    def save_alert_to_file(self, alert: FailureAlert):
        """Save alert to file for external notification systems"""
        alert_file = f"data/alerts_{datetime.now().strftime('%Y%m%d')}.json"
        
        # Load existing alerts
        alerts_data = []
        if os.path.exists(alert_file):
            try:
                with open(alert_file, 'r') as f:
                    alerts_data = json.load(f)
            except:
                alerts_data = []
        
        # Add new alert
        alert_dict = asdict(alert)
        alert_dict['timestamp'] = alert.timestamp.isoformat()
        alerts_data.append(alert_dict)
        
        # Save updated alerts
        with open(alert_file, 'w') as f:
            json.dump(alerts_data, f, indent=2)
            
    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[FailureAlert]:
        """
        Get current active alerts, optionally filtered by level.
        
        Args:
            level: Alert level to filter by
            
        Returns:
            list: Active alerts
        """
        alerts = [alert for alert in self.active_alerts.values() if not alert.acknowledged]
        
        if level:
            alerts = [alert for alert in alerts if alert.alert_level == level]
            
        return sorted(alerts, key=lambda x: (x.alert_level.value, x.timestamp))
        
    def acknowledge_alert(self, alert_id: str):
        """Mark an alert as acknowledged"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            self.logger.info(f"Alert {alert_id} acknowledged")
            
    def start_monitoring(self):
        """Start the monitoring loop in a background thread"""
        if self.running:
            self.logger.warning("Monitor is already running")
            return
            
        self.running = True
        self.stop_event.clear()
        
        monitor_thread = Thread(target=self._monitoring_loop, daemon=True)
        monitor_thread.start()
        
        self.logger.info("Irrigation monitoring started")
        
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        self.stop_event.set()
        self.logger.info("Irrigation monitoring stopped")
        
    def _monitoring_loop(self):
        """Main monitoring loop (runs in background thread)"""
        while self.running and not self.stop_event.is_set():
            try:
                # Check zone status
                self.check_zone_status()
                
                # Detect failures
                new_alerts = self.detect_failures()
                
                # Process any new alerts
                if new_alerts:
                    self.process_alerts(new_alerts)
                    
                # Sleep until next check
                self.stop_event.wait(self.check_interval.total_seconds())
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                self.stop_event.wait(60)  # Wait 1 minute before retrying
                
    def get_zone_summary(self) -> Dict:
        """Get summary of all zones and their current status"""
        summary = {
            'zones': {},
            'active_alerts_count': len([a for a in self.active_alerts.values() if not a.acknowledged]),
            'critical_alerts': len(self.get_active_alerts(AlertLevel.CRITICAL)),
            'warning_alerts': len(self.get_active_alerts(AlertLevel.WARNING)),
            'last_check': datetime.now().isoformat()
        }
        
        for zone_id, zone in self.zone_status.items():
            summary['zones'][zone_id] = {
                'name': zone.name,
                'running': zone.running,
                'priority': zone.priority,
                'last_successful_run': zone.last_successful_run.isoformat() if zone.last_successful_run else None,
                'expected_next_run': zone.expected_next_run.isoformat() if zone.expected_next_run else None,
                'hours_since_water': (datetime.now() - zone.last_successful_run).total_seconds() / 3600 if zone.last_successful_run else None
            }
            
        return summary

if __name__ == "__main__":
    # Example usage
    print("Irrigation Failure Monitor")
    print("=" * 50)
    
    # Load API key
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    if not api_key:
        print("❌ No API key found. Please set HUNTER_HYDRAWISE_API_KEY in .env file")
        sys.exit(1)
        
    # Create and run monitor
    monitor = IrrigationMonitor(api_key, check_interval_minutes=5)
    
    print(f"✅ Monitor initialized with {len(monitor.zone_status)} zones")
    print("\nZone Information:")
    for zone_id, zone in monitor.zone_status.items():
        print(f"  Zone {zone_id}: {zone.name} ({zone.priority} priority, {zone.flow_rate_gpm} GPM)")
    
    print("\n🔍 Starting monitoring (press Ctrl+C to stop)...")
    
    try:
        monitor.start_monitoring()
        
        # Show status every 30 seconds
        while True:
            time.sleep(30)
            
            summary = monitor.get_zone_summary()
            critical_count = summary['critical_alerts']
            warning_count = summary['warning_alerts']
            
            print(f"\n📊 Status: {critical_count} critical, {warning_count} warning alerts")
            
            # Show any critical alerts
            critical_alerts = monitor.get_active_alerts(AlertLevel.CRITICAL)
            for alert in critical_alerts:
                print(f"🚨 CRITICAL: {alert.zone_name} - {alert.description}")
                
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor...")
        monitor.stop_monitoring()
        print("✅ Monitor stopped")
