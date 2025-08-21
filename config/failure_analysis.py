#!/usr/bin/env python3
"""
Failure Pattern Analysis Script

Analyzes Hydrawise Excel reports to identify all types of irrigation failures
and patterns that require user intervention for plant protection.

Author: AI Assistant
Date: 2025
"""

import pandas as pd
import os
from collections import defaultdict
from datetime import datetime, timedelta

def analyze_failure_patterns():
    """
    Analyze both Excel reports to understand all failure patterns.
    
    Returns:
        dict: Analysis results with failure types, patterns, and recommendations
    """
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    # Read schedule report (aggregated data)
    schedule_file = os.path.join(data_dir, 'hydrawise-watering-report (4).xls')
    df_schedule = pd.read_excel(schedule_file)
    
    # Read historical runs report (per-zone data)
    runs_file = os.path.join(data_dir, 'hydrawise-watering-report (3).xls')
    df_runs_all = pd.read_excel(runs_file, sheet_name=None)
    
    analysis = {
        'schedule_failures': {},
        'zone_failures': {},
        'failure_types': defaultdict(int),
        'recommendations': []
    }
    
    # Analyze schedule-level failures
    print("=== SCHEDULE-LEVEL FAILURES ===")
    schedule_failures = df_schedule['Notes'].value_counts()
    print(schedule_failures)
    
    for failure_type, count in schedule_failures.items():
        analysis['failure_types'][failure_type] = count
        analysis['schedule_failures'][failure_type] = {
            'count': count,
            'percentage': (count / len(df_schedule)) * 100
        }
    
    # Analyze zone-specific failures
    print("\n=== ZONE-SPECIFIC FAILURES ===")
    zone_analysis = {}
    
    for zone_name, zone_df in df_runs_all.items():
        print(f"\n{zone_name}:")
        zone_failures = zone_df['Notes'].value_counts()
        print(zone_failures)
        
        zone_analysis[zone_name] = {
            'total_runs': len(zone_df),
            'failure_breakdown': zone_failures.to_dict(),
            'failure_rate': {}
        }
        
        # Calculate failure rates
        for failure_type, count in zone_failures.items():
            if 'Normal watering cycle' not in failure_type:
                zone_analysis[zone_name]['failure_rate'][failure_type] = (count / len(zone_df)) * 100
    
    analysis['zone_failures'] = zone_analysis
    
    # Identify critical failure patterns
    critical_failures = [
        'Aborted due to sensor input',
        'Cancelled due to manual start',
        'Watering cycle suspended'
    ]
    
    # Identify patterns requiring immediate alerts
    immediate_alert_patterns = []
    warning_patterns = []
    
    for failure_type in analysis['failure_types']:
        if any(critical in failure_type for critical in critical_failures):
            immediate_alert_patterns.append(failure_type)
        elif 'Manual' not in failure_type and 'Normal' not in failure_type:
            warning_patterns.append(failure_type)
    
    analysis['immediate_alerts'] = immediate_alert_patterns
    analysis['warning_alerts'] = warning_patterns
    
    # Generate recommendations
    analysis['recommendations'] = [
        "Monitor for 'Aborted due to sensor input' - indicates sensor failures requiring immediate attention",
        "Track zones with high manual intervention rates - may indicate schedule problems",
        "Watch for missing scheduled runs (gaps in timeline) - could indicate power outages or system failures",
        "Alert when normal watering cycles are cancelled or suspended unexpectedly",
        "Priority alerts for high-value zones (trees, expensive plants) based on flow rate data"
    ]
    
    return analysis

def detect_schedule_gaps(zone_df, expected_frequency_hours=12):
    """
    Detect gaps in watering schedule that might indicate system failures.
    
    Args:
        zone_df (DataFrame): Zone data with Date and Time columns
        expected_frequency_hours (int): Expected hours between waterings
        
    Returns:
        list: List of detected gaps with timestamps
    """
    
    # Convert to datetime and sort
    zone_df = zone_df.copy()
    zone_df['DateTime'] = pd.to_datetime(zone_df['Date'])
    zone_df = zone_df.sort_values('DateTime')
    
    gaps = []
    
    for i in range(1, len(zone_df)):
        time_diff = zone_df.iloc[i]['DateTime'] - zone_df.iloc[i-1]['DateTime']
        
        # If gap is significantly longer than expected frequency
        if time_diff > timedelta(hours=expected_frequency_hours * 2):
            gaps.append({
                'start': zone_df.iloc[i-1]['DateTime'],
                'end': zone_df.iloc[i]['DateTime'],
                'duration_hours': time_diff.total_seconds() / 3600,
                'likely_cause': 'System failure, power outage, or extended manual suspension'
            })
    
    return gaps

if __name__ == "__main__":
    print("Analyzing Hydrawise failure patterns...")
    
    analysis = analyze_failure_patterns()
    
    print(f"\n=== SUMMARY ===")
    print(f"Total failure types identified: {len(analysis['failure_types'])}")
    print(f"Immediate alert patterns: {analysis['immediate_alerts']}")
    print(f"Warning patterns: {analysis['warning_alerts']}")
    
    print(f"\n=== RECOMMENDATIONS ===")
    for i, rec in enumerate(analysis['recommendations'], 1):
        print(f"{i}. {rec}")
    
    # Example gap detection for first zone
    if analysis['zone_failures']:
        first_zone = list(analysis['zone_failures'].keys())[0]
        print(f"\n=== GAP ANALYSIS EXAMPLE ({first_zone}) ===")
        
        # Re-read first zone data for gap analysis
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        runs_file = os.path.join(data_dir, 'hydrawise-watering-report (3).xls')
        zone_df = pd.read_excel(runs_file, sheet_name=first_zone)
        
        gaps = detect_schedule_gaps(zone_df)
        if gaps:
            print(f"Found {len(gaps)} potential system failures:")
            for gap in gaps[:5]:  # Show first 5
                print(f"  {gap['start']} to {gap['end']} ({gap['duration_hours']:.1f} hours)")
        else:
            print("No significant gaps detected")
