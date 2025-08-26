#!/usr/bin/env python3
"""
Zone Flow Monitor - Real-time zone control and flow monitoring

This script allows you to:
1. Start a zone for a specified duration
2. Monitor flow data in real-time while it runs
3. Display detailed water usage when it stops

Author: AI Assistant
Date: 2024
"""

import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from hydrawise_api_explorer import HydrawiseAPIExplorer


class ZoneFlowMonitor:
    """
    Monitor zone operation and flow data in real-time.
    """
    
    def __init__(self, api_key: str):
        """Initialize the zone flow monitor."""
        # FIXED: Use less aggressive rate limiting for better monitoring
        self.explorer = HydrawiseAPIExplorer(api_key, respect_rate_limits=True, aggressive_rate_limiting=False)
        self.zones_info = {}
        self.flow_data_history = []
        self._refresh_system_info()
    
    def _refresh_system_info(self):
        """Get current system information including zones and sensors."""
        try:
            print("[PERIODIC] Refreshing system information...")
            # FIXED: Zones are in statusschedule, not customerdetails
            status_data = self.explorer.get_status_schedule()
            
            # Extract zone information from statusschedule
            zones_found = False
            
            # Zones are in the statusschedule response
            if 'relays' in status_data:
                for relay in status_data['relays']:
                    zone_id = relay.get('relay_id') or relay.get('id')
                    if zone_id:
                        self.zones_info[zone_id] = {
                            'id': zone_id,
                            'name': relay.get('name', f'Zone {zone_id}'),
                            'type': relay.get('type', 'Unknown')
                        }
                        zones_found = True
            
            # If no zones found in customer_data, try status_data
            if not zones_found and 'relays' in status_data:
                for relay in status_data['relays']:
                    zone_id = relay.get('relay_id') or relay.get('id')
                    if zone_id:
                        self.zones_info[zone_id] = {
                            'id': zone_id,
                            'name': relay.get('name', f'Zone {zone_id}'),
                            'type': relay.get('type', 'Unknown')
                        }
                        zones_found = True
            
            # Debug: Show what we actually received
            if not zones_found:
                print("[ANALYSIS] DEBUG: Zone data not found in expected format")
                print("[LOG] Customer data keys:", list(customer_data.keys()) if customer_data else "None")
                print("[LOG] Status data keys:", list(status_data.keys()) if status_data else "None")
                
                # Try to find zones in any nested structure
                self._debug_find_zones(customer_data, "customer_data")
                self._debug_find_zones(status_data, "status_data")
            
            # Add current status
            if 'relays' in status_data:
                for relay in status_data['relays']:
                    zone_id = relay.get('relay_id')
                    if zone_id and zone_id in self.zones_info:
                        self.zones_info[zone_id].update({
                            'running': relay.get('running', False),
                            'time_left': relay.get('timestr', ''),
                            'next_run': relay.get('nextrun', ''),
                            'status': relay.get('status', 'Unknown')
                        })
            
            # Extract sensor information
            self.sensor_info = self._extract_sensor_info(status_data)
            
        except Exception as e:
            print(f"[WARNING] Warning: Could not refresh system info: {e}")
    
    def _debug_find_zones(self, data, data_name):
        """Debug helper to find zone data in any structure."""
        if not data:
            return
            
        print(f"[ANALYSIS] Searching for zones in {data_name}...")
        
        def search_recursive(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # Look for potential zone indicators
                    if any(indicator in key.lower() for indicator in ['relay', 'zone', 'id', 'name']):
                        print(f"   [SYMBOL] Found potential zone data at {current_path}: {value}")
                    
                    # Look for arrays that might contain zones
                    if isinstance(value, list) and len(value) > 0:
                        print(f"   [LOG] Found array at {current_path} with {len(value)} items")
                        if isinstance(value[0], dict):
                            print(f"      First item keys: {list(value[0].keys())}")
                    
                    # Recurse into nested structures
                    if isinstance(value, (dict, list)):
                        search_recursive(value, current_path)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    search_recursive(item, f"{path}[{i}]")
        
        search_recursive(data)
    
    def _extract_sensor_info(self, status_data):
        """Extract flow sensor information from API response."""
        sensors = {}
        
        # Look for sensors in status data
        if 'sensors' in status_data:
            for sensor in status_data['sensors']:
                sensor_type = sensor.get('type')
                if sensor_type == 3:  # Type 3 = Flow sensor
                    input_num = sensor.get('input', 'unknown')
                    sensors[input_num] = {
                        'type': 'flow',
                        'rate': sensor.get('rate', 0),
                        'mode': sensor.get('mode', 0),
                        'timer': sensor.get('timer', 0),
                        'relays': sensor.get('relays', [])
                    }
        
        return sensors
    
    def list_available_zones(self):
        """Display all available zones with their current status."""
        print("\n[SYMBOL] AVAILABLE ZONES")
        print("=" * 50)
        
        if not self.zones_info:
            print("[ERROR] No zones found. Check your system setup.")
            return
        
        for zone_id, info in self.zones_info.items():
            status_icon = "[SYMBOL]" if info.get('running') else "[SYMBOL]"
            print(f"{status_icon} Zone {zone_id}: {info.get('name', 'Unknown')}")
            print(f"   Status: {info.get('status', 'Unknown')}")
            if info.get('running'):
                print(f"   [SCHEDULE] Time Left: {info.get('time_left', 'Unknown')}")
            if info.get('next_run'):
                print(f"   [DATE] Next Run: {info.get('next_run')}")
            print()
    
    def show_flow_sensor_info(self):
        """Display information about detected flow sensors."""
        print("\n[WATER] FLOW SENSOR INFORMATION")
        print("=" * 40)
        
        if not self.sensor_info:
            print("[ERROR] No flow sensors detected")
            return
        
        for input_num, sensor in self.sensor_info.items():
            print(f"[RESULTS] Flow Sensor (Input {input_num}):")
            print(f"   Rate: {sensor['rate']} (units/minute)")
            print(f"   Mode: {sensor['mode']}")
            print(f"   Connected Zones: {len(sensor.get('relays', []))}")
            print()
    
    def start_zone_with_monitoring(self, zone_id: int, duration_minutes: int):
        """Start a zone and monitor it until completion."""
        if zone_id not in self.zones_info:
            print(f"[ERROR] Zone {zone_id} not found. Available zones:")
            self.list_available_zones()
            return
        
        zone_name = self.zones_info[zone_id].get('name', f'Zone {zone_id}')
        
        print(f"\n[SYMBOL] STARTING ZONE MONITORING")
        print("=" * 40)
        print(f"Zone: {zone_name} (ID: {zone_id})")
        print(f"Duration: {duration_minutes} minutes")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get baseline readings before starting
        print("\n[RESULTS] Getting baseline readings...")
        baseline_data = self._get_current_readings()
        
        # Start the zone
        try:
            print(f"\n[SYMBOL] Starting zone {zone_id}...")
            result = self.explorer.start_zone(zone_id, duration_minutes)
            print("[OK] Zone started successfully!")
            
        except Exception as e:
            print(f"[ERROR] Failed to start zone: {e}")
            return
        
        # Monitor the zone
        self._monitor_zone_operation(zone_id, duration_minutes, baseline_data)
    
    def _get_current_readings(self):
        """Get current system readings including flow data."""
        try:
            status_data = self.explorer.get_status_schedule()
            
            readings = {
                'timestamp': datetime.now(),
                'zones': {},
                'sensors': {},
                'raw_data': status_data
            }
            
            # Extract zone status
            if 'relays' in status_data:
                for relay in status_data['relays']:
                    zone_id = relay.get('relay_id')
                    if zone_id:
                        readings['zones'][zone_id] = {
                            'running': relay.get('running', False),
                            'time_left': relay.get('timestr', ''),
                            'status': relay.get('status', 'Unknown')
                        }
            
            # Extract sensor data
            if 'sensors' in status_data:
                for sensor in status_data['sensors']:
                    input_num = sensor.get('input', 'unknown')
                    readings['sensors'][input_num] = sensor
            
            return readings
            
        except Exception as e:
            print(f"[WARNING] Error getting readings: {e}")
            return {'timestamp': datetime.now(), 'zones': {}, 'sensors': {}}
    
    def _monitor_zone_operation(self, zone_id: int, duration_minutes: int, baseline_data: dict):
        """Monitor zone operation in real-time."""
        zone_name = self.zones_info[zone_id].get('name', f'Zone {zone_id}')
        expected_end_time = time.time() + (duration_minutes * 60)
        
        print(f"\n[SCHEDULE] MONITORING ZONE OPERATION")
        print("=" * 40)
        print("Press Ctrl+C to stop monitoring early")
        print()
        
        monitoring_data = []
        last_status_check = 0
        check_interval = 15  # Check every 15 seconds
        
        try:
            while time.time() < expected_end_time:
                current_time = time.time()
                
                # Rate-limited status checks
                if current_time - last_status_check >= check_interval:
                    print(f"[RESULTS] Checking status... ({datetime.now().strftime('%H:%M:%S')})")
                    
                    readings = self._get_current_readings()
                    monitoring_data.append(readings)
                    
                    # Display current status
                    zone_status = readings['zones'].get(zone_id, {})
                    if zone_status.get('running'):
                        time_left = zone_status.get('time_left', 'Unknown')
                        print(f"   [SYMBOL] Zone {zone_name} running - Time left: {time_left}")
                        
                        # Show any flow data
                        self._display_current_flow_data(readings)
                    else:
                        print(f"   [SYMBOL] Zone {zone_name} not running - may have finished early")
                        break
                    
                    last_status_check = current_time
                
                # Wait before next check
                time.sleep(5)
        
        except KeyboardInterrupt:
            print("\n[CANCELLED] Monitoring stopped by user")
        
        # Get final readings
        print(f"\n[RESULTS] Getting final readings...")
        final_data = self._get_current_readings()
        monitoring_data.append(final_data)
        
        # Analyze and display results
        self._analyze_monitoring_results(zone_id, baseline_data, monitoring_data, final_data)
    
    def _display_current_flow_data(self, readings):
        """Display current flow data from readings."""
        if 'sensors' in readings:
            for input_num, sensor in readings['sensors'].items():
                if sensor.get('type') == 3:  # Flow sensor
                    rate = sensor.get('rate', 0)
                    timer = sensor.get('timer', 0)
                    print(f"   [WATER] Flow Rate: {rate} units/min, Timer: {timer}")
    
    def _analyze_monitoring_results(self, zone_id: int, baseline_data: dict, monitoring_data: list, final_data: dict):
        """Analyze and display the monitoring results."""
        zone_name = self.zones_info[zone_id].get('name', f'Zone {zone_id}')
        
        print(f"\n[SYMBOL] MONITORING RESULTS FOR {zone_name}")
        print("=" * 50)
        
        # Basic operation info
        start_time = baseline_data['timestamp']
        end_time = final_data['timestamp']
        duration = end_time - start_time
        
        print(f"[TIME] Operation Duration: {duration.total_seconds()/60:.1f} minutes")
        print(f"[SYMBOL] Start Time: {start_time.strftime('%H:%M:%S')}")
        print(f"[SYMBOL] End Time: {end_time.strftime('%H:%M:%S')}")
        
        # Flow analysis
        print(f"\n[WATER] FLOW DATA ANALYSIS")
        print("-" * 30)
        
        # Look for flow data in monitoring results
        flow_readings = []
        for reading in monitoring_data:
            if 'sensors' in reading:
                for input_num, sensor in reading['sensors'].items():
                    if sensor.get('type') == 3:  # Flow sensor
                        flow_readings.append({
                            'timestamp': reading['timestamp'],
                            'rate': sensor.get('rate', 0),
                            'timer': sensor.get('timer', 0),
                            'mode': sensor.get('mode', 0)
                        })
        
        if flow_readings:
            print(f"[RESULTS] Flow readings collected: {len(flow_readings)}")
            
            # Calculate statistics
            rates = [r['rate'] for r in flow_readings if r['rate'] > 0]
            if rates:
                avg_rate = sum(rates) / len(rates)
                max_rate = max(rates)
                min_rate = min(rates)
                
                print(f"   Average Flow Rate: {avg_rate:.2f} units/min")
                print(f"   Maximum Flow Rate: {max_rate:.2f} units/min")
                print(f"   Minimum Flow Rate: {min_rate:.2f} units/min")
                
                # Estimate total water usage
                total_minutes = duration.total_seconds() / 60
                estimated_usage = avg_rate * total_minutes
                print(f"   Estimated Total Usage: {estimated_usage:.2f} units")
            else:
                print("   [WARNING] No positive flow rates detected")
            
            # Show detailed readings
            print(f"\n[LOG] DETAILED FLOW READINGS")
            print("-" * 30)
            for reading in flow_readings[-5:]:  # Show last 5 readings
                time_str = reading['timestamp'].strftime('%H:%M:%S')
                print(f"   {time_str}: Rate={reading['rate']:.2f}, Timer={reading['timer']}")
        else:
            print("[ERROR] No flow data collected during monitoring")
            print("[INFO] This might mean:")
            print("   - Flow meter is not properly configured")
            print("   - Zone is not connected to flow meter")
            print("   - Flow data is reported differently")
        
        # Save detailed log
        self._save_monitoring_log(zone_id, baseline_data, monitoring_data, final_data)
    
    def _save_monitoring_log(self, zone_id: int, baseline_data: dict, monitoring_data: list, final_data: dict):
        """Save detailed monitoring log to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"zone_{zone_id}_monitoring_{timestamp}.json"
        
        log_data = {
            'zone_id': zone_id,
            'zone_name': self.zones_info[zone_id].get('name', f'Zone {zone_id}'),
            'baseline_data': self._serialize_datetime(baseline_data),
            'monitoring_data': [self._serialize_datetime(data) for data in monitoring_data],
            'final_data': self._serialize_datetime(final_data)
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(log_data, f, indent=2)
            print(f"\n[SAVED] Detailed log saved to: {filename}")
        except Exception as e:
            print(f"[WARNING] Could not save log: {e}")
    
    def _serialize_datetime(self, data):
        """Convert datetime objects to strings for JSON serialization."""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif isinstance(value, dict):
                    result[key] = self._serialize_datetime(value)
                elif isinstance(value, list):
                    result[key] = [self._serialize_datetime(item) if isinstance(item, dict) else item for item in value]
                else:
                    result[key] = value
            return result
        return data


def main():
    """Main function for zone flow monitoring."""
    print("[WATER] HYDRAWISE ZONE FLOW MONITOR")
    print("=" * 40)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        print("[ERROR] No API key found in .env file")
        return
    
    print(f"[OK] API key loaded: {api_key[:8]}..." + "*" * (len(api_key) - 8))
    
    # Initialize monitor
    monitor = ZoneFlowMonitor(api_key)
    
    # Show system info
    monitor.show_flow_sensor_info()
    monitor.list_available_zones()
    
    # Interactive zone selection
    try:
        zone_id = int(input("\n[SYMBOL] Enter zone ID to run and monitor: "))
        duration = int(input("[SCHEDULE] Enter duration in minutes: "))
        
        confirm = input(f"\n[WARNING] Start zone {zone_id} for {duration} minutes? (yes/no): ").lower().strip()
        if confirm == 'yes':
            monitor.start_zone_with_monitoring(zone_id, duration)
        else:
            print("[ERROR] Operation cancelled")
    
    except KeyboardInterrupt:
        print("\n[SYMBOL] Goodbye!")
    except ValueError:
        print("[ERROR] Invalid input. Please enter numbers only.")
    except Exception as e:
        print(f"[ERROR] Error: {e}")


if __name__ == "__main__":
    main()
