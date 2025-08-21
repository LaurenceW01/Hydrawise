#!/usr/bin/env python3
"""
Diagnose Zone Control Issues

This script investigates why zone control commands are returning
"Invalid operation requested" errors.
"""

import os
import json
from dotenv import load_dotenv
from hydrawise_api_explorer import HydrawiseAPIExplorer


def diagnose_zone_control():
    """Diagnose zone control permission and parameter issues."""
    load_dotenv()
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        print("❌ No API key found")
        return
    
    print("🔬 ZONE CONTROL DIAGNOSTICS")
    print("=" * 40)
    
    explorer = HydrawiseAPIExplorer(api_key, respect_rate_limits=True)
    
    # Step 1: Check controller and account info
    print("1️⃣ Checking account and controller status...")
    try:
        customer_data = explorer.get_customer_details()
        
        if 'controllers' in customer_data:
            for controller in customer_data['controllers']:
                print(f"📡 Controller: {controller.get('name', 'Unknown')}")
                print(f"   ID: {controller.get('controller_id')}")
                print(f"   Status: {controller.get('status', 'Unknown')}")
                print(f"   Last Contact: {controller.get('last_contact', 'Unknown')}")
                print(f"   Serial: {controller.get('serial_number', 'Unknown')}")
    except Exception as e:
        print(f"❌ Failed to get controller info: {e}")
        return
    
    # Step 2: Check zone details and permissions
    print("\n2️⃣ Checking zone details...")
    try:
        status_data = explorer.get_status_schedule()
        
        zones = []
        if 'relays' in status_data:
            for i, relay in enumerate(status_data['relays'][:3]):  # Check first 3 zones
                zone_id = relay.get('relay_id')
                zones.append({
                    'id': zone_id,
                    'name': relay.get('name', f'Zone {zone_id}'),
                    'running': relay.get('running', False),
                    'status': relay.get('status', 'Unknown'),
                    'type': relay.get('type', 'Unknown'),
                    'enabled': relay.get('enabled', 'Unknown'),
                    'suspended': relay.get('suspended', 'Unknown')
                })
                
                print(f"🌱 Zone {zone_id}: {relay.get('name', 'Unknown')}")
                print(f"   Status: {relay.get('status', 'Unknown')}")
                print(f"   Running: {relay.get('running', False)}")
                print(f"   Type: {relay.get('type', 'Unknown')}")
                print(f"   Enabled: {relay.get('enabled', 'Unknown')}")
                print(f"   Suspended: {relay.get('suspended', 'Unknown')}")
                
                # Show any other interesting fields
                other_fields = {}
                for key, value in relay.items():
                    if key not in ['relay_id', 'name', 'running', 'status', 'type', 'enabled', 'suspended']:
                        other_fields[key] = value
                
                if other_fields:
                    print(f"   Other fields: {other_fields}")
                print()
    
    except Exception as e:
        print(f"❌ Failed to get zone details: {e}")
        return
    
    # Step 3: Test different zone control parameters
    print("3️⃣ Testing zone control parameters...")
    
    if not zones:
        print("❌ No zones to test")
        return
    
    test_zone = zones[0]  # Use first zone
    zone_id = test_zone['id']
    zone_name = test_zone['name']
    
    print(f"🧪 Testing with zone {zone_id}: {zone_name}")
    
    # Test different parameter combinations
    test_cases = [
        {
            'name': 'Standard run command',
            'params': {'action': 'run', 'period_id': zone_id, 'custom': 1}
        },
        {
            'name': 'Run command with relay_id',
            'params': {'action': 'run', 'relay_id': zone_id, 'custom': 1}
        },
        {
            'name': 'Different duration',
            'params': {'action': 'run', 'period_id': zone_id, 'custom': 5}
        },
        {
            'name': 'Test stop command',
            'params': {'action': 'stop', 'period_id': zone_id}
        },
        {
            'name': 'Test stopall command',
            'params': {'action': 'stopall'}
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🔬 Testing: {test_case['name']}")
        print(f"   Parameters: {test_case['params']}")
        
        try:
            # Make the request manually to see the raw response
            params = test_case['params'].copy()
            params['api_key'] = api_key
            
            url = "https://api.hydrawise.com/api/v1/setzone.php"
            response = explorer.session.get(url, params=params, timeout=30)
            
            print(f"   HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   Response: {data}")
                    
                    if data.get('message_type') == 'error':
                        print(f"   ❌ Error: {data.get('message', 'Unknown error')}")
                    else:
                        print(f"   ✅ Success: {data}")
                        
                except ValueError:
                    print(f"   📄 Raw response: {response.text}")
            else:
                print(f"   ❌ HTTP Error: {response.status_code}")
                print(f"   📄 Response: {response.text}")
        
        except Exception as e:
            print(f"   💥 Exception: {e}")
    
    # Step 4: Check API documentation hints
    print(f"\n4️⃣ Checking for system restrictions...")
    
    # Look for any fields that might indicate restrictions
    if 'options' in status_data:
        print(f"💡 System options: {status_data['options']}")
    
    if 'message' in status_data:
        print(f"💡 System message: {status_data['message']}")
    
    # Check for any controller-level restrictions
    print(f"\n💡 POSSIBLE SOLUTIONS:")
    print(f"1. 🔑 Check if your API key has zone control permissions")
    print(f"2. 📱 Try the same operation in the Hydrawise mobile app")
    print(f"3. 🌐 Check your Hydrawise account settings online")
    print(f"4. 📞 Contact Hydrawise support about API permissions")
    print(f"5. 🔄 Try regenerating your API key")
    print(f"6. ⚙️ Check if controller is in manual/automatic mode")


if __name__ == "__main__":
    diagnose_zone_control()

