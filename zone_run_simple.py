#!/usr/bin/env python3
"""
Simple Zone Runner with Flow Monitoring

A simplified approach to run zones and monitor flow data.
This script focuses on reliability and clear feedback.

Author: AI Assistant
Date: 2024
"""

import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from hydrawise_api_explorer import HydrawiseAPIExplorer


def get_zone_list(explorer):
    """Get list of all available zones."""
    try:
        print("[ANALYSIS] Getting zone list...")
        
        # FIXED: Zones are in statusschedule, not customerdetails
        status_data = explorer.get_status_schedule()
        
        zones = {}
        
        # Extract from status data (where zones actually are)
        if 'relays' in status_data:
            for relay in status_data['relays']:
                zone_id = relay.get('relay_id')
                if zone_id:
                    zones[zone_id] = {
                        'id': zone_id,
                        'name': relay.get('name', f'Zone {zone_id}'),
                        'running': relay.get('running', False),
                        'time_left': relay.get('timestr', '')
                    }
        
        # Status information is already included above since we're getting from statusschedule
        
        return zones
        
    except Exception as e:
        print(f"[ERROR] Error getting zones: {e}")
        return {}


def show_zone_status(explorer):
    """Show current status of all zones."""
    zones = get_zone_list(explorer)
    
    if not zones:
        print("[ERROR] No zones found")
        return zones
    
    print("\n[SYMBOL] CURRENT ZONE STATUS")
    print("=" * 50)
    
    running_zones = []
    idle_zones = []
    
    for zone_id, info in zones.items():
        if info['running']:
            running_zones.append(info)
        else:
            idle_zones.append(info)
    
    if running_zones:
        print("[SYMBOL] CURRENTLY RUNNING:")
        for zone in running_zones:
            print(f"   [WATER] Zone {zone['id']}: {zone['name']}")
            print(f"      Time left: {zone.get('time_left', 'Unknown')}")
    
    if idle_zones:
        print(f"\n[SYMBOL] IDLE ZONES ({len(idle_zones)} available):")
        for zone in idle_zones[:10]:  # Show first 10
            print(f"   Zone {zone['id']}: {zone['name']}")
        
        if len(idle_zones) > 10:
            print(f"   ... and {len(idle_zones) - 10} more zones")
    
    return zones


def get_flow_sensor_info(explorer):
    """Get flow sensor information."""
    try:
        status_data = explorer.get_status_schedule()
        
        flow_sensors = {}
        if 'sensors' in status_data:
            for sensor in status_data['sensors']:
                if sensor.get('type') == 3:  # Flow sensor
                    input_num = sensor.get('input', 'unknown')
                    flow_sensors[input_num] = {
                        'rate': sensor.get('rate', 0),
                        'mode': sensor.get('mode', 0),
                        'timer': sensor.get('timer', 0),
                        'connected_zones': len(sensor.get('relays', []))
                    }
        
        return flow_sensors
        
    except Exception as e:
        print(f"[ERROR] Error getting flow sensors: {e}")
        return {}


def start_zone_and_wait(explorer, zone_id, duration_minutes):
    """Start a zone and wait for it to begin running."""
    print(f"\n[SYMBOL] STARTING ZONE {zone_id}")
    print("=" * 40)
    
    # Get zone info
    zones = get_zone_list(explorer)
    if zone_id not in zones:
        print(f"[ERROR] Zone {zone_id} not found")
        return False
    
    zone_name = zones[zone_id]['name']
    print(f"Zone: {zone_name}")
    print(f"Duration: {duration_minutes} minutes")
    
    # Check if zone is already running
    if zones[zone_id]['running']:
        print(f"[WARNING] Zone is already running! Time left: {zones[zone_id]['time_left']}")
        response = input("Continue anyway? (y/n): ").lower().strip()
        if response != 'y':
            return False
    
    try:
        # Start the zone
        print(f"[SYMBOL] Sending start command...")
        result = explorer.start_zone(zone_id, duration_minutes)
        print(f"[OK] Command sent successfully")
        
        # Wait a moment for the command to take effect
        print("[SYMBOL] Waiting 10 seconds for zone to start...")
        time.sleep(10)
        
        # Check if zone actually started
        print("[ANALYSIS] Verifying zone started...")
        zones_updated = get_zone_list(explorer)
        
        if zone_id in zones_updated and zones_updated[zone_id]['running']:
            print(f"[OK] Zone {zone_name} is now running!")
            print(f"[SCHEDULE] Time left: {zones_updated[zone_id]['time_left']}")
            return True
        else:
            print(f"[ERROR] Zone did not start running")
            print("[INFO] Possible reasons:")
            print("   - Zone may be disabled or suspended")
            print("   - Controller may be offline") 
            print("   - System may have restrictions")
            
            # Show what the API returned
            print(f"\n[LOG] API Response: {result}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error starting zone: {e}")
        return False


def monitor_zone_simple(explorer, zone_id, check_interval=30):
    """Simple zone monitoring with flow data."""
    zones = get_zone_list(explorer)
    if zone_id not in zones:
        print(f"[ERROR] Zone {zone_id} not found")
        return
    
    zone_name = zones[zone_id]['name']
    
    print(f"\n[SCHEDULE] MONITORING ZONE {zone_name}")
    print("=" * 40)
    print("Press Ctrl+C to stop monitoring")
    print(f"Checking every {check_interval} seconds")
    
    flow_readings = []
    start_time = datetime.now()
    
    try:
        while True:
            print(f"\n[RESULTS] Status check at {datetime.now().strftime('%H:%M:%S')}")
            
            # Get current zone status
            zones_current = get_zone_list(explorer)
            flow_sensors = get_flow_sensor_info(explorer)
            
            # Check zone status
            if zone_id in zones_current:
                zone_info = zones_current[zone_id]
                if zone_info['running']:
                    print(f"   [SYMBOL] {zone_name} is running")
                    print(f"   [SCHEDULE] Time left: {zone_info.get('time_left', 'Unknown')}")
                    
                    # Record flow data
                    for sensor_input, sensor_info in flow_sensors.items():
                        flow_reading = {
                            'timestamp': datetime.now(),
                            'sensor_input': sensor_input,
                            'rate': sensor_info['rate'],
                            'timer': sensor_info['timer'],
                            'mode': sensor_info['mode']
                        }
                        flow_readings.append(flow_reading)
                        
                        print(f"   [WATER] Flow Sensor {sensor_input}: {sensor_info['rate']:.2f} units/min")
                        if sensor_info['timer'] > 0:
                            print(f"   [RESULTS] Flow Timer: {sensor_info['timer']}")
                
                else:
                    print(f"   [SYMBOL] {zone_name} has stopped running")
                    break
            else:
                print(f"   [ERROR] Could not get status for zone {zone_id}")
            
            # Wait before next check
            time.sleep(check_interval)
    
    except KeyboardInterrupt:
        print("\n[CANCELLED] Monitoring stopped by user")
    
    # Show results
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n[SYMBOL] MONITORING SUMMARY")
    print("=" * 30)
    print(f"[TIME] Total monitoring time: {duration.total_seconds()/60:.1f} minutes")
    print(f"[RESULTS] Flow readings collected: {len(flow_readings)}")
    
    if flow_readings:
        # Calculate flow statistics
        rates = [r['rate'] for r in flow_readings if r['rate'] > 0]
        if rates:
            avg_rate = sum(rates) / len(rates)
            max_rate = max(rates)
            min_rate = min(rates)
            total_estimated = avg_rate * (duration.total_seconds() / 60)
            
            print(f"\n[WATER] FLOW ANALYSIS:")
            print(f"   Average rate: {avg_rate:.2f} units/min")
            print(f"   Max rate: {max_rate:.2f} units/min") 
            print(f"   Min rate: {min_rate:.2f} units/min")
            print(f"   Estimated total: {total_estimated:.2f} units")
        
        # Show recent readings
        print(f"\n[LOG] RECENT READINGS:")
        for reading in flow_readings[-5:]:
            time_str = reading['timestamp'].strftime('%H:%M:%S')
            print(f"   {time_str}: {reading['rate']:.2f} units/min")
        
        # Save detailed log
        save_monitoring_log(zone_id, zone_name, flow_readings, start_time, end_time)
    
    else:
        print("[WARNING] No flow data collected")


def save_monitoring_log(zone_id, zone_name, flow_readings, start_time, end_time):
    """Save monitoring results to a file."""
    timestamp = start_time.strftime('%Y%m%d_%H%M%S')
    filename = f"zone_{zone_id}_flow_log_{timestamp}.json"
    
    log_data = {
        'zone_id': zone_id,
        'zone_name': zone_name,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'duration_minutes': (end_time - start_time).total_seconds() / 60,
        'flow_readings': [
            {
                'timestamp': r['timestamp'].isoformat(),
                'sensor_input': r['sensor_input'],
                'rate': r['rate'],
                'timer': r['timer'],
                'mode': r['mode']
            }
            for r in flow_readings
        ]
    }
    
    try:
        with open(filename, 'w') as f:
            json.dump(log_data, f, indent=2)
        print(f"[SAVED] Flow log saved to: {filename}")
    except Exception as e:
        print(f"[WARNING] Could not save log: {e}")


def main():
    """Main function."""
    print("[WATER] SIMPLE HYDRAWISE ZONE RUNNER")
    print("=" * 40)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        print("[ERROR] No API key found in .env file")
        return
    
    print(f"[OK] API key loaded")
    
    # FIXED: Initialize explorer with less aggressive rate limiting
    explorer = HydrawiseAPIExplorer(api_key, respect_rate_limits=True, aggressive_rate_limiting=False)
    
    # Show current system status
    print("\n[ANALYSIS] Checking system status...")
    zones = show_zone_status(explorer)
    
    if not zones:
        print("[ERROR] No zones available")
        return
    
    # Show flow sensors
    flow_sensors = get_flow_sensor_info(explorer)
    if flow_sensors:
        print(f"\n[WATER] FLOW SENSORS DETECTED:")
        for input_num, sensor in flow_sensors.items():
            print(f"   Sensor {input_num}: {sensor['rate']:.2f} units/min ({sensor['connected_zones']} zones)")
    else:
        print("\n[WARNING] No flow sensors detected")
    
    # Interactive zone selection
    try:
        print(f"\n[SYMBOL] ZONE SELECTION")
        zone_id = int(input("Enter zone ID to run: "))
        duration = int(input("Enter duration in minutes: "))
        
        # Confirm
        if zone_id in zones:
            zone_name = zones[zone_id]['name']
            print(f"\n[WARNING] About to start: {zone_name} for {duration} minutes")
            confirm = input("Proceed? (yes/no): ").lower().strip()
            
            if confirm == 'yes':
                # Start zone and verify
                if start_zone_and_wait(explorer, zone_id, duration):
                    # Monitor the zone
                    monitor_zone_simple(explorer, zone_id, check_interval=20)
                else:
                    print("[ERROR] Zone did not start - cannot monitor")
            else:
                print("[ERROR] Operation cancelled")
        else:
            print(f"[ERROR] Zone {zone_id} not found")
    
    except KeyboardInterrupt:
        print("\n[SYMBOL] Goodbye!")
    except ValueError:
        print("[ERROR] Invalid input. Please enter numbers only.")
    except Exception as e:
        print(f"[ERROR] Error: {e}")


if __name__ == "__main__":
    main()
