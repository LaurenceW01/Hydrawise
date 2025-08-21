#!/usr/bin/env python3
"""
Hydrawise Zone Control Examples

This script demonstrates practical examples of controlling Hydrawise zones
for common irrigation scenarios.

Author: AI Assistant
Date: 2024
"""

from hydrawise_api_explorer import HydrawiseAPIExplorer
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import os
from dotenv import load_dotenv


class HydrawiseZoneController:
    """
    Enhanced zone controller with practical irrigation scenarios.
    
    This class provides higher-level methods for common irrigation tasks
    beyond the basic API calls.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the zone controller.
        
        Args:
            api_key (str): Your Hydrawise API key
        """
        # FIXED: Use less aggressive rate limiting for better zone control
        self.explorer = HydrawiseAPIExplorer(api_key, respect_rate_limits=True, aggressive_rate_limiting=False)
        self.zones_info = {}
        self._refresh_zone_info()
    
    def _refresh_zone_info(self) -> None:
        """
        Refresh zone information from the API.
        Internal method to keep zone data current.
        """
        try:
            # FIXED: Get zone information from statusschedule (not customerdetails)
            status_data = self.explorer.get_status_schedule()
            
            # Extract zone information from status response
            self.zones_info = self._extract_zone_info(status_data)
            
        except Exception as e:
            print(f"⚠️ Warning: Could not refresh zone info: {e}")
    
    def _extract_zone_info(self, status_data: Dict) -> Dict[int, Dict]:
        """
        Extract zone information from statusschedule API response.
        
        Args:
            status_data (dict): Response from statusschedule endpoint
            
        Returns:
            dict: Zone information indexed by zone ID
        """
        zones = {}
        
        # FIXED: Process status data for zone names, IDs, and current state
        if 'relays' in status_data:
            for relay in status_data['relays']:
                zone_id = relay.get('relay_id')
                if zone_id:
                    zones[zone_id] = {
                        'id': zone_id,
                        'name': relay.get('name', f'Zone {zone_id}'),
                        'type': relay.get('type', 'Unknown'),
                        'running': relay.get('running', False),
                        'time_left': relay.get('timestr', ''),
                        'next_run': relay.get('nextrun', ''),
                        'status': relay.get('status', 'Unknown')
                    }
        
        return zones
    
    def list_zones(self) -> None:
        """
        Display all available zones with their current status.
        """
        print("\n🌱 AVAILABLE ZONES")
        print("=" * 40)
        
        if not self.zones_info:
            print("❌ No zones found. Check your API key and controller setup.")
            return
        
        for zone_id, info in self.zones_info.items():
            status_icon = "🟢" if info.get('running') else "⚫"
            print(f"{status_icon} Zone {zone_id}: {info.get('name', 'Unknown')}")
            print(f"   Status: {info.get('status', 'Unknown')}")
            if info.get('running'):
                print(f"   Time Left: {info.get('time_left', 'Unknown')}")
            if info.get('next_run'):
                print(f"   Next Run: {info.get('next_run')}")
            print()
    
    def quick_water(self, zone_id: int, minutes: int = 5) -> Dict[str, Any]:
        """
        Start a quick watering session for a zone.
        
        Args:
            zone_id (int): ID of the zone to water
            minutes (int): Duration in minutes (default: 5)
            
        Returns:
            dict: API response
        """
        print(f"💧 Starting quick {minutes}-minute watering for zone {zone_id}")
        
        # Check if zone exists
        if zone_id not in self.zones_info:
            print(f"❌ Zone {zone_id} not found. Available zones:")
            self.list_zones()
            return {}
        
        zone_name = self.zones_info[zone_id].get('name', f'Zone {zone_id}')
        print(f"🌱 Watering: {zone_name}")
        
        return self.explorer.start_zone(zone_id, minutes)
    
    def deep_water_cycle(self, zone_ids: List[int], minutes_per_zone: int = 20, 
                        rest_minutes: int = 5) -> None:
        """
        Run a deep watering cycle across multiple zones with rest periods.
        
        Args:
            zone_ids (list): List of zone IDs to water
            minutes_per_zone (int): Minutes to water each zone
            rest_minutes (int): Minutes to rest between zones
        """
        print(f"\n🌊 STARTING DEEP WATER CYCLE")
        print(f"Zones: {zone_ids}")
        print(f"Duration per zone: {minutes_per_zone} minutes")
        print(f"Rest between zones: {rest_minutes} minutes")
        print("=" * 50)
        
        for i, zone_id in enumerate(zone_ids):
            zone_name = self.zones_info.get(zone_id, {}).get('name', f'Zone {zone_id}')
            
            print(f"\n🚿 Step {i+1}/{len(zone_ids)}: Watering {zone_name}")
            
            try:
                # Start the zone
                result = self.explorer.start_zone(zone_id, minutes_per_zone)
                print(f"✅ Zone {zone_id} started successfully")
                
                # Wait for the zone to finish (plus a small buffer)
                wait_time = minutes_per_zone * 60 + 30  # Add 30 seconds buffer
                print(f"⏰ Waiting {minutes_per_zone} minutes for zone to complete...")
                
                # Could add real-time monitoring here
                time.sleep(wait_time)
                
                # Add rest period between zones (except for the last zone)
                if i < len(zone_ids) - 1 and rest_minutes > 0:
                    print(f"😴 Resting for {rest_minutes} minutes before next zone...")
                    time.sleep(rest_minutes * 60)
                
            except Exception as e:
                print(f"❌ Error watering zone {zone_id}: {e}")
                
                # Ask user if they want to continue
                response = input("Continue with remaining zones? (y/n): ").lower().strip()
                if response != 'y':
                    print("🛑 Deep water cycle stopped by user")
                    break
        
        print("\n✅ Deep water cycle complete!")
    
    def morning_routine(self, lawn_zones: List[int], garden_zones: List[int]) -> None:
        """
        Execute a typical morning watering routine.
        
        Args:
            lawn_zones (list): Zone IDs for lawn areas (shorter duration)
            garden_zones (list): Zone IDs for garden areas (longer duration)
        """
        print("\n🌅 MORNING WATERING ROUTINE")
        print("=" * 30)
        
        # Water lawn zones for 10 minutes each
        print("🏞️ Watering lawn zones...")
        for zone_id in lawn_zones:
            self.quick_water(zone_id, 10)
            time.sleep(2)  # Small delay between starts
        
        # Wait a bit, then water garden zones for 15 minutes each
        time.sleep(60)  # 1 minute pause
        
        print("🌻 Watering garden zones...")
        for zone_id in garden_zones:
            self.quick_water(zone_id, 15)
            time.sleep(2)  # Small delay between starts
        
        print("✅ Morning routine started!")
    
    def emergency_stop_all(self) -> Dict[str, Any]:
        """
        Emergency stop all zones immediately.
        
        Returns:
            dict: API response
        """
        print("🚨 EMERGENCY STOP - Stopping all zones immediately!")
        return self.explorer.stop_all_zones()
    
    def maintenance_suspend(self, zone_ids: List[int], days: int = 7) -> None:
        """
        Suspend multiple zones for maintenance.
        
        Args:
            zone_ids (list): List of zone IDs to suspend
            days (int): Number of days to suspend
        """
        print(f"🔧 MAINTENANCE MODE - Suspending {len(zone_ids)} zones for {days} days")
        
        for zone_id in zone_ids:
            zone_name = self.zones_info.get(zone_id, {}).get('name', f'Zone {zone_id}')
            print(f"⏸️ Suspending {zone_name}...")
            
            try:
                result = self.explorer.suspend_zone(zone_id, days)
                print(f"✅ Zone {zone_id} suspended successfully")
            except Exception as e:
                print(f"❌ Error suspending zone {zone_id}: {e}")
    
    def resume_from_maintenance(self, zone_ids: List[int]) -> None:
        """
        Resume multiple zones from maintenance suspension.
        
        Args:
            zone_ids (list): List of zone IDs to resume
        """
        print(f"🔧 RESUMING FROM MAINTENANCE - Activating {len(zone_ids)} zones")
        
        for zone_id in zone_ids:
            zone_name = self.zones_info.get(zone_id, {}).get('name', f'Zone {zone_id}')
            print(f"▶️ Resuming {zone_name}...")
            
            try:
                result = self.explorer.resume_zone(zone_id)
                print(f"✅ Zone {zone_id} resumed successfully")
            except Exception as e:
                print(f"❌ Error resuming zone {zone_id}: {e}")


def demonstrate_zone_control():
    """
    Interactive demonstration of zone control capabilities.
    """
    print("🎛️ HYDRAWISE ZONE CONTROL DEMONSTRATION")
    print("=" * 50)
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Try to get API key from environment variable first
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        # Fall back to manual input if not found in .env
        print("🔍 No API key found in .env file (HUNTER_HYDRAWISE_API_KEY)")
        api_key = input("🔑 Enter your Hydrawise API key: ").strip()
        
        if not api_key:
            print("❌ API key required! Please add HUNTER_HYDRAWISE_API_KEY to your .env file")
            return
    else:
        print(f"✅ API key loaded from .env file")
        print(f"🔑 Using key: {api_key[:8]}..." + "*" * (len(api_key) - 8) if len(api_key) > 8 else api_key)
    
    # Initialize controller
    controller = HydrawiseZoneController(api_key)
    
    # Show available zones
    controller.list_zones()
    
    while True:
        print("\n" + "=" * 40)
        print("🎮 ZONE CONTROL MENU")
        print("=" * 40)
        print("1. 💧 Quick water a zone")
        print("2. 🌊 Deep water cycle")
        print("3. 🌅 Morning routine")
        print("4. 🚨 Emergency stop all")
        print("5. 🔧 Maintenance suspend")
        print("6. ▶️ Resume from maintenance")
        print("7. 🔍 Refresh zone list")
        print("0. 🚪 Exit")
        
        choice = input("\n👉 Choose an option: ").strip()
        
        try:
            if choice == "1":
                zone_id = int(input("Enter zone ID: "))
                minutes = int(input("Enter minutes (default 5): ") or "5")
                controller.quick_water(zone_id, minutes)
            
            elif choice == "2":
                zones_input = input("Enter zone IDs separated by commas: ")
                zone_ids = [int(x.strip()) for x in zones_input.split(",")]
                minutes = int(input("Minutes per zone (default 20): ") or "20")
                rest = int(input("Rest minutes between zones (default 5): ") or "5")
                controller.deep_water_cycle(zone_ids, minutes, rest)
            
            elif choice == "3":
                lawn_input = input("Enter lawn zone IDs (comma-separated): ")
                garden_input = input("Enter garden zone IDs (comma-separated): ")
                
                lawn_zones = [int(x.strip()) for x in lawn_input.split(",") if x.strip()]
                garden_zones = [int(x.strip()) for x in garden_input.split(",") if x.strip()]
                
                controller.morning_routine(lawn_zones, garden_zones)
            
            elif choice == "4":
                confirm = input("⚠️ Really stop ALL zones? (yes/no): ").lower()
                if confirm == "yes":
                    controller.emergency_stop_all()
                else:
                    print("❌ Cancelled")
            
            elif choice == "5":
                zones_input = input("Enter zone IDs to suspend (comma-separated): ")
                zone_ids = [int(x.strip()) for x in zones_input.split(",")]
                days = int(input("Days to suspend (default 7): ") or "7")
                controller.maintenance_suspend(zone_ids, days)
            
            elif choice == "6":
                zones_input = input("Enter zone IDs to resume (comma-separated): ")
                zone_ids = [int(x.strip()) for x in zones_input.split(",")]
                controller.resume_from_maintenance(zone_ids)
            
            elif choice == "7":
                print("🔄 Refreshing zone information...")
                controller._refresh_zone_info()
                controller.list_zones()
            
            elif choice == "0":
                print("👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice")
        
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    demonstrate_zone_control()
