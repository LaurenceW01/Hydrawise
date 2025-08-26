#!/usr/bin/env python3
"""
Zone Configuration Management Utility

Command-line utility for managing irrigation zone configuration including:
- Viewing current zone configuration
- Updating average flow rates
- Importing/exporting configuration
- Synchronizing with database

Author: AI Assistant
Date: 2025-01-27
"""

import argparse
import sys
import os
import json
from datetime import datetime
from typing import Dict, List

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.zone_configuration import ZoneConfiguration
from database.database_manager import DatabaseManager

def print_banner():
    """Print the utility banner"""
    print("=" * 60)
    print("[SYMBOL] HYDRAWISE ZONE CONFIGURATION MANAGER")
    print("=" * 60)

def show_zones(args):
    """Show current zone configuration"""
    print_banner()
    print("[LOG] CURRENT ZONE CONFIGURATION")
    print("-" * 50)
    
    try:
        config = ZoneConfiguration()
        zones_data = config.get_zones_data()
        flow_rates = config.get_average_flow_rates()
        
        if not zones_data:
            print("[ERROR] No zones configured")
            return 1
        
        print(f"[RESULTS] Total Zones: {len(zones_data)}")
        print(f"[WATER] Flow Rates Configured: {len(flow_rates)}")
        print()
        
        # Table header
        print(f"{'ID':<3} {'Name':<35} {'Flow':<6} {'Avg':<6} {'Priority':<8} {'Type':<10}")
        print("-" * 70)
        
        for zone_id, name, flow_rate_gpm, priority, plant_type in zones_data:
            avg_rate = flow_rates.get(zone_id, 'N/A')
            avg_str = f"{avg_rate:.1f}" if isinstance(avg_rate, (int, float)) else str(avg_rate)
            flow_str = f"{flow_rate_gpm:.1f}" if flow_rate_gpm else 'N/A'
            
            print(f"{zone_id:<3} {name[:34]:<35} {flow_str:<6} {avg_str:<6} {priority:<8} {plant_type:<10}")
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] Failed to show zones: {e}")
        return 1

def update_flow_rate(args):
    """Update average flow rate for a zone"""
    print_banner()
    print(f"[WATER] UPDATING FLOW RATE FOR ZONE {args.zone_id}")
    print("-" * 50)
    
    try:
        # Update configuration
        config = ZoneConfiguration()
        config.update_flow_rate(args.zone_id, args.flow_rate)
        
        # Update database if requested
        if args.update_db:
            db_manager = DatabaseManager()
            success = db_manager.update_zone_average_flow_rate(args.zone_id, args.flow_rate)
            
            if success:
                print(f"[OK] Updated zone {args.zone_id} flow rate to {args.flow_rate} GPM")
                print("   [RESULTS] Configuration updated")
                print("   [DATABASE]  Database updated")
            else:
                print(f"[ERROR] Failed to update database for zone {args.zone_id}")
                return 1
        else:
            print(f"[OK] Updated zone {args.zone_id} flow rate to {args.flow_rate} GPM in configuration")
            print("   [INFO] Use --update-db to also update the database")
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] Failed to update flow rate: {e}")
        return 1

def export_config(args):
    """Export configuration to file"""
    print_banner()
    print(f"[SYMBOL] EXPORTING CONFIGURATION")
    print("-" * 50)
    
    try:
        config = ZoneConfiguration()
        zones_data = config.get_zones_data()
        flow_rates = config.get_average_flow_rates()
        
        # Build export data
        export_data = {
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "total_zones": len(zones_data),
                "flow_rates_configured": len(flow_rates)
            },
            "zones": []
        }
        
        for zone_id, name, flow_rate_gpm, priority, plant_type in zones_data:
            zone_data = {
                "zone_id": zone_id,
                "name": name,
                "flow_rate_gpm": flow_rate_gpm,
                "priority": priority,
                "plant_type": plant_type,
                "average_flow_rate": flow_rates.get(zone_id)
            }
            export_data["zones"].append(zone_data)
        
        # Write to file
        with open(args.file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"[OK] Exported {len(zones_data)} zones to {args.file}")
        return 0
        
    except Exception as e:
        print(f"[ERROR] Failed to export configuration: {e}")
        return 1

def import_config(args):
    """Import configuration from file"""
    print_banner()
    print(f"[SYMBOL] IMPORTING CONFIGURATION")
    print("-" * 50)
    
    try:
        # Read import file
        with open(args.file, 'r') as f:
            import_data = json.load(f)
        
        zones_data = import_data.get("zones", [])
        
        if not zones_data:
            print(f"[ERROR] No zones found in {args.file}")
            return 1
        
        print(f"[RESULTS] Found {len(zones_data)} zones in import file")
        
        if not args.force:
            response = input("[WARNING]  This will replace current configuration. Continue? (y/N): ")
            if response.lower() != 'y':
                print("[ERROR] Import cancelled")
                return 1
        
        # Update configuration
        config = ZoneConfiguration()
        config.save_configuration(zones_data)
        
        print(f"[OK] Imported {len(zones_data)} zones")
        print("   [RESULTS] Configuration file updated")
        
        return 0
        
    except FileNotFoundError:
        print(f"[ERROR] File not found: {args.file}")
        return 1
    except Exception as e:
        print(f"[ERROR] Failed to import configuration: {e}")
        return 1

def sync_to_db(args):
    """Synchronize configuration to database"""
    print_banner()
    print("[PERIODIC] SYNCHRONIZING CONFIGURATION TO DATABASE")
    print("-" * 50)
    
    try:
        config = ZoneConfiguration()
        flow_rates = config.get_average_flow_rates()
        
        if not flow_rates:
            print("[ERROR] No average flow rates configured")
            return 1
        
        db_manager = DatabaseManager()
        
        success_count = 0
        for zone_id, flow_rate in flow_rates.items():
            if db_manager.update_zone_average_flow_rate(zone_id, flow_rate):
                success_count += 1
            else:
                print(f"[WARNING]  Failed to update zone {zone_id}")
        
        print(f"[OK] Successfully synchronized {success_count}/{len(flow_rates)} zones to database")
        return 0 if success_count == len(flow_rates) else 1
        
    except Exception as e:
        print(f"[ERROR] Failed to synchronize to database: {e}")
        return 1

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Manage Hydrawise zone configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show current configuration
  python manage_zone_config.py --show

  # Update flow rate for zone 4
  python manage_zone_config.py --update-flow-rate 4 1.5

  # Update flow rate and sync to database
  python manage_zone_config.py --update-flow-rate 4 1.5 --update-db

  # Export configuration
  python manage_zone_config.py --export zones_backup.json

  # Import configuration
  python manage_zone_config.py --import zones_backup.json --force

  # Sync all flow rates to database
  python manage_zone_config.py --sync-to-db
        """
    )
    
    # Action arguments
    parser.add_argument('--show', action='store_true',
                       help='Show current zone configuration')
    parser.add_argument('--update-flow-rate', nargs=2, type=float, metavar=('ZONE_ID', 'FLOW_RATE'),
                       help='Update average flow rate for a zone')
    parser.add_argument('--export', type=str, metavar='FILE',
                       help='Export configuration to JSON file')
    parser.add_argument('--import', dest='import_file', type=str, metavar='FILE',
                       help='Import configuration from JSON file')
    parser.add_argument('--sync-to-db', action='store_true',
                       help='Synchronize configuration to database')
    
    # Modifier arguments
    parser.add_argument('--update-db', action='store_true',
                       help='Also update database when updating flow rates')
    parser.add_argument('--force', action='store_true',
                       help='Force operation without confirmation')
    
    args = parser.parse_args()
    
    # Determine which command to execute
    if args.show:
        return show_zones(args)
    elif args.update_flow_rate:
        args.zone_id = int(args.update_flow_rate[0])
        args.flow_rate = args.update_flow_rate[1]
        return update_flow_rate(args)
    elif args.export:
        args.file = args.export
        return export_config(args)
    elif args.import_file:
        args.file = args.import_file
        return import_config(args)
    elif args.sync_to_db:
        return sync_to_db(args)
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())

