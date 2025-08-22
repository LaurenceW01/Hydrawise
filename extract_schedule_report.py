#!/usr/bin/env python3
"""
Extract Schedule Report with Popup Details

Queries the database for today's scheduled runs and displays all popup line items
in a readable format for analysis.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, date
from typing import List, Dict, Any

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.intelligent_data_storage import IntelligentDataStorage

def extract_schedule_report():
    """Extract and display today's scheduled runs with popup details"""
    
    print("📊 HYDRAWISE SCHEDULED RUNS REPORT")
    print("=" * 80)
    print(f"📅 Date: {date.today().strftime('%A, %B %d, %Y')}")
    print("🔍 Data Source: Local SQLite Database")
    print("=" * 80)
    
    try:
        # Connect to database
        storage = IntelligentDataStorage("database/irrigation_data.db")
        
        # Query today's scheduled runs
        with sqlite3.connect(storage.db_path) as conn:
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id,
                    zone_name,
                    scheduled_start_time,
                    scheduled_duration_minutes,
                    expected_gallons,
                    is_rain_cancelled,
                    rain_sensor_status,
                    popup_status,
                    raw_popup_text,
                    popup_lines_json,
                    parsed_summary,
                    created_at
                FROM scheduled_runs 
                WHERE schedule_date = ?
                ORDER BY scheduled_start_time, id
            """, (date.today(),))
            
            runs = cursor.fetchall()
            
        if not runs:
            print("❌ No scheduled runs found for today")
            print("   This could mean:")
            print("   • No data has been collected yet")
            print("   • All irrigation was cancelled")
            print("   • Database is empty")
            return False
            
        print(f"📋 Found {len(runs)} scheduled runs for today\n")
        
        # Display summary table
        print("📊 SCHEDULE SUMMARY:")
        print("-" * 120)
        print(f"{'Zone Name':<35} {'Start Time':<12} {'Duration':<10} {'Rain Cancel':<12} {'Status':<25} {'Popup Lines':<12}")
        print("-" * 120)
        
        total_duration = 0
        rain_cancelled_count = 0
        
        for run in runs:
            zone_name = run['zone_name'][:32] + "..." if len(run['zone_name']) > 32 else run['zone_name']
            start_time = datetime.fromisoformat(run['scheduled_start_time']).strftime('%I:%M %p')
            duration = f"{run['scheduled_duration_minutes']} min"
            rain_cancel = "🌧️ YES" if run['is_rain_cancelled'] else "☀️ NO"
            status = (run['popup_status'] or 'Normal')[:22] + "..." if len(run['popup_status'] or 'Normal') > 22 else (run['popup_status'] or 'Normal')
            
            # Count popup lines
            popup_lines_count = 0
            if run['popup_lines_json']:
                try:
                    popup_lines = json.loads(run['popup_lines_json'])
                    popup_lines_count = len(popup_lines)
                except:
                    pass
                    
            popup_count = f"{popup_lines_count} lines"
            
            print(f"{zone_name:<35} {start_time:<12} {duration:<10} {rain_cancel:<12} {status:<25} {popup_count:<12}")
            
            if not run['is_rain_cancelled']:
                total_duration += run['scheduled_duration_minutes']
            else:
                rain_cancelled_count += 1
                
        print("-" * 120)
        print(f"TOTALS: {len(runs)} runs scheduled | {rain_cancelled_count} rain cancelled | {total_duration} minutes active irrigation")
        print()
        
        # Display detailed popup analysis for each run
        print("📄 DETAILED POPUP ANALYSIS:")
        print("=" * 80)
        
        for i, run in enumerate(runs, 1):
            print(f"\n{i}. {run['zone_name']}")
            print(f"   ⏰ Scheduled: {datetime.fromisoformat(run['scheduled_start_time']).strftime('%I:%M %p')}")
            print(f"   ⏱️  Duration: {run['scheduled_duration_minutes']} minutes")
            print(f"   💧 Expected: {run['expected_gallons']:.2f} gallons" if run['expected_gallons'] else "   💧 Expected: Not calculated")
            print(f"   🌧️  Rain Cancelled: {'YES' if run['is_rain_cancelled'] else 'NO'}")
            
            if run['rain_sensor_status']:
                print(f"   🌦️  Rain Status: {run['rain_sensor_status']}")
                
            # Display popup lines
            if run['popup_lines_json']:
                try:
                    popup_lines = json.loads(run['popup_lines_json'])
                    print(f"   📄 Popup Lines ({len(popup_lines)} total):")
                    
                    for idx, line_data in enumerate(popup_lines, 1):
                        line_type = line_data.get('type', 'unknown').upper()
                        line_text = line_data.get('text', '')
                        parsed_value = line_data.get('parsed_value')
                        
                        if parsed_value is not None and parsed_value != '':
                            print(f"      Line {idx} [{line_type}]: '{line_text}' → {parsed_value}")
                        else:
                            print(f"      Line {idx} [{line_type}]: '{line_text}'")
                            
                except json.JSONDecodeError:
                    print("   📄 Popup Lines: Error parsing JSON data")
                    
            elif run['raw_popup_text']:
                print(f"   📄 Raw Popup Text:")
                for line in run['raw_popup_text'].split('\n'):
                    if line.strip():
                        print(f"      {line.strip()}")
            else:
                print("   📄 Popup Data: None available")
                
            if run['parsed_summary']:
                print(f"   📊 Summary: {run['parsed_summary']}")
                
            print(f"   📅 Collected: {datetime.fromisoformat(run['created_at']).strftime('%Y-%m-%d %I:%M %p')}")
            
            # Ensure output is flushed for each zone
            sys.stdout.flush()
            
        print("\n" + "=" * 80)
        print("✅ Schedule report completed successfully")
        
        # Additional analysis
        if rain_cancelled_count == len(runs):
            print("🌧️  WEATHER ALERT: All irrigation cancelled due to rain sensor")
        elif rain_cancelled_count > 0:
            print(f"🌦️  PARTIAL CANCELLATION: {rain_cancelled_count}/{len(runs)} runs cancelled due to rain")
        else:
            print("☀️  NORMAL OPERATION: No rain cancellations detected")
        
        # Final flush to ensure all output is displayed
        sys.stdout.flush()
        return True
        
    except Exception as e:
        print(f"❌ Error extracting schedule report: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the schedule report extraction"""
    try:
        success = extract_schedule_report()
        
        if success:
            print("\n✨ Report generation completed!")
        else:
            print("\n💔 Report generation failed")
            
    except KeyboardInterrupt:
        print("\n👋 Report interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")

if __name__ == "__main__":
    main()
