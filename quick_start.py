#!/usr/bin/env python3
"""
Quick Start Script for Hydrawise API

This script provides a simple way to immediately test your Hydrawise API setup
and get basic information about your system.

Author: AI Assistant  
Date: 2024
"""

import os
from dotenv import load_dotenv
from hydrawise_api_explorer import HydrawiseAPIExplorer


def quick_start():
    """
    Quick start function to test API connectivity and show basic info.
    """
    print("[SYMBOL] HYDRAWISE API QUICK START")
    print("=" * 40)
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get API key from environment variable
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        print("[ERROR] No API key found!")
        print("\n[SYMBOL] Setup Instructions:")
        print("1. Create a .env file in this directory")
        print("2. Add this line: HUNTER_HYDRAWISE_API_KEY=your_actual_key_here")
        print("3. Get your API key from Hydrawise account settings")
        print("4. Run this script again")
        return
    
    print(f"[OK] API key found: {api_key[:8]}..." + "*" * (len(api_key) - 8))
    
    # Initialize explorer
    explorer = HydrawiseAPIExplorer(api_key)
    
    try:
        print("\n[ANALYSIS] Testing API connection...")
        
        # Get customer details
        customer_data = explorer.get_customer_details()
        print("[OK] Successfully connected to Hydrawise API!")
        
        # Analyze the response to show basic info
        print("\n[RESULTS] YOUR HYDRAWISE SYSTEM:")
        print("-" * 30)
        
        # Extract controller info
        if 'controllers' in customer_data:
            controllers = customer_data['controllers']
            print(f"[SYMBOL] Controllers found: {len(controllers)}")
            
            for controller in controllers:
                print(f"   [SYMBOL] {controller.get('name', 'Unknown Controller')}")
                print(f"      ID: {controller.get('controller_id', 'Unknown')}")
                print(f"      Status: {controller.get('status', 'Unknown')}")
        
        # Extract zone info  
        if 'relays' in customer_data:
            zones = customer_data['relays']
            print(f"\n[SYMBOL] Zones found: {len(zones)}")
            
            for zone in zones:
                zone_id = zone.get('relay_id', 'Unknown')
                zone_name = zone.get('name', f'Zone {zone_id}')
                zone_type = zone.get('type', 'Unknown')
                print(f"   [WATER] {zone_name} (ID: {zone_id}, Type: {zone_type})")
        
        # Get current status
        print("\n[SCHEDULE] Getting current status...")
        status_data = explorer.get_status_schedule()
        
        if 'relays' in status_data:
            running_zones = []
            upcoming_zones = []
            
            for relay in status_data['relays']:
                if relay.get('running'):
                    running_zones.append({
                        'name': relay.get('name', 'Unknown'),
                        'time_left': relay.get('timestr', 'Unknown')
                    })
                
                next_run = relay.get('nextrun')
                if next_run and next_run != 'Not scheduled':
                    upcoming_zones.append({
                        'name': relay.get('name', 'Unknown'),
                        'next_run': next_run
                    })
            
            print(f"\n[SYMBOL] Currently running: {len(running_zones)} zones")
            for zone in running_zones:
                print(f"   [SYMBOL][SYMBOL] {zone['name']} - {zone['time_left']} remaining")
            
            if not running_zones:
                print("   [SYMBOL] No zones currently running")
            
            print(f"\n[DATE] Upcoming runs: {len(upcoming_zones)} zones scheduled")
            for zone in upcoming_zones[:3]:  # Show first 3
                print(f"   [SCHEDULE] {zone['name']} - {zone['next_run']}")
            
            if len(upcoming_zones) > 3:
                print(f"   ... and {len(upcoming_zones) - 3} more")
        
        # Try to detect flow meter
        print("\n[WATER] Checking for flow meter data...")
        
        # Look for flow-related fields in the responses
        flow_indicators = ['flow', 'water_used', 'flow_rate', 'sensor']
        flow_found = False
        
        def check_for_flow_data(data, prefix=""):
            """Recursively check for flow-related data in responses."""
            nonlocal flow_found
            
            if isinstance(data, dict):
                for key, value in data.items():
                    if any(indicator in key.lower() for indicator in flow_indicators):
                        print(f"   [ANALYSIS] Found potential flow data: {prefix}{key} = {value}")
                        flow_found = True
                    elif isinstance(value, (dict, list)):
                        check_for_flow_data(value, f"{prefix}{key}.")
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    check_for_flow_data(item, f"{prefix}[{i}].")
        
        check_for_flow_data(customer_data)
        check_for_flow_data(status_data)
        
        if not flow_found:
            print("   [INFO] No flow meter data detected in basic responses")
            print("   [INFO] Flow data may be available through:")
            print("      - GraphQL API (requires special access)")
            print("      - Real-time monitoring during zone runs")
            print("      - Dedicated flow meter endpoints")
        
        print("\n[OK] QUICK START COMPLETE!")
        print("\n[SYMBOL] Next Steps:")
        print("   1. Run 'python hydrawise_api_explorer.py' for full exploration")
        print("   2. Run 'python hydrawise_zone_control_examples.py' for zone control")
        print("   3. Check the README.md for detailed usage instructions")
        
    except Exception as e:
        print(f"[ERROR] Error connecting to Hydrawise API: {e}")
        print("\n[SYMBOL] Troubleshooting:")
        print("   1. Check your API key is correct")
        print("   2. Verify your internet connection")
        print("   3. Make sure your Hydrawise account is active")
        print("   4. Try generating a new API key from Hydrawise settings")


if __name__ == "__main__":
    quick_start()

