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
from database.universal_database_manager import get_universal_database_manager
from database.irrigation_analytics import IrrigationAnalytics
from datetime import datetime, timedelta

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
            # Use the universal database manager for consistency
            db_manager_universal = get_universal_database_manager()
            
            # Update in the zones table directly
            update_query = "UPDATE zones SET average_flow_rate = %s WHERE zone_id = %s"
            rows_updated = db_manager_universal.adapter.execute_update(update_query, (args.flow_rate, args.zone_id))
            success = rows_updated > 0
            
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

def calculate_flow_rates(args):
    """Calculate optimal flow rates from historical actual usage data"""
    print_banner()
    print("[ANALYTICS] CALCULATING FLOW RATES FROM HISTORICAL DATA")
    print("-" * 50)
    
    try:
        # Calculate date range (past 7 days, excluding today)
        today = datetime.now().date()
        end_date = today - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=args.days - 1)  # Past N days
        
        print(f"[PERIOD] Analyzing data from {start_date} to {end_date} ({args.days} days)")
        print()
        
        db_manager = get_universal_database_manager()
        
        # Query actual runs with valid water usage data
        query = """
            SELECT 
                zone_id, 
                zone_name,
                actual_gallons,
                actual_duration_minutes,
                usage_flag,
                run_date
            FROM actual_runs 
            WHERE run_date BETWEEN %s AND %s
            AND actual_gallons IS NOT NULL 
            AND actual_gallons > 0
            AND actual_duration_minutes > 0
            AND usage_flag IN ('normal', 'too_high', 'too_low')
            ORDER BY zone_id, run_date
        """
        
        runs = db_manager.adapter.execute_query(query, (start_date, end_date))
        
        if not runs:
            print("[ERROR] No valid run data found in the specified period")
            return 1
        
        print(f"[DATA] Found {len(runs)} valid runs to analyze")
        print()
        
        # Group runs by zone
        zone_data = {}
        for run in runs:
            zone_id = run['zone_id']
            zone_name = run['zone_name']
            gallons = float(run['actual_gallons'])
            duration = float(run['actual_duration_minutes'])
            usage_flag = run['usage_flag']
            run_date = run['run_date']
            
            if zone_id not in zone_data:
                zone_data[zone_id] = {
                    'zone_name': zone_name,
                    'runs': [],
                    'total_gallons': 0,
                    'total_duration': 0,
                    'normal_runs': 0,
                    'high_runs': 0,
                    'low_runs': 0
                }
            
            zone_info = zone_data[zone_id]
            zone_info['runs'].append({
                'gallons': gallons,
                'duration': duration,
                'gpm': gallons / duration,
                'usage_flag': usage_flag,
                'date': run_date
            })
            zone_info['total_gallons'] += gallons
            zone_info['total_duration'] += duration
            
            # Count usage flags
            if usage_flag == 'normal':
                zone_info['normal_runs'] += 1
            elif usage_flag == 'too_high':
                zone_info['high_runs'] += 1
            elif usage_flag == 'too_low':
                zone_info['low_runs'] += 1
        
        # Calculate flow rates for each zone
        print("CALCULATED FLOW RATES:")
        print("=" * 80)
        print(f"{'Zone':<4} {'Name':<30} {'Runs':<5} {'Calc GPM':<8} {'Current':<8} {'Change':<8} {'Quality':<10}")
        print("-" * 80)
        
        calculated_rates = {}
        recommendations = []
        
        for zone_id, data in zone_data.items():
            zone_name = data['zone_name']
            runs = data['runs']
            total_runs = len(runs)
            
            if total_runs < args.min_runs:
                print(f"{zone_id:<4} {zone_name[:29]:<30} {total_runs:<5} {'N/A':<8} {'N/A':<8} {'N/A':<8} {'Too few':<10}")
                continue
            
            # Calculate flow rate using different methods
            
            # Method 1: Simple average (all runs)
            simple_avg = data['total_gallons'] / data['total_duration']
            
            # Method 2: Median GPM (more robust against outliers)
            gpm_values = [run['gpm'] for run in runs]
            gpm_values.sort()
            median_gpm = gpm_values[len(gpm_values) // 2]
            
            # Method 3: Average of "normal" runs only (excludes anomalies)
            normal_runs = [run for run in runs if run['usage_flag'] == 'normal']
            if normal_runs:
                normal_avg = sum(run['gpm'] for run in normal_runs) / len(normal_runs)
            else:
                normal_avg = simple_avg
            
            # Method 4: Weighted average (give more weight to recent runs)
            sorted_runs = sorted(runs, key=lambda x: x['date'])
            weighted_sum = 0
            weight_sum = 0
            for i, run in enumerate(sorted_runs):
                weight = i + 1  # More recent runs get higher weight
                weighted_sum += run['gpm'] * weight
                weight_sum += weight
            weighted_avg = weighted_sum / weight_sum if weight_sum > 0 else simple_avg
            
            # Choose the best method based on data quality
            normal_ratio = data['normal_runs'] / total_runs
            
            if normal_ratio >= 0.8:  # 80% or more normal runs
                calculated_gpm = normal_avg
                quality = "Excellent"
            elif normal_ratio >= 0.6:  # 60-80% normal runs
                calculated_gpm = median_gpm
                quality = "Good"
            elif total_runs >= 10:  # Lots of data, use weighted average
                calculated_gpm = weighted_avg
                quality = "Fair"
            else:
                calculated_gpm = simple_avg
                quality = "Poor"
            
            # Get current flow rate
            current_rate = db_manager.get_zone_average_flow_rate(zone_id)
            current_str = f"{current_rate:.2f}" if current_rate else "None"
            
            # Calculate change
            if current_rate:
                change = calculated_gpm - current_rate
                change_str = f"{change:+.2f}"
                change_percent = (change / current_rate) * 100
            else:
                change_str = "New"
                change_percent = None
            
            calculated_rates[zone_id] = {
                'zone_name': zone_name,
                'calculated_gpm': calculated_gpm,
                'current_gpm': current_rate,
                'change': change if current_rate else None,
                'change_percent': change_percent,
                'runs_analyzed': total_runs,
                'normal_runs': data['normal_runs'],
                'quality': quality,
                'methods': {
                    'simple_avg': simple_avg,
                    'median': median_gpm,
                    'normal_avg': normal_avg,
                    'weighted_avg': weighted_avg
                }
            }
            
            print(f"{zone_id:<4} {zone_name[:29]:<30} {total_runs:<5} {calculated_gpm:<8.2f} {current_str:<8} {change_str:<8} {quality:<10}")
            
            # Add to recommendations if significant change
            if current_rate and change_percent and abs(change_percent) >= args.threshold:
                recommendations.append({
                    'zone_id': zone_id,
                    'zone_name': zone_name,
                    'current': current_rate,
                    'calculated': calculated_gpm,
                    'change_percent': change_percent
                })
        
        print()
        print("RECOMMENDATIONS:")
        print("-" * 50)
        
        if recommendations:
            print(f"Found {len(recommendations)} zones with significant flow rate changes (>{args.threshold}%):")
            for rec in recommendations:
                direction = "increase" if rec['change_percent'] > 0 else "decrease"
                print(f"  Zone {rec['zone_id']} ({rec['zone_name'][:30]}): {direction} from {rec['current']:.2f} to {rec['calculated']:.2f} GPM ({rec['change_percent']:+.1f}%)")
        else:
            print("No significant flow rate changes recommended.")
        
        print()
        
        # Apply updates if requested
        if args.apply:
            if not recommendations:
                print("[INFO] No updates needed - all flow rates are within threshold")
                return 0
            
            print("[UPDATE] Applying flow rate updates...")
            
            config = ZoneConfiguration()
            db_manager_old = DatabaseManager()
            
            success_count = 0
            for rec in recommendations:
                zone_id = rec['zone_id']
                new_rate = rec['calculated']
                
                try:
                    # Update configuration
                    config.update_flow_rate(zone_id, new_rate)
                    
                    # Update database
                    if db_manager_old.update_zone_average_flow_rate(zone_id, new_rate):
                        print(f"  ✓ Updated zone {zone_id}: {rec['current']:.2f} → {new_rate:.2f} GPM")
                        success_count += 1
                    else:
                        print(f"  ❌ Failed to update zone {zone_id} in database")
                        
                except Exception as e:
                    print(f"  ❌ Failed to update zone {zone_id}: {e}")
            
            print(f"[OK] Successfully updated {success_count}/{len(recommendations)} zones")
            
        elif recommendations:
            print("[INFO] Use --apply to update flow rates, or update individual zones with:")
            for rec in recommendations:
                print(f"  python manage_zone_config.py --update-flow-rate {rec['zone_id']} {rec['calculated']:.2f} --update-db")
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] Failed to calculate flow rates: {e}")
        import traceback
        traceback.print_exc()
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

  # Calculate optimal flow rates from past 7 days of data
  python manage_zone_config.py --calculate-flow-rates

  # Calculate and apply flow rate changes (15% threshold)
  python manage_zone_config.py --calculate-flow-rates --apply

  # Analyze past 14 days with 10% threshold
  python manage_zone_config.py --calculate-flow-rates --days 14 --threshold 10.0
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
    parser.add_argument('--calculate-flow-rates', action='store_true',
                       help='Calculate optimal flow rates from historical usage data')
    
    # Modifier arguments
    parser.add_argument('--update-db', action='store_true',
                       help='Also update database when updating flow rates')
    parser.add_argument('--force', action='store_true',
                       help='Force operation without confirmation')
    parser.add_argument('--apply', action='store_true',
                       help='Apply calculated flow rate changes automatically')
    parser.add_argument('--days', type=int, default=7,
                       help='Number of days of historical data to analyze (default: 7)')
    parser.add_argument('--min-runs', type=int, default=3,
                       help='Minimum number of runs required per zone for calculation (default: 3)')
    parser.add_argument('--threshold', type=float, default=15.0,
                       help='Percentage change threshold for recommendations (default: 15.0)')
    
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
    elif args.calculate_flow_rates:
        return calculate_flow_rates(args)
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())

