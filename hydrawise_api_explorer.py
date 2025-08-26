#!/usr/bin/env python3
"""
Hunter Hydrawise API Explorer

This script explores the Hydrawise API capabilities including:
- Retrieving controller and zone information
- Zone control (start/stop/timed runs)
- Water usage and flow meter data analysis
- Watering history and schedules

Author: AI Assistant
Date: 2024
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sys
import os
from dotenv import load_dotenv
from collections import deque
import threading


class RateLimiter:
    """
    Rate limiter to enforce Hydrawise API restrictions.
    
    Hydrawise API Limits:
    - Zone control operations: 3 calls per 30 seconds
    - General API usage: 30 calls per 5 minutes (300 seconds)
    """
    
    def __init__(self):
        """Initialize rate limiter with separate tracking for different operation types."""
        self.lock = threading.Lock()
        
        # Track general API calls (30 per 5 minutes)
        self.general_calls = deque()
        self.general_limit = 30
        self.general_window = 300  # 5 minutes in seconds
        
        # Track zone control calls (3 per 30 seconds)
        self.zone_control_calls = deque()
        self.zone_control_limit = 3
        self.zone_control_window = 30  # 30 seconds
        
    def _cleanup_old_calls(self, call_queue: deque, window_seconds: int) -> None:
        """
        Remove calls older than the specified window.
        
        Args:
            call_queue (deque): Queue of timestamps to clean
            window_seconds (int): Time window in seconds
        """
        current_time = time.time()
        while call_queue and current_time - call_queue[0] > window_seconds:
            call_queue.popleft()
    
    def wait_if_needed(self, is_zone_control: bool = False) -> None:
        """
        Wait if necessary to respect rate limits before making a call.
        
        Args:
            is_zone_control (bool): True if this is a zone control operation
        """
        with self.lock:
            current_time = time.time()
            
            # Clean up old calls
            self._cleanup_old_calls(self.general_calls, self.general_window)
            self._cleanup_old_calls(self.zone_control_calls, self.zone_control_window)
            
            # Check general rate limit
            if len(self.general_calls) >= self.general_limit:
                wait_time = self.general_window - (current_time - self.general_calls[0])
                if wait_time > 0:
                    print(f"[SYMBOL] Rate limit reached. Waiting {wait_time:.1f} seconds for general API limit...")
                    time.sleep(wait_time)
                    self._cleanup_old_calls(self.general_calls, self.general_window)
            
            # Check zone control rate limit if applicable
            if is_zone_control and len(self.zone_control_calls) >= self.zone_control_limit:
                wait_time = self.zone_control_window - (current_time - self.zone_control_calls[0])
                if wait_time > 0:
                    print(f"[SYMBOL] Zone control rate limit reached. Waiting {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                    self._cleanup_old_calls(self.zone_control_calls, self.zone_control_window)
            
            # Record the new call
            call_time = time.time()
            self.general_calls.append(call_time)
            if is_zone_control:
                self.zone_control_calls.append(call_time)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current rate limiter status.
        
        Returns:
            dict: Current status of rate limits
        """
        with self.lock:
            current_time = time.time()
            self._cleanup_old_calls(self.general_calls, self.general_window)
            self._cleanup_old_calls(self.zone_control_calls, self.zone_control_window)
            
            return {
                'general_calls_used': len(self.general_calls),
                'general_calls_limit': self.general_limit,
                'general_calls_remaining': self.general_limit - len(self.general_calls),
                'zone_control_calls_used': len(self.zone_control_calls),
                'zone_control_calls_limit': self.zone_control_limit,
                'zone_control_calls_remaining': self.zone_control_limit - len(self.zone_control_calls),
                'next_general_reset': min([call + self.general_window for call in self.general_calls], default=current_time),
                'next_zone_reset': min([call + self.zone_control_window for call in self.zone_control_calls], default=current_time)
            }


class HydrawiseAPIExplorer:
    """
    Hunter Hydrawise API client for exploring and controlling irrigation systems.
    
    This class provides methods to interact with the Hydrawise REST API for:
    - Getting controller and zone information
    - Starting and stopping zones
    - Running zones for specific durations
    - Retrieving watering history and flow data
    
    Features:
    - Automatic rate limiting compliance with Hydrawise API restrictions
    - Respect for nextpoll recommendations
    - Comprehensive error handling and retry logic
    """
    
    def __init__(self, api_key: str, respect_rate_limits: bool = True, aggressive_rate_limiting: bool = False):
        """
        Initialize the Hydrawise API explorer.
        
        Args:
            api_key (str): Your Hydrawise API key obtained from account settings
            respect_rate_limits (bool): Whether to enforce rate limiting (default: True)
            aggressive_rate_limiting (bool): Whether to aggressively follow nextpoll (default: False)
        """
        self.api_key = api_key
        self.base_url = "https://api.hydrawise.com/api/v1"
        self.session = requests.Session()
        self.respect_rate_limits = respect_rate_limits
        self.aggressive_rate_limiting = aggressive_rate_limiting
        self.rate_limiter = RateLimiter() if respect_rate_limits else None
        self.last_nextpoll = {}  # Track nextpoll recommendations per endpoint
        
        # Set default headers for all requests
        self.session.headers.update({
            'User-Agent': 'HydrawiseAPIExplorer/1.0',
            'Accept': 'application/json'
        })
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None, is_zone_control: bool = False, try_php_extension: bool = True) -> Dict[str, Any]:
        """
        Make a GET request to the Hydrawise API with rate limiting and nextpoll respect.
        
        Args:
            endpoint (str): API endpoint to call
            params (dict): Additional parameters for the request
            is_zone_control (bool): Whether this is a zone control operation
            
        Returns:
            dict: JSON response from the API
            
        Raises:
            requests.RequestException: If the API request fails
        """
        if params is None:
            params = {}
        
        # Add API key to all requests
        params['api_key'] = self.api_key
        
        # Only use .php endpoints for Hydrawise API - non-.php endpoints use different auth
        if try_php_extension and not endpoint.endswith('.php'):
            url = f"{self.base_url}/{endpoint}.php"
        else:
            url = f"{self.base_url}/{endpoint}"
        
        # Check if we should respect nextpoll for this endpoint
        if self.respect_rate_limits and self.aggressive_rate_limiting and endpoint in self.last_nextpoll:
            nextpoll_time = self.last_nextpoll[endpoint]
            current_time = time.time()
            if current_time < nextpoll_time:
                wait_time = nextpoll_time - current_time
                print(f"[SCHEDULE] Respecting nextpoll recommendation. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
        elif self.respect_rate_limits and endpoint in self.last_nextpoll:
            # Less aggressive: only wait if nextpoll is very recent (< 10 seconds)
            nextpoll_time = self.last_nextpoll[endpoint]
            current_time = time.time()
            if current_time < nextpoll_time:
                wait_time = nextpoll_time - current_time
                if wait_time > 10:
                    print(f"[SCHEDULE] Large nextpoll delay ({wait_time:.1f}s) - reducing to 10s for monitoring")
                    time.sleep(10)
                else:
                    print(f"[SCHEDULE] Short nextpoll delay. Waiting {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
        
        # Apply rate limiting
        if self.respect_rate_limits and self.rate_limiter:
            self.rate_limiter.wait_if_needed(is_zone_control)
            
            # Show rate limit status
            status = self.rate_limiter.get_status()
            if is_zone_control:
                print(f"[SYMBOL] Zone control calls: {status['zone_control_calls_used']}/{status['zone_control_calls_limit']} used")
            print(f"[SYMBOL] General API calls: {status['general_calls_used']}/{status['general_calls_limit']} used")
        
        # Try the request with connection retry logic
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"[ANALYSIS] Making request to: {url}")
                if retry_count > 0:
                    print(f"   (Retry {retry_count}/{max_retries-1})")
                print(f"[LOG] Parameters: {params}")
                
                # Set a reasonable timeout and add connection handling
                response = self.session.get(url, params=params, timeout=30)
                
                # Handle rate limiting response
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', 60)
                    print(f"[WARNING] Rate limited by server. Waiting {retry_after} seconds...")
                    time.sleep(int(retry_after))
                    
                    # Retry the request once
                    response = self.session.get(url, params=params, timeout=30)
                
                response.raise_for_status()
                
                data = response.json()
                print(f"[OK] Request successful - Status: {response.status_code}")
                
                # Check for nextpoll recommendation in response
                if 'nextpoll' in data and self.respect_rate_limits:
                    try:
                        nextpoll_seconds = int(data['nextpoll'])
                        self.last_nextpoll[endpoint] = time.time() + nextpoll_seconds
                        print(f"[SYMBOL] API recommends next poll in {nextpoll_seconds} seconds")
                    except (ValueError, TypeError):
                        pass  # Invalid nextpoll value, ignore
                
                return data
                
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                retry_count += 1
                print(f"[SYMBOL] Connection issue (attempt {retry_count}): {e}")
                
                if retry_count < max_retries:
                    wait_time = min(5 * retry_count, 15)  # Progressive backoff: 5s, 10s, 15s
                    print(f"[SYMBOL] Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[ERROR] Max retries ({max_retries}) exceeded for connection errors")
                    raise
                
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] Request failed: {e}")
                
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response status: {e.response.status_code}")
                    print(f"Response text: {e.response.text}")
                    
                    # If it's a rate limit error, provide helpful info
                    if e.response.status_code == 429:
                        print("[INFO] You've hit the rate limit. Consider:")
                        print("   - Reducing request frequency")
                        print("   - Implementing longer delays between calls")
                        print("   - Using the nextpoll recommendations")
                    
                    # If it's 401, this is an auth issue
                    if e.response.status_code == 401:
                        print("[SYMBOL] Authentication failed. Check:")
                        print("   - API key is correct and active")
                        print("   - Using .php endpoints (non-.php need different auth)")
                        print("   - Account has necessary permissions")
                
                # For non-connection errors, don't retry
                raise
        
        # Should not reach here due to raise in the loop, but just in case
        raise requests.exceptions.RequestException(f"Failed to complete request to {url}")
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Returns:
            dict: Rate limit status information
        """
        if not self.rate_limiter:
            return {"rate_limiting": "disabled"}
        
        return self.rate_limiter.get_status()
    
    def reset_rate_limits(self) -> None:
        """
        Reset rate limit counters (use carefully for testing).
        """
        if self.rate_limiter:
            with self.rate_limiter.lock:
                self.rate_limiter.general_calls.clear()
                self.rate_limiter.zone_control_calls.clear()
            print("[PERIODIC] Rate limit counters reset")
    
    def get_customer_details(self) -> Dict[str, Any]:
        """
        Get customer account details including controllers and zones.
        
        Returns:
            dict: Customer details with controllers and zone information
        """
        print("\n[SYMBOL] Getting customer details...")
        return self._make_request("customerdetails")
    
    def get_status_schedule(self, controller_id: Optional[int] = None, retry_on_failure: bool = True) -> Dict[str, Any]:
        """
        Get current status and schedule for all controllers or a specific controller.
        
        Args:
            controller_id (int, optional): Specific controller ID to query
            retry_on_failure (bool): Whether to retry on connection failures
            
        Returns:
            dict: Status and schedule information
        """
        print(f"\n[DATE] Getting status and schedule{f' for controller {controller_id}' if controller_id else ''}...")
        params = {}
        if controller_id:
            params['controller_id'] = controller_id
        
        try:
            return self._make_request("statusschedule", params)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if retry_on_failure:
                print(f"[PERIODIC] Connection failed, retrying in 10 seconds...")
                time.sleep(10)
                try:
                    return self._make_request("statusschedule", params)
                except Exception as retry_e:
                    print(f"[ERROR] Retry also failed: {retry_e}")
                    # Return minimal data structure to prevent crashes
                    return {'relays': [], 'sensors': []}
            else:
                raise
        except Exception as e:
            print(f"[WARNING] Status check failed: {e}")
            # Return minimal data structure to prevent crashes
            return {'relays': [], 'sensors': []}
    
    def start_zone(self, zone_id: int, duration_minutes: int) -> Dict[str, Any]:
        """
        Start a specific zone for a given duration.
        
        Args:
            zone_id (int): ID of the zone to start
            duration_minutes (int): Duration in minutes to run the zone
            
        Returns:
            dict: API response confirming the action
        """
        # FIXED: Convert minutes to seconds - Hydrawise 'custom' parameter uses seconds!
        duration_seconds = duration_minutes * 60
        print(f"\n[SYMBOL] Starting zone {zone_id} for {duration_minutes} minutes ({duration_seconds} seconds)...")
        params = {
            'action': 'run',
            'relay_id': zone_id,
            'custom': duration_seconds
        }
        return self._make_request("setzone", params, is_zone_control=True)
    
    def stop_zone(self, zone_id: int) -> Dict[str, Any]:
        """
        Stop a specific zone immediately.
        
        Args:
            zone_id (int): ID of the zone to stop
            
        Returns:
            dict: API response confirming the action
        """
        print(f"\n[SYMBOL] Stopping zone {zone_id}...")
        params = {
            'action': 'stop',
            'relay_id': zone_id
        }
        return self._make_request("setzone", params, is_zone_control=True)
    
    def stop_all_zones(self) -> Dict[str, Any]:
        """
        Stop all running zones immediately.
        
        Returns:
            dict: API response confirming the action
        """
        print("\n[SYMBOL] Stopping all zones...")
        params = {'action': 'stopall'}
        return self._make_request("setzone", params, is_zone_control=True)
    
    def suspend_zone(self, zone_id: int, days: int = 1) -> Dict[str, Any]:
        """
        Suspend a zone for a specified number of days.
        
        Args:
            zone_id (int): ID of the zone to suspend
            days (int): Number of days to suspend (default: 1)
            
        Returns:
            dict: API response confirming the action
        """
        print(f"\n[SYMBOL][SYMBOL] Suspending zone {zone_id} for {days} days...")
        params = {
            'action': 'suspend',
            'relay_id': zone_id,
            'custom': days
        }
        return self._make_request("setzone", params, is_zone_control=True)
    
    def resume_zone(self, zone_id: int) -> Dict[str, Any]:
        """
        Resume a suspended zone.
        
        Args:
            zone_id (int): ID of the zone to resume
            
        Returns:
            dict: API response confirming the action
        """
        print(f"\n[SYMBOL][SYMBOL] Resuming zone {zone_id}...")
        params = {
            'action': 'suspend',
            'relay_id': zone_id,
            'custom': 0
        }
        return self._make_request("setzone", params, is_zone_control=True)
    
    def get_flow_meter_data(self, status_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract flow meter data from status response.
        Flow meter data is embedded in the statusschedule response as sensors with type=3.
        
        Args:
            status_data (dict, optional): Status data from statusschedule.php. If None, will fetch it.
            
        Returns:
            dict: Flow meter data if available
        """
        print(f"\n[WATER] Extracting flow meter data...")
        
        # Get status data if not provided
        if not status_data:
            try:
                status_data = self.get_status_schedule()
            except Exception as e:
                print(f"  [ERROR] Failed to get status data: {e}")
                return {}
        
        flow_meters = {}
        
        # Look for sensors in the response
        if 'sensors' in status_data:
            sensors = status_data['sensors']
            print(f"  [ANALYSIS] Found {len(sensors)} sensors to check...")
            
            # Handle both dictionary and list formats
            if isinstance(sensors, dict):
                # Dictionary format: {sensor_id: sensor_data}
                for sensor_id, sensor_data in sensors.items():
                    if sensor_data.get('type') == 3:
                        flow_meters[sensor_id] = {
                            'input': sensor_data.get('input'),
                            'type': sensor_data.get('type'),
                            'mode': sensor_data.get('mode'),
                            'timer': sensor_data.get('timer', 0),
                            'offtimer': sensor_data.get('offtimer', 0),
                            'rate': sensor_data.get('rate', 0.0),
                            'relays': sensor_data.get('relays', [])
                        }
                        print(f"  [OK] Flow meter found - Sensor {sensor_id}")
                        print(f"     Current Rate: {sensor_data.get('rate', 0.0)} GPM")
                        print(f"     Timer: {sensor_data.get('timer', 0)} seconds")
                        print(f"     Connected to {len(sensor_data.get('relays', []))} zones")
            
            elif isinstance(sensors, list):
                # List format: [sensor_data, sensor_data, ...]
                for i, sensor_data in enumerate(sensors):
                    if sensor_data.get('type') == 3:
                        sensor_id = str(sensor_data.get('input', i))  # Use input number or index as ID
                        flow_meters[sensor_id] = {
                            'input': sensor_data.get('input'),
                            'type': sensor_data.get('type'),
                            'mode': sensor_data.get('mode'),
                            'timer': sensor_data.get('timer', 0),
                            'offtimer': sensor_data.get('offtimer', 0),
                            'rate': sensor_data.get('rate', 0.0),
                            'relays': sensor_data.get('relays', [])
                        }
                        print(f"  [OK] Flow meter found - Sensor {sensor_id} (Input {sensor_data.get('input')})")
                        print(f"     Current Rate: {sensor_data.get('rate', 0.0)} GPM")
                        print(f"     Timer: {sensor_data.get('timer', 0)} seconds")
                        print(f"     Connected to {len(sensor_data.get('relays', []))} zones")
        
        if not flow_meters:
            print("  [ERROR] No flow meters (type=3 sensors) found in response")
            print("  [INFO] Make sure your HC Flow Meter is properly connected and configured")
        
        return flow_meters
    
    def analyze_zone_data(self, data: Dict[str, Any]) -> None:
        """
        Analyze and display zone information from API response.
        
        Args:
            data (dict): API response data to analyze
        """
        print("\n[RESULTS] ZONE ANALYSIS")
        print("=" * 50)
        
        # Try to find zones in the response
        zones = []
        if 'relays' in data:
            zones = data['relays']
        elif 'zones' in data:
            zones = data['zones']
        elif isinstance(data, list):
            zones = data
        
        if not zones:
            print("[ERROR] No zone data found in response")
            return
        
        for i, zone in enumerate(zones):
            print(f"\n[SYMBOL] Zone {i + 1}:")
            print(f"   Name: {zone.get('name', 'Unknown')}")
            print(f"   ID: {zone.get('relay_id', zone.get('id', 'Unknown'))}")
            print(f"   Physical Relay: {zone.get('relay', 'Unknown')}")
            
            # Interpret running status correctly
            running = zone.get('running')
            if running == 1 or running is True:
                print(f"   Status: [SYMBOL] RUNNING")
            elif running == 0 or running is False:
                print(f"   Status: [SYMBOL] IDLE")
            elif running is None:
                print(f"   Status: [SYMBOL] NOT SCHEDULED TODAY")
            else:
                print(f"   Status: [SYMBOL] Unknown ({running})")
            
            # Interpret time information correctly
            timestr = zone.get('timestr', '')
            if timestr:
                # Check if it's a day of week (next scheduled day)
                if timestr in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
                    print(f"   Next Run Day: [DATE] {timestr}")
                # Check if it's a time format (scheduled time today/tomorrow)
                elif ':' in timestr:
                    print(f"   Next Run Time: [SCHEDULE] {timestr}")
                else:
                    print(f"   Schedule Info: {timestr}")
            
            # Show next run details if available
            nextrun = zone.get('nextrun')
            if nextrun and nextrun not in ['Unknown', '']:
                print(f"   Next Run: {nextrun}")
            
            # Look for flow/water usage data
            flow_fields = ['flow', 'water_used', 'flow_rate', 'usage', 'gallons', 'liters']
            flow_data_found = False
            for field in flow_fields:
                if field in zone and zone[field] is not None:
                    print(f"   [WATER] {field.title()}: {zone[field]}")
                    flow_data_found = True
            
            if not flow_data_found:
                print(f"   [WATER] Flow Data: Not available")
    
    def analyze_controller_data(self, data: Dict[str, Any]) -> None:
        """
        Analyze and display controller information from API response.
        
        Args:
            data (dict): API response data to analyze
        """
        print("\n[SYMBOL][SYMBOL] CONTROLLER ANALYSIS")
        print("=" * 50)
        
        # Look for controller information
        controllers = []
        if 'controllers' in data:
            controllers = data['controllers']
        elif 'controller' in data:
            controllers = [data['controller']]
        
        for controller in controllers:
            print(f"\n[SYMBOL] Controller:")
            print(f"   Name: {controller.get('name', 'Unknown')}")
            print(f"   ID: {controller.get('controller_id', 'Unknown')}")
            print(f"   Status: {controller.get('status', 'Unknown')}")
            print(f"   Last Contact: {controller.get('last_contact', 'Unknown')}")
            print(f"   Hardware: {controller.get('hardware', 'Unknown')}")
            
            # Look for sensor/flow meter information
            if 'sensors' in controller:
                print(f"   Sensors: {len(controller['sensors'])} found")
                for sensor in controller['sensors']:
                    print(f"     - {sensor.get('name', 'Unknown')} ({sensor.get('type', 'Unknown')})")
    
    def comprehensive_exploration(self) -> None:
        """
        Perform a comprehensive exploration of the Hydrawise API.
        This method calls various endpoints to discover available functionality.
        """
        print("\n[SYMBOL] STARTING COMPREHENSIVE HYDRAWISE API EXPLORATION")
        print("=" * 60)
        
        try:
            # 1. Get customer details
            customer_data = self.get_customer_details()
            self.analyze_controller_data(customer_data)
            self.analyze_zone_data(customer_data)
            
            # 2. Get status and schedule
            status_data = self.get_status_schedule()
            self.analyze_zone_data(status_data)
            
            # 3. Extract flow meter data from status response
            flow_data = self.get_flow_meter_data(status_data)
            if flow_data:
                print("\n[WATER] FLOW METER DATA FOUND:")
                print(json.dumps(flow_data, indent=2))
            else:
                print("\n[WATER] No flow meter data found - check if HC Flow Meter is connected")
            
            # 4. Display raw data for manual inspection
            print("\n[LOG] RAW CUSTOMER DATA:")
            print("=" * 30)
            print(json.dumps(customer_data, indent=2))
            
            print("\n[LOG] RAW STATUS DATA:")
            print("=" * 30)
            print(json.dumps(status_data, indent=2))
            
        except Exception as e:
            print(f"\n[ERROR] Exploration failed: {e}")
            return
        
        print("\n[OK] EXPLORATION COMPLETE!")
        print("\n[INFO] Check the raw data above for any flow meter or water usage information.")
        print("[INFO] If no flow data is visible, it may require the GraphQL API or special permissions.")


def main():
    """
    Main function to run the Hydrawise API exploration.
    """
    print("[SYMBOL] Hunter Hydrawise API Explorer")
    print("=" * 40)
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Try to get API key from environment variable first
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        # Fall back to manual input if not found in .env
        print("[ANALYSIS] No API key found in .env file (HUNTER_HYDRAWISE_API_KEY)")
        api_key = input("\n[SYMBOL] Enter your Hydrawise API key: ").strip()
        
        if not api_key:
            print("[ERROR] API key is required. Please:")
            print("   1. Add HUNTER_HYDRAWISE_API_KEY=your_key_here to your .env file, OR")
            print("   2. Get one from your Hydrawise account settings and enter it manually")
            sys.exit(1)
    else:
        print(f"[OK] API key loaded from .env file")
        print(f"[SYMBOL] Using key: {api_key[:8]}..." + "*" * (len(api_key) - 8) if len(api_key) > 8 else api_key)
    
    # Initialize the explorer
    explorer = HydrawiseAPIExplorer(api_key)
    
    # Main menu loop
    while True:
        print("\n" + "=" * 50)
        print("[SYMBOL][SYMBOL] HYDRAWISE API EXPLORER MENU")
        print("=" * 50)
        print("1. [ANALYSIS] Comprehensive API exploration")
        print("2. [SYMBOL] Get customer details")
        print("3. [DATE] Get status and schedule")
        print("4. [SYMBOL] Start a zone")
        print("5. [SYMBOL] Stop a zone")
        print("6. [SYMBOL] Stop all zones")
        print("7. [SYMBOL][SYMBOL] Suspend a zone")
        print("8. [SYMBOL][SYMBOL] Resume a zone")
        print("9. [WATER] Try to get flow meter data")
        print("10. [SYMBOL] Show rate limit status")
        print("11. [PERIODIC] Reset rate limits (testing only)")
        print("0. [SYMBOL] Exit")
        
        choice = input("\n[SYMBOL] Enter your choice (0-11): ").strip()
        
        try:
            if choice == "1":
                explorer.comprehensive_exploration()
            
            elif choice == "2":
                data = explorer.get_customer_details()
                explorer.analyze_controller_data(data)
                explorer.analyze_zone_data(data)
            
            elif choice == "3":
                data = explorer.get_status_schedule()
                explorer.analyze_zone_data(data)
            
            elif choice == "4":
                zone_id = int(input("Enter zone ID to start: "))
                duration = int(input("Enter duration in minutes: "))
                result = explorer.start_zone(zone_id, duration)
                print(f"Result: {json.dumps(result, indent=2)}")
            
            elif choice == "5":
                zone_id = int(input("Enter zone ID to stop: "))
                result = explorer.stop_zone(zone_id)
                print(f"Result: {json.dumps(result, indent=2)}")
            
            elif choice == "6":
                result = explorer.stop_all_zones()
                print(f"Result: {json.dumps(result, indent=2)}")
            
            elif choice == "7":
                zone_id = int(input("Enter zone ID to suspend: "))
                days = int(input("Enter number of days to suspend (default 1): ") or "1")
                result = explorer.suspend_zone(zone_id, days)
                print(f"Result: {json.dumps(result, indent=2)}")
            
            elif choice == "8":
                zone_id = int(input("Enter zone ID to resume: "))
                result = explorer.resume_zone(zone_id)
                print(f"Result: {json.dumps(result, indent=2)}")
            
            elif choice == "9":
                data = explorer.get_flow_meter_data()
                if data:
                    print(f"Flow data: {json.dumps(data, indent=2)}")
                else:
                    print("No flow meter data endpoints found")
            
            elif choice == "10":
                status = explorer.get_rate_limit_status()
                print("\n[SYMBOL] RATE LIMIT STATUS")
                print("=" * 30)
                if status.get("rate_limiting") == "disabled":
                    print("[WARNING] Rate limiting is disabled")
                else:
                    print(f"[RESULTS] General API calls: {status['general_calls_used']}/{status['general_calls_limit']} used")
                    print(f"   Remaining: {status['general_calls_remaining']}")
                    print(f"[SYMBOL][SYMBOL] Zone control calls: {status['zone_control_calls_used']}/{status['zone_control_calls_limit']} used")
                    print(f"   Remaining: {status['zone_control_calls_remaining']}")
                    
                    # Show time until reset
                    current_time = time.time()
                    if status['next_general_reset'] > current_time:
                        general_reset = status['next_general_reset'] - current_time
                        print(f"[SCHEDULE] General limit resets in: {general_reset:.1f} seconds")
                    if status['next_zone_reset'] > current_time:
                        zone_reset = status['next_zone_reset'] - current_time
                        print(f"[SCHEDULE] Zone control limit resets in: {zone_reset:.1f} seconds")
            
            elif choice == "11":
                confirm = input("[WARNING] Really reset rate limit counters? This is for testing only (y/n): ").lower()
                if confirm == 'y':
                    explorer.reset_rate_limits()
                else:
                    print("[ERROR] Cancelled")
            
            elif choice == "0":
                print("[SYMBOL] Goodbye!")
                break
            
            else:
                print("[ERROR] Invalid choice. Please try again.")
        
        except KeyboardInterrupt:
            print("\n\n[SYMBOL] Goodbye!")
            break
        except Exception as e:
            print(f"[ERROR] Error: {e}")
            print("Please try again.")


if __name__ == "__main__":
    main()
