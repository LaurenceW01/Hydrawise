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
import threading
from datetime import datetime, timedelta
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
                    # Debug: Show RAW relay data from API before processing
                    raw_running = relay.get('running')
                    raw_timestr = relay.get('timestr')
                    
                    zones[zone_id] = {
                        'id': zone_id,
                        'name': relay.get('name', f'Zone {zone_id}'),
                        'running': raw_running,  # Keep original value
                        'time_left': raw_timestr,
                        'raw_relay_data': relay  # Store complete raw data for debugging
                    }
        
        # Status information is already included above since we're getting from statusschedule
        
        return zones
        
    except Exception as e:
        print(f"[ERROR] Error getting zones: {e}")
        return {}


def show_zone_status(explorer):
    """Show current status of all zones with simplified numbering."""
    zones = get_zone_list(explorer)
    
    if not zones:
        print("[ERROR] No zones found")
        return zones, []
    
    print("\n[SYMBOL] CURRENT ZONE STATUS")
    print("=" * 60)
    
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
    
    # Create a sorted list of all zones for simplified selection
    all_zones = list(zones.values())
    all_zones.sort(key=lambda z: z['id'])  # Sort by zone ID
    
    print(f"\n[SYMBOL] ALL ZONES ({len(all_zones)} total):")
    print("=" * 40)
    
    for i, zone in enumerate(all_zones, 1):
        status = "[RUNNING]" if zone['running'] else "[IDLE]"
        print(f"   {i:2d}. {zone['name']:<25} {status}")
        if zone['running'] and zone.get('time_left'):
            print(f"       Time left: {zone['time_left']}")
    
    return zones, all_zones


def safety_stop_all_zones(explorer, delay_seconds=30):
    """Safety function to stop all zones after a delay."""
    def stop_all():
        time.sleep(delay_seconds)
        try:
            print(f"\n[SAFETY] Executing safety stop - stopping all zones...")
            # Stop all zones using the API
            result = explorer.stop_all_zones()
            print(f"[SAFETY] All zones stopped successfully")
            print(f"[LOG] Stop result: {result}")
        except Exception as e:
            print(f"[ERROR] Safety stop failed: {e}")
            print(f"[WARNING] Please manually stop zones if any are still running!")
    
    # Start the safety stop in a background thread
    safety_thread = threading.Thread(target=stop_all, daemon=True)
    safety_thread.start()
    print(f"[SAFETY] Safety stop scheduled in {delay_seconds} seconds")
    return safety_thread





def calculate_api_budget_needed(duration_minutes, quick_check=False):
    """Calculate how many API calls we'll need for the entire operation."""
    # Zone start command: 1 call (zone control)
    zone_start_calls = 1
    
    # Verification calls
    if quick_check:
        verification_calls = 1  # Just one check after 20s
    else:
        verification_calls = 2  # Two checks maximum (at 30s and 90s)
    
    # Monitoring calls (check every 45s during zone run)
    monitoring_calls = max(1, (duration_minutes * 60) // 45)
    
    # Stop detection calls (2 calls after duration expires)
    stop_detection_calls = 2
    
    total_general_calls = verification_calls + monitoring_calls + stop_detection_calls
    total_zone_calls = zone_start_calls
    
    return {
        'general_calls': total_general_calls,
        'zone_calls': total_zone_calls,
        'total_time_minutes': duration_minutes + 5  # Zone time + monitoring buffer
    }


def wait_for_api_budget(explorer, required_budget):
    """Wait until we have enough API calls available."""
    print(f"[BUDGET] Checking API budget...")
    print(f"[BUDGET] Required: {required_budget['general_calls']} general + {required_budget['zone_calls']} zone control calls")
    
    while True:
        status = explorer.rate_limiter.get_status() if explorer.rate_limiter else {
            'general_calls_remaining': 30, 'zone_control_calls_remaining': 3
        }
        
        general_available = status['general_calls_remaining']
        zone_available = status['zone_control_calls_remaining']
        
        if (general_available >= required_budget['general_calls'] and 
            zone_available >= required_budget['zone_calls']):
            print(f"[BUDGET] Sufficient budget available!")
            print(f"[BUDGET] Available: {general_available} general + {zone_available} zone calls")
            return True
        else:
            needed_general = max(0, required_budget['general_calls'] - general_available)
            needed_zone = max(0, required_budget['zone_calls'] - zone_available)
            
            if needed_general > 0:
                print(f"[BUDGET] Need {needed_general} more general API calls. Waiting 30 seconds...")
            if needed_zone > 0:
                print(f"[BUDGET] Need {needed_zone} more zone control calls. Waiting 30 seconds...")
            
            time.sleep(30)


def test_zone_start_timing(explorer, zone_id, duration_minutes):
    """Test how long it takes for a zone to show as running after start command, then monitor throughout run."""
    print(f"\n[TIMING] TESTING ZONE START TIMING + FULL RUN MONITORING")
    print("=" * 60)
    
    # Send start command and record exact time
    start_command_time = datetime.now()
    end_time = start_command_time + timedelta(minutes=duration_minutes)
    print(f"[TIMING] Sending start command at {start_command_time.strftime('%H:%M:%S.%f')[:-3]}")
    print(f"[TIMING] Zone will run until {end_time.strftime('%H:%M:%S')} ({duration_minutes} minutes)")
    
    result = explorer.start_zone(zone_id, duration_minutes)
    command_sent_time = datetime.now()
    command_delay = (command_sent_time - start_command_time).total_seconds()
    print(f"[TIMING] Command sent in {command_delay:.2f}s")
    
    # Check every 10 seconds throughout the entire run and a bit after
    print(f"[TIMING] Monitoring every 10 seconds throughout run and 30s after...")
    
    detection_time = None
    check = 0
    
    while True:
        check += 1
        time.sleep(10)
        check_time = datetime.now()
        elapsed = (check_time - start_command_time).total_seconds()
        
        zones = get_zone_list(explorer)
        
        print(f"\n[CHECK {check}] Time: {check_time.strftime('%H:%M:%S')} ({elapsed:.1f}s elapsed)")
        
        # Show raw API data
        if zone_id in zones:
            zone_info = zones[zone_id]
            raw_timestr = zone_info.get('time_left')
            raw_relay = zone_info.get('raw_relay_data', {})
            print(f"[RAW API] {raw_relay}")
            print(f"[STATUS] timestr='{raw_timestr}'")
            
            # Check if running
            if raw_timestr == 'Now':
                if detection_time is None:
                    detection_time = check_time
                    total_delay = (detection_time - start_command_time).total_seconds()
                    api_delay = (detection_time - command_sent_time).total_seconds()
                    print(f"[DETECTION] Zone first detected as running!")
                    print(f"[DETECTION] Total delay: {total_delay:.2f}s (command: {command_delay:.2f}s + API: {api_delay:.2f}s)")
                print(f"[RUNNING] Zone is currently running")
            else:
                print(f"[STOPPED] Zone is stopped (next: {raw_timestr})")
        else:
            print(f"[ERROR] Zone {zone_id} not found in API response")
        
        # Stop conditions
        current_time = datetime.now()
        duration_expired = current_time >= end_time
        
        if duration_expired:
            time_since_end = (current_time - end_time).total_seconds()
            if time_since_end > 30:  # Monitor 30 seconds after end
                print(f"\n[COMPLETE] Monitoring complete!")
                if detection_time:
                    recommended_delay = int((detection_time - start_command_time).total_seconds()) + 5
                    print(f"[RECOMMENDATION] Use {recommended_delay}s delay for verification")
                    return recommended_delay
                else:
                    print(f"[WARNING] Zone was never detected as running")
                    return 60
            else:
                print(f"[POST-RUN] Monitoring {30 - time_since_end:.0f}s more after zone stop...")
    
    return 60  # Fallback


def start_zone_and_wait(explorer, zone_id, duration_minutes):
    """Start a zone and verify it started - simplified version.
    
    Args:
        explorer: API explorer instance
        zone_id: Zone ID to start
        duration_minutes: How long to run the zone
    """
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
        
        # Wait for zone to start (based on timing test: ~15 seconds)
        print("[SYMBOL] Waiting 15 seconds for zone to start...")
        time.sleep(15)
        
        # Single verification check
        print(f"[ANALYSIS] Verifying zone started...")
        zones_updated = get_zone_list(explorer)
        
        # Debug: Show what we got back
        if zone_id in zones_updated:
            zone_info = zones_updated[zone_id]
            print(f"[DEBUG] Zone {zone_id} found: running={zone_info['running']}, name='{zone_info['name']}'")
            if zone_info.get('time_left'):
                print(f"[DEBUG] Time left: {zone_info['time_left']}")
            # Show ALL fields for this zone to see what else might indicate it's running
            print(f"[RAW] All zone data: {zone_info}")
        else:
            print(f"[DEBUG] Zone {zone_id} not found in verification check")
            print(f"[DEBUG] Available zones: {list(zones_updated.keys())}")
        
        # FIXED: Check time_left="Now" instead of running=True  
        if zone_id in zones_updated and zones_updated[zone_id].get('time_left') == 'Now':
            print(f"[OK] Zone {zone_name} started successfully!")
            print(f"[INFO] Zone will run for {duration_minutes} minutes")
            return True
        else:
            time_left = zones_updated[zone_id].get('time_left', 'Unknown') if zone_id in zones_updated else 'Not found'
            print(f"[WARNING] Zone not detected as running (timestr='{time_left}')")
            print(f"[INFO] Zone may still be starting or there may be an issue")
            # Safety stop after 30 seconds
            safety_stop_all_zones(explorer, delay_seconds=30)
            return False
            
    except Exception as e:
        print(f"[ERROR] Error starting zone: {e}")
        return False


def stop_all_zones_now(explorer):
    """Immediately stop all zones."""
    try:
        print(f"\n[STOP] Stopping all zones...")
        result = explorer.stop_all_zones()
        print(f"[OK] All zones stopped successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to stop zones: {e}")
        return False


def show_running_zones(explorer):
    """Show which zones are currently running."""
    zones = get_zone_list(explorer)
    running_zones = [zone for zone in zones.values() if zone.get('time_left') == 'Now']
    
    if running_zones:
        print(f"\n[RUNNING] Currently running zones:")
        for zone in running_zones:
            print(f"   - {zone['name']} (ID: {zone['id']})")
    else:
        print(f"\n[INFO] No zones currently running")
    
    return running_zones


def monitor_zone_smart(explorer, zone_id, duration_minutes, check_interval=45):
    """Smart zone monitoring that stops when duration expires AND all zones are stopped."""
    zones = get_zone_list(explorer)
    if zone_id not in zones:
        print(f"[ERROR] Zone {zone_id} not found")
        return
    
    zone_name = zones[zone_id]['name']
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    print(f"\n[SCHEDULE] MONITORING ZONE {zone_name}")
    print("=" * 50)
    print(f"[TIME] Started at: {start_time.strftime('%H:%M:%S')}")
    print(f"[TIME] Will run until: {end_time.strftime('%H:%M:%S')} ({duration_minutes} minutes)")
    print(f"[TIME] Checking every {check_interval} seconds")
    print("Press Ctrl+C to stop monitoring early")
    
    api_calls_used = 0
    
    try:
        while True:
            current_time = datetime.now()
            elapsed_minutes = (current_time - start_time).total_seconds() / 60
            
            print(f"\n[RESULTS] Status check at {current_time.strftime('%H:%M:%S')} ({elapsed_minutes:.1f} min elapsed)")
            
            # Get current zone status
            zones_current = get_zone_list(explorer)
            api_calls_used += 1
            
            # FIXED: Check if any zones are running using time_left="Now"
            any_zones_running = any(zone.get('time_left') == 'Now' for zone in zones_current.values())
            target_zone_running = zone_id in zones_current and zones_current[zone_id].get('time_left') == 'Now'
            
            # Show RAW API data for the target zone
            if zone_id in zones_current:
                zone_info = zones_current[zone_id]
                raw_relay = zone_info.get('raw_relay_data', {})
                print(f"   [RAW API] Zone {zone_id} data: {raw_relay}")
                
                # Show interpreted status
                if target_zone_running:
                    print(f"   [SYMBOL] {zone_name} is running")
                    print(f"   [SCHEDULE] Time left: {zone_info.get('time_left', 'Unknown')}")
                else:
                    time_left = zone_info.get('time_left', 'Unknown')
                    print(f"   [SYMBOL] {zone_name} is stopped (next: {time_left})")
            else:
                print(f"   [ERROR] Zone {zone_id} not found in API response")
            
            # Show all running zones (FIXED: use time_left="Now")
            running_zones = [z for z in zones_current.values() if z.get('time_left') == 'Now']
            if running_zones:
                print(f"   [INFO] Other running zones: {len(running_zones)}")
                for zone in running_zones[:3]:  # Show first 3
                    print(f"      - {zone['name']}")
            else:
                print(f"   [INFO] No zones currently running")
            

            
            # Check stop conditions
            duration_expired = current_time >= end_time
            
            if duration_expired:
                print(f"   [TIME] Duration expired at {current_time.strftime('%H:%M:%S')}")
                if not any_zones_running:
                    # Continue monitoring for 30 more seconds to see API data after stop
                    time_since_end = (current_time - end_time).total_seconds()
                    if time_since_end < 30:
                        print(f"   [INFO] All zones stopped - monitoring 30s more to see API changes ({time_since_end:.0f}s elapsed)")
                    else:
                        print(f"   [COMPLETE] Monitoring complete after 30s post-stop observation!")
                        break
                else:
                    print(f"   [INFO] Duration expired but {len(running_zones)} zones still running")
                    print(f"   [INFO] Continuing to monitor until all zones stop...")
            
            # Wait before next check (unless we're close to the end)
            if not duration_expired:
                time_until_end = (end_time - current_time).total_seconds()
                wait_time = min(check_interval, time_until_end)
                if wait_time > 10:  # Only wait if we have more than 10 seconds
                    time.sleep(wait_time)
            else:
                # After duration expires, check more frequently
                time.sleep(20)
    
    except KeyboardInterrupt:
        print("\n[CANCELLED] Monitoring stopped by user")
    
    # Show results
    end_time_actual = datetime.now()
    duration = end_time_actual - start_time
    
    print(f"\n[SYMBOL] MONITORING SUMMARY")
    print("=" * 30)
    print(f"[TIME] Total monitoring time: {duration.total_seconds()/60:.1f} minutes")
    print(f"[API] Total API calls used: {api_calls_used}")





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
    
    # Initialize with NO rate limiting for zone control testing
    explorer = HydrawiseAPIExplorer(api_key, respect_rate_limits=False, aggressive_rate_limiting=False)
    
    # Show current system status
    print("\n[ANALYSIS] Checking system status...")
    zones, zone_list = show_zone_status(explorer)
    
    if not zones:
        print("[ERROR] No zones available")
        return
    

    
    # Main menu loop
    try:
        while True:
            # Show all zones with status
            print(f"\n[SYMBOL] ZONE STATUS")
            print("=" * 50)
            zones = get_zone_list(explorer)
            for i, zone in enumerate(zone_list, 1):
                zone_id = zone['id']
                zone_name = zone['name']
                if zone_id in zones and zones[zone_id].get('time_left') == 'Now':
                    status = "[RUNNING]"
                else:
                    status = "[IDLE]"
                print(f"{i:2}. {zone_name:<20} {status}")
            
            print(f"\n[SYMBOL] ZONE CONTROL MENU")
            print("=" * 40)
            print("1. Start a zone")
            print("2. Stop all running zones")
            print("3. Refresh status")
            print("4. Exit")
            
            choice = input("\nChoose option (1-4): ").strip()
            
            if choice == '1':
                # Start zone
                print(f"\n[SYMBOL] ZONE SELECTION")
                print("=" * 40)
                
                # Get zone selection
                while True:
                    try:
                        zone_choice = int(input(f"Enter zone number (1-{len(zone_list)}): "))
                        if 1 <= zone_choice <= len(zone_list):
                            selected_zone = zone_list[zone_choice - 1]
                            zone_id = selected_zone['id']
                            zone_name = selected_zone['name']
                            break
                        else:
                            print(f"[ERROR] Please enter a number between 1 and {len(zone_list)}")
                    except ValueError:
                        print("[ERROR] Please enter a valid number")
                
                # Get duration
                duration = int(input("Enter duration in minutes: "))
                
                # Confirm and start
                print(f"\n[INFO] Starting: {zone_name} for {duration} minutes")
                confirm = input("Proceed? (yes/no): ").lower().strip()
                
                if confirm == 'yes':
                    success = start_zone_and_wait(explorer, zone_id, duration)
                    if success:
                        print(f"[SUCCESS] Zone {zone_name} is now running for {duration} minutes!")
                    else:
                        print("[ERROR] Zone did not start properly")
                
            elif choice == '2':
                # Stop all zones
                # Check if any zones are running
                zones = get_zone_list(explorer)
                running_zones = [zone for zone in zones.values() if zone.get('time_left') == 'Now']
                
                if running_zones:
                    confirm = input("Stop all running zones? (yes/no): ").lower().strip()
                    if confirm == 'yes':
                        stop_all_zones_now(explorer)
                else:
                    print("[INFO] No zones currently running")
                    
            elif choice == '3':
                # Refresh status - just loop back to show status
                continue
                
            elif choice == '4':
                # Exit
                print("[INFO] Exiting zone control")
                break
                
            else:
                print("[ERROR] Please enter 1-4")
    
    except KeyboardInterrupt:
        print("\n[SYMBOL] Goodbye!")
    except Exception as e:
        print(f"[ERROR] Error: {e}")


if __name__ == "__main__":
    main()
