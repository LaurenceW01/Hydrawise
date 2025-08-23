#!/usr/bin/env python3
"""
Debug Flow Readings - Investigate flow meter behavior
"""

import os
import time
import json
from dotenv import load_dotenv
from hydrawise_api_explorer import HydrawiseAPIExplorer

def debug_flow_readings():
    """Debug flow meter readings during different states."""
    print("🔍 DEBUGGING FLOW METER READINGS")
    print("=" * 60)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        print("❌ No API key found")
        return
    
    explorer = HydrawiseAPIExplorer(api_key, respect_rate_limits=True, aggressive_rate_limiting=False)
    
    try:
        # Step 1: Get readings when ALL zones are idle
        print("\n📊 Step 1: Baseline - All zones idle")
        idle_data = explorer.get_status_schedule()
        
        # Show ALL sensor data, not just flow meters
        if 'sensors' in idle_data:
            print(f"🔍 Found {len(idle_data['sensors'])} sensors:")
            for i, sensor in enumerate(idle_data['sensors']):
                print(f"\n   Sensor {i} (Input {sensor.get('input', 'Unknown')}):")
                print(f"     Type: {sensor.get('type')} ({get_sensor_type_name(sensor.get('type'))})")
                print(f"     Mode: {sensor.get('mode')}")
                print(f"     Timer: {sensor.get('timer', 0)} seconds")
                print(f"     Off Timer: {sensor.get('offtimer', 0)} seconds")
                if 'rate' in sensor:
                    print(f"     Rate: {sensor.get('rate')} GPM")
                print(f"     All fields: {list(sensor.keys())}")
        
        # Step 2: Start a zone and monitor readings
        zone_id = 2419310  # Zone 1
        print(f"\n🚿 Step 2: Starting zone {zone_id} for 1 minute...")
        start_result = explorer.start_zone(zone_id, 1)
        print(f"Start result: {start_result.get('message', 'No message')}")
        
        # Check readings every 10 seconds for 1 minute
        for check_num in range(6):  # 6 checks over 60 seconds
            wait_time = 10
            print(f"\n⏱️ Check {check_num + 1}/6 - Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            
            print(f"📊 Getting readings at {(check_num + 1) * wait_time} seconds...")
            current_data = explorer.get_status_schedule()
            
            # Show sensor readings during operation
            if 'sensors' in current_data:
                for i, sensor in enumerate(current_data['sensors']):
                    if sensor.get('type') == 3:  # Flow meter
                        print(f"   Flow Meter {i}: Rate = {sensor.get('rate', 0)} GPM, Timer = {sensor.get('timer', 0)}s")
                    elif 'rate' in sensor:
                        print(f"   Sensor {i}: Rate = {sensor.get('rate', 0)}, Timer = {sensor.get('timer', 0)}s")
            
            # Check zone status
            if 'relays' in current_data:
                for relay in current_data['relays']:
                    if relay.get('relay_id') == zone_id:
                        running = relay.get('running')
                        timestr = relay.get('timestr', '')
                        print(f"   Zone {zone_id}: Running={running}, TimeLeft='{timestr}'")
                        break
        
        print(f"\n🛑 Zone {zone_id} should have finished by now...")
        
        # Step 3: Final readings after zone stops
        print("\n📊 Step 3: Final readings after zone stops...")
        time.sleep(10)  # Wait a bit more
        final_data = explorer.get_status_schedule()
        
        if 'sensors' in final_data:
            for i, sensor in enumerate(final_data['sensors']):
                if sensor.get('type') == 3:  # Flow meter
                    print(f"   Final Flow Meter {i}: Rate = {sensor.get('rate', 0)} GPM, Timer = {sensor.get('timer', 0)}s")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def get_sensor_type_name(sensor_type):
    """Get human-readable sensor type name."""
    types = {
        1: "Soil Moisture/Other",
        2: "Temperature", 
        3: "Flow Meter",
        4: "Rain Sensor"
    }
    return types.get(sensor_type, f"Unknown ({sensor_type})")

if __name__ == "__main__":
    debug_flow_readings()





