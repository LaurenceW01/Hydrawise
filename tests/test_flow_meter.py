#!/usr/bin/env python3
"""
Test Flow Meter Detection
Simple script to test if flow meter data is available.
"""

import os
from dotenv import load_dotenv
from hydrawise_api_explorer import HydrawiseAPIExplorer

def test_flow_meter():
    """Test flow meter detection with zone 1 (ID 2419310)."""
    print("[SYMBOL] TESTING FLOW METER DETECTION - ZONE 1 (2419310)")
    print("=" * 60)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        print("[SYMBOL] No API key found in .env file")
        return
    
    print(f"[SYMBOL] API key loaded: {api_key[:8]}...")
    
    # Initialize explorer
    explorer = HydrawiseAPIExplorer(api_key, respect_rate_limits=True, aggressive_rate_limiting=False)
    
    zone_id = 2419310  # Zone 1: Front Right Tur
    
    try:
        # Step 1: Get baseline flow data
        print("\n[SYMBOL] Step 1: Getting baseline status...")
        baseline_data = explorer.get_status_schedule()
        baseline_flow = explorer.get_flow_meter_data(baseline_data)
        
        if baseline_flow:
            print("[SYMBOL] Flow meter detected in baseline!")
            for sensor_id, data in baseline_flow.items():
                print(f"   Sensor {sensor_id}: Rate = {data.get('rate', 0)} GPM")
        else:
            print("[SYMBOL] No flow meter in baseline")
        
        # Step 2: Start zone 1 for 1 minute ONLY
        print(f"\n[SYMBOL] Step 2: Starting zone {zone_id} (Front Right Tur) for 1 minute...")
        start_result = explorer.start_zone(zone_id, 1)
        print(f"Start result: {start_result.get('message', 'No message')}")
        
        # Step 3: Wait a moment then check flow during operation
        import time
        print("\n[SYMBOL] Step 3: Waiting 20 seconds for zone to start...")
        time.sleep(20)
        
        print("[SYMBOL] Getting status during zone operation...")
        running_data = explorer.get_status_schedule()
        running_flow = explorer.get_flow_meter_data(running_data)
        
        if running_flow:
            print("[SYMBOL] Flow meter data during operation!")
            for sensor_id, data in running_flow.items():
                print(f"   Sensor {sensor_id}: Rate = {data.get('rate', 0)} GPM")
                print(f"   Timer: {data.get('timer', 0)} seconds")
        else:
            print("[SYMBOL] No flow meter data during operation")
        
        # Step 4: Check zone status
        print(f"\n[SYMBOL] Step 4: Checking zone {zone_id} status...")
        if 'relays' in running_data:
            for relay in running_data['relays']:
                if relay.get('relay_id') == zone_id:
                    print(f"   Zone Name: {relay.get('name')}")
                    print(f"   Running: {relay.get('running')}")
                    print(f"   Time Left: {relay.get('timestr')}")
                    break
        
        flow_data = running_flow if running_flow else baseline_flow
        
        if flow_data:
            print("\n[SYMBOL] FLOW METER DATA FOUND!")
            print("=" * 30)
            for sensor_id, data in flow_data.items():
                print(f"\n[SYMBOL] Flow Meter {sensor_id}:")
                print(f"   Input: {data.get('input')}")
                print(f"   Type: {data.get('type')} (3 = Flow Meter)")
                print(f"   Mode: {data.get('mode')}")
                print(f"   Current Rate: {data.get('rate', 0)} GPM")
                print(f"   Timer: {data.get('timer', 0)} seconds")
                print(f"   Off Timer: {data.get('offtimer', 0)} seconds")
                print(f"   Connected Zones: {len(data.get('relays', []))}")
                
                if data.get('relays'):
                    print("   Zone IDs:")
                    for relay in data.get('relays', []):
                        print(f"     - {relay.get('id')}")
        else:
            print("\n[SYMBOL] NO FLOW METER DATA FOUND")
            print("[SYMBOL] Possible reasons:")
            print("   - No HC Flow Meter connected")
            print("   - Flow meter not configured in Hydrawise")
            print("   - Different sensor type or API structure")
            
            # Debug: Show what sensors we did find
            if 'sensors' in status_data:
                print(f"\n[SYMBOL] DEBUG: Found {len(status_data['sensors'])} sensors:")
                for sensor_id, sensor in status_data['sensors'].items():
                    sensor_type = sensor.get('type', 'Unknown')
                    print(f"   Sensor {sensor_id}: Type {sensor_type}")
                    if sensor_type == 1:
                        print(f"     (Type 1 = Soil moisture or other sensor)")
                    elif sensor_type == 3:
                        print(f"     (Type 3 = Flow meter - should be detected!)")
                    else:
                        print(f"     (Unknown sensor type)")
            else:
                print("   - No 'sensors' section found in API response")
    
    except Exception as e:
        print(f"\n[SYMBOL] Error testing flow meter: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_flow_meter()
