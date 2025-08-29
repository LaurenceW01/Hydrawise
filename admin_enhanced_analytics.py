#!/usr/bin/env python3
"""
Enhanced Analytics CLI for Irrigation System

Provides comprehensive analytics for irrigation usage flags, zone health monitoring,
and flow meter performance analysis. This CLI focuses on:
- Usage flag pattern analysis (too_high, too_low, zero_reported)
- Zone health monitoring and investigation recommendations
- Daily usage comparison reports (actual vs calculated usage)
- Flow meter accuracy and reliability analysis
- Configurable deviation thresholds for usage analysis

Author: AI Assistant
Date: 2025-08-27
"""

import argparse
import sys
import os
import json
import logging
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from io import StringIO

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.usage_analytics import UsageAnalytics
from database.irrigation_analytics import IrrigationAnalytics
from utils.timezone_utils import get_houston_now, get_display_timestamp

class OutputLogger:
    """
    Custom logging class that captures stdout and writes to both console and log file
    with Houston timezone timestamps in the log filename
    """
    def __init__(self, log_filename=None):
        # Capture original stdout for console output
        self.console = sys.stdout
        # StringIO buffer to capture output for logging
        self.log_buffer = StringIO()
        # Flag to track if logging is enabled
        self.logging_enabled = log_filename is not None
        self.log_filename = log_filename
        
        if self.logging_enabled:
            # Ensure logs directory exists
            os.makedirs('logs', exist_ok=True)
            
    def write(self, text):
        """Write text to both console and log buffer"""
        # Always write to console for immediate display
        self.console.write(text)
        # If logging enabled, also capture to buffer
        if self.logging_enabled:
            self.log_buffer.write(text)
    
    def flush(self):
        """Flush both console and log buffer"""
        self.console.flush()
        if self.logging_enabled:
            self.log_buffer.flush()
    
    def save_log(self):
        """Save the captured output to log file with Houston timezone timestamp"""
        if not self.logging_enabled:
            return
            
        try:
            log_content = self.log_buffer.getvalue()
            if log_content.strip():  # Only save if there's actual content
                with open(self.log_filename, 'w', encoding='utf-8') as f:
                    # Add header with timestamp information
                    houston_now = get_houston_now()
                    f.write(f"# Enhanced Analytics Log\n")
                    f.write(f"# Generated: {get_display_timestamp(houston_now)}\n")
                    f.write(f"# Command: {' '.join(sys.argv)}\n")
                    f.write("#" + "=" * 68 + "\n\n")
                    f.write(log_content)
                print(f"\n[LOG] Output saved to: {self.log_filename}")
        except Exception as e:
            print(f"\n[ERROR] Failed to save log file: {e}")

def setup_logging(enable_logging=False):
    """
    Set up logging with Houston timezone timestamp in filename
    Returns the OutputLogger instance
    """
    if not enable_logging:
        return OutputLogger()  # Return logger with logging disabled
    
    # Generate filename with Houston timezone timestamp
    houston_now = get_houston_now()
    # Format: logfile-YYYYMMDD_HHMMSS.txt (avoiding special characters per user preference)
    timestamp_str = houston_now.strftime("%Y%m%d_%H%M%S")
    log_filename = f"logs/logfile-{timestamp_str}.txt"
    
    return OutputLogger(log_filename)

def print_banner():
    """Print the enhanced analytics banner"""
    print("=" * 70)
    print("[ENHANCED] HYDRAWISE USAGE & ZONE HEALTH ANALYTICS")
    print("=" * 70)

def _interpret_zone_data(zone_name: str, zone_data: dict, is_filtered: bool) -> str:
    """Generate smart interpretation of zone data based on patterns and anomalies"""
    flag_counts = zone_data['usage_flags']
    variance_pct = zone_data['variance_percentage']
    estimation_pct = zone_data['estimation_percentage']
    reporting_accuracy = zone_data['reporting_accuracy_percentage']
    total_runs = zone_data['total_runs']
    
    interpretations = []
    
    # High estimation percentage analysis
    if estimation_pct > 80:
        if flag_counts['zero_reported'] > total_runs * 0.8:
            interpretations.append("Flow meter likely not working - mostly zero readings")
        elif flag_counts['too_high'] > 0 and flag_counts['zero_reported'] > 0:
            interpretations.append("Flow meter has erratic readings - possible connection/power issues")
    elif estimation_pct > 50:
        interpretations.append("Significant flow meter reliability issues detected")
    
    # Variance analysis when filtered
    if is_filtered:
        if abs(variance_pct) < 5:
            interpretations.append("Flow rate appears accurate when anomalies filtered out")
        elif variance_pct > 15:
            interpretations.append("Flow rate may be too low - consider increasing average_flow_rate")
        elif variance_pct < -15:
            interpretations.append("Flow rate may be too high - consider reducing average_flow_rate")
    else:
        # Raw data analysis
        if variance_pct > 50:
            if flag_counts['too_high'] > 0:
                interpretations.append("Excessive high readings - possible valve leak or flow meter over-reporting")
            else:
                interpretations.append("Usage consistently higher than expected - flow rate may need adjustment")
        elif variance_pct > 25:
            interpretations.append("Moderate over-reporting - monitor for trends")
    
    # Reporting accuracy analysis
    if reporting_accuracy < 50:
        interpretations.append("Poor flow meter accuracy - frequent zero readings despite run activity")
    elif reporting_accuracy < 80:
        interpretations.append("Moderate flow meter issues - some readings not captured")
    
    # Specific flag pattern analysis
    if flag_counts['too_high'] > 0 and flag_counts['zero_reported'] > flag_counts['too_high']:
        interpretations.append("Classic flow meter lag pattern - zero followed by catch-up high readings")
    
    # Zone type specific insights
    if "Turf" in zone_name and flag_counts['zero_reported'] > total_runs * 0.6:
        interpretations.append("Turf zone with poor flow reporting - check for clogged meter or wiring issues")
    elif any(term in zone_name for term in ["Pots", "Planters", "Baskets"]) and variance_pct < -10:
        interpretations.append("Drip/micro irrigation may have lower actual flow than configured rate")
    
    # Recommendations based on patterns
    if len(interpretations) == 0:
        if abs(variance_pct) < 10 and estimation_pct < 20:
            return "Zone operating normally with good flow meter accuracy"
        else:
            return "Minor variance detected - continue monitoring"
    
    return " | ".join(interpretations)

def cmd_usage_flags(args):
    """Analyze usage flag patterns"""
    print_banner()
    print("[ANALYSIS] USAGE FLAG PATTERN ANALYSIS")
    print()
    
    try:
        analytics = UsageAnalytics(
            too_high_multiplier=args.too_high_threshold,
            too_low_multiplier=args.too_low_threshold
        )
        
        # Parse date range
        end_date = date.today()
        start_date = end_date - timedelta(days=args.days)
        
        if args.start_date:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        if args.end_date:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        
        print(f"Analysis Period: {start_date} to {end_date}")
        print(f"Deviation Thresholds: Too High >{args.too_high_threshold}x, Too Low <{args.too_low_threshold}x")
        print()
        
        # Get usage flag analysis
        analysis = analytics.analyze_usage_flags(start_date, end_date)
        
        # Display flag counts
        print("[RESULTS] Overall Usage Flag Distribution:")
        total_runs = sum(analysis.flag_counts.values())
        for flag, count in analysis.flag_counts.items():
            percentage = (count / total_runs * 100) if total_runs > 0 else 0
            print(f"  {flag.upper():<15}: {count:>6} runs ({percentage:5.1f}%)")
        print(f"  {'TOTAL':<15}: {total_runs:>6} runs")
        print()
        
        # Display problematic zones
        if analysis.problematic_zones:
            print("[ALERT] Problematic Zones Detected:")
            for zone_issue in analysis.problematic_zones:
                print(f"  - {zone_issue['zone_name']}: {zone_issue['description']}")
            print()
        
        # Display flow meter issues
        if analysis.flow_meter_issues:
            print("[WARNING] Flow Meter Issues Detected:")
            for issue in analysis.flow_meter_issues:
                print(f"  - {issue['zone_name']}: {issue['description']}")
                print(f"    Pattern: {' -> '.join(issue['pattern'])}")
            print()
        
        # Display missing usage summary
        missing_info = analysis.missing_usage_analysis
        print("[SUMMARY] Missing Usage Analysis:")
        print(f"  Total Actual Usage:     {missing_info['total_actual_usage']:8.2f} gallons")
        print(f"  Total Calculated Usage: {missing_info['total_calculated_usage']:8.2f} gallons")
        print(f"  Missing Percentage:     {missing_info['missing_percentage']:8.1f}%")
        print(f"  Estimated Usage Added:  {missing_info['estimated_gallons_used']:8.2f} gallons")
        print()
        
        # Zone-by-zone details if requested
        if args.detailed:
            print("[DETAILS] Zone-by-Zone Flag Analysis:")
            for zone_name, pattern in analysis.zone_flag_patterns.items():
                print(f"\n  Zone: {zone_name}")
                print(f"    Total Runs: {pattern['total_runs']}")
                print(f"    Flag Distribution:")
                for flag, percentage in pattern['flag_percentages'].items():
                    print(f"      {flag.upper():<12}: {percentage:5.1f}%")
                print(f"    Missing Usage: {pattern['missing_usage_percentage']:5.1f}%")
                if pattern['recent_issues']:
                    print(f"    Recent Issues: {', '.join([f'{date}:{flag}' for date, flag in pattern['recent_issues']])}")
        
        print("[SUCCESS] Usage flag analysis completed")
        
    except Exception as e:
        print(f"[ERROR] Failed to analyze usage flags: {e}")
        return False
    
    return True

def cmd_zone_health(args):
    """Identify zones needing investigation"""
    print_banner()
    print("[ANALYSIS] ZONE HEALTH MONITORING")
    print()
    
    try:
        analytics = UsageAnalytics(
            too_high_multiplier=args.too_high_threshold,
            too_low_multiplier=args.too_low_threshold
        )
        
        print(f"Analysis Period: Last {args.days} days")
        print(f"Deviation Thresholds: Too High >{args.too_high_threshold}x, Too Low <{args.too_low_threshold}x")
        print()
        
        # Get zones needing investigation
        investigation_zones = analytics.identify_zones_needing_investigation(args.days)
        
        if not investigation_zones:
            print("[SUCCESS] No zones currently require investigation - all zones operating normally")
            return True
        
        print(f"[ALERT] {len(investigation_zones)} zones require investigation:")
        print()
        
        for i, zone in enumerate(investigation_zones, 1):
            print(f"{i}. Zone: {zone.zone_name} - Priority: {zone.priority}")
            print(f"   Investigation Reason: {zone.investigation_reason}")
            print(f"   Recommendation: {zone.recommendation}")
            print(f"   Total Runs Analyzed: {zone.total_runs}")
            print(f"   Missing Usage: {zone.missing_usage_percentage:.1f}%")
            
            # Show flag summary
            print(f"   Flag Distribution:")
            for flag, percentage in zone.flag_summary.items():
                if percentage > 0:
                    print(f"     {flag.upper()}: {percentage:.1f}%")
            
            # Show recent issues
            if zone.recent_issues:
                print(f"   Recent Issues: {', '.join([f'{date}:{flag}' for date, flag in zone.recent_issues])}")
            
            print()
        
        # Priority breakdown
        priorities = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for zone in investigation_zones:
            priorities[zone.priority] += 1
        
        print("[SUMMARY] Priority Breakdown:")
        for priority, count in priorities.items():
            if count > 0:
                print(f"  {priority}: {count} zones")
        
        print("[ACTION] Review zones marked as HIGH priority immediately")
        
    except Exception as e:
        print(f"[ERROR] Failed to analyze zone health: {e}")
        return False
    
    return True

def cmd_daily_comparison(args):
    """Generate daily usage comparison report"""
    print_banner()
    print("[ANALYSIS] DAILY USAGE COMPARISON REPORT")
    print()
    
    try:
        analytics = UsageAnalytics(
            too_high_multiplier=args.too_high_threshold,
            too_low_multiplier=args.too_low_threshold
        )
        
        # Parse target date with support for 'today' and 'yesterday'
        target_date = date.today() - timedelta(days=1)  # Default to yesterday
        if args.date:
            if args.date.lower() == 'today':
                target_date = date.today()
            elif args.date.lower() == 'yesterday':
                target_date = date.today() - timedelta(days=1)
            else:
                target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        
        print(f"Analysis Date: {target_date}")
        print()
        
        # Get daily comparison report
        report = analytics.generate_daily_usage_comparison_report(target_date, args.filter_anomalies)
        
        if 'error' in report.totals:
            print(f"[WARNING] {report.totals['error']}")
            return True
        
        # Display overall totals
        totals = report.totals
        print("[SUMMARY] Overall Usage Comparison:")
        print(f"  Usage (from usage column):     {totals['total_usage_gallons']:8.2f} gallons")
        print(f"  Calculated (flow rate * time): {totals['total_calculated_gallons']:8.2f} gallons")
        print(f"  Variance:                      {totals['variance_gallons']:8.2f} gallons ({totals['variance_percentage']:+6.1f}%)")
        print(f"  Zones Analyzed:                {totals['zones_analyzed']:8} zones")
        print(f"  Total Runs:                    {totals['total_runs']:8} runs")
        print(f"  Estimated Runs:                {totals['estimated_runs']:8} runs ({totals['estimation_percentage']:5.1f}%)")
        
        if totals.get('use_estimated_for_anomalies'):
            print(f"  [FILTER] Anomaly filtering enabled - too_high/too_low values replaced with estimates")
        else:
            print(f"  [INFO] Using raw usage values - add --filter-anomalies to replace too_high/too_low with estimates")
        print()
        
        # Explain variance
        if totals['variance_percentage'] > 10:
            print(f"[ALERT] High positive variance suggests possible flow meter over-reporting")
        elif totals['variance_percentage'] < -10:
            print(f"[ALERT] High negative variance suggests possible flow meter under-reporting")
        else:
            print(f"[OK] Variance within acceptable range")
        print()
        
        # Zone-by-zone analysis if requested
        if args.detailed:
            print("[DETAILS] Zone-by-Zone Analysis:")
            for zone_name, zone_data in report.zone_comparisons.items():
                print(f"\n  Zone: {zone_name}")
                print(f"    Usage:        {zone_data['total_usage']:8.2f} gallons")
                print(f"    Calculated:   {zone_data['total_calculated']:8.2f} gallons")
                print(f"    Variance:     {zone_data['variance_gallons']:8.2f} gallons ({zone_data['variance_percentage']:+6.1f}%)")
                print(f"    Actual Reported: {zone_data['total_actual_gallons']:8.2f} gallons")
                print(f"    Reporting Accuracy: {zone_data['reporting_accuracy_percentage']:6.1f}%")
                print(f"    Unreported:   {zone_data['unreported_gallons']:8.2f} gallons")
                print(f"    Runs:         {zone_data['total_runs']:8} runs")
                print(f"    Estimated:    {zone_data['estimated_runs']:8} runs ({zone_data['estimation_percentage']:5.1f}%)")
                
                # Flag distribution
                flag_counts = zone_data['usage_flags']
                if sum(flag_counts.values()) > 0:
                    print(f"    Flags: ", end="")
                    flag_summary = []
                    for flag, count in flag_counts.items():
                        if count > 0:
                            flag_summary.append(f"{flag}:{count}")
                    print(", ".join(flag_summary))
                
                # Smart interpretation
                interpretation = _interpret_zone_data(zone_name, zone_data, totals.get('use_estimated_for_anomalies', False))
                if interpretation:
                    print(f"    [ANALYSIS] {interpretation}")
        
        # Methodology explanation
        print("\n[METHODOLOGY]")
        for key, description in report.analysis_summary.items():
            print(f"  {key.replace('_', ' ').title()}: {description}")
        
        print("[SUCCESS] Daily comparison report completed")
        
    except Exception as e:
        print(f"[ERROR] Failed to generate daily comparison: {e}")
        return False
    
    return True

def cmd_flow_meter_performance(args):
    """Generate flow meter performance report"""
    print_banner()
    print("[ANALYSIS] FLOW METER PERFORMANCE REPORT")
    print()
    
    try:
        analytics = UsageAnalytics(
            too_high_multiplier=args.too_high_threshold,
            too_low_multiplier=args.too_low_threshold
        )
        
        print(f"Analysis Period: Last {args.days} days")
        print()
        
        # Get flow meter performance report
        report = analytics.generate_flow_meter_performance_report(args.days)
        
        if 'error' in report:
            print(f"[WARNING] {report['error']}")
            return True
        
        # Display overall metrics
        metrics = report['overall_metrics']
        print("[SUMMARY] Overall Flow Meter Performance:")
        print(f"  Total Runs Analyzed:     {metrics['total_runs_analyzed']:6}")
        print(f"  Successful Readings:     {metrics['successful_readings']:6} ({metrics['accuracy_percentage']:5.1f}%)")
        print(f"  Zero Readings:           {metrics['zero_readings']:6}")
        print(f"  High Readings:           {metrics['high_readings']:6}")
        print(f"  Low Readings:            {metrics['low_readings']:6}")
        print(f"  Overall Failure Rate:    {metrics['failure_percentage']:5.1f}%")
        print()
        
        # Performance grade summary
        grade_counts = {}
        for zone_name, zone_perf in report['zone_performance'].items():
            grade = zone_perf['performance_grade']
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
        
        if grade_counts:
            print("[GRADES] Zone Performance Distribution:")
            for grade in ['A', 'B', 'C', 'D', 'F']:
                if grade in grade_counts:
                    print(f"  Grade {grade}: {grade_counts[grade]} zones")
            print()
        
        # Zone details if requested
        if args.detailed:
            print("[DETAILS] Zone-by-Zone Performance:")
            sorted_zones = sorted(report['zone_performance'].items(), 
                                key=lambda x: x[1]['accuracy_percentage'], reverse=True)
            
            for zone_name, zone_perf in sorted_zones:
                print(f"\n  Zone: {zone_name} (Grade: {zone_perf['performance_grade']})")
                print(f"    Accuracy:      {zone_perf['accuracy_percentage']:5.1f}%")
                print(f"    Missing Usage: {zone_perf['missing_usage_percentage']:5.1f}%")
                print(f"    Total Runs:    {zone_perf['total_runs']:6}")
        
        # Flow meter issues
        if report['flow_meter_issues']:
            print("[ALERT] Flow Meter Issues Detected:")
            for issue in report['flow_meter_issues']:
                print(f"  - {issue['zone_name']}: {issue['description']}")
        
        print("[SUCCESS] Flow meter performance report completed")
        
    except Exception as e:
        print(f"[ERROR] Failed to generate flow meter report: {e}")
        return False
    
    return True

def cmd_configure_thresholds(args):
    """Configure deviation thresholds"""
    print_banner()
    print("[CONFIG] CONFIGURE DEVIATION THRESHOLDS")
    print()
    
    print(f"Current Thresholds:")
    print(f"  Too High Multiplier: {args.too_high_threshold}x (usage > {args.too_high_threshold}x expected)")
    print(f"  Too Low Multiplier:  {args.too_low_threshold}x (usage < {args.too_low_threshold}x expected)")
    print()
    
    print("[INFO] These thresholds determine when usage is flagged as 'too_high' or 'too_low'")
    print("[INFO] Default values: too_high=2.0 (double), too_low=0.5 (half)")
    print("[INFO] Use command line arguments --too-high-threshold and --too-low-threshold to modify")
    print()
    
    # Test with current settings
    try:
        analytics = UsageAnalytics(
            too_high_multiplier=args.too_high_threshold,
            too_low_multiplier=args.too_low_threshold
        )
        
        print("[TEST] Testing current thresholds with recent data...")
        analysis = analytics.analyze_usage_flags(date.today() - timedelta(days=7), date.today())
        
        total_runs = sum(analysis.flag_counts.values())
        if total_runs > 0:
            print(f"  Sample from last 7 days ({total_runs} total runs):")
            for flag, count in analysis.flag_counts.items():
                percentage = (count / total_runs * 100)
                print(f"    {flag.upper()}: {count} runs ({percentage:.1f}%)")
        else:
            print(f"  No recent data available for testing")
        
        print("\n[SUCCESS] Threshold configuration displayed")
        
    except Exception as e:
        print(f"[ERROR] Failed to test thresholds: {e}")
        return False
    
    return True

def main():
    """Main CLI entry point"""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Enhanced Analytics CLI for Irrigation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s usage-flags --days 30 --detailed
  %(prog)s zone-health --too-high-threshold 2.5 --too-low-threshold 0.4
  %(prog)s daily-comparison --date today --detailed --filter-anomalies
  %(prog)s daily-comparison --date yesterday --detailed --log
  %(prog)s daily-comparison --date 2025-08-26 --detailed
  %(prog)s flow-meter --days 14 --detailed --log
  %(prog)s configure --too-high-threshold 3.0
        """
    )
    
    # Global arguments
    parser.add_argument('--too-high-threshold', type=float, default=2.0,
                       help='Multiplier for too_high usage flag (default: 2.0)')
    parser.add_argument('--too-low-threshold', type=float, default=0.5,
                       help='Multiplier for too_low usage flag (default: 0.5)')
    parser.add_argument('--log', action='store_true',
                       help='Save output to log file in logs/ directory with Houston timezone timestamp')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Usage flags analysis
    usage_parser = subparsers.add_parser('usage-flags', 
                                       help='Analyze usage flag patterns')
    usage_parser.add_argument('--days', type=int, default=30,
                            help='Days to analyze (default: 30)')
    usage_parser.add_argument('--start-date', type=str,
                            help='Start date (YYYY-MM-DD)')
    usage_parser.add_argument('--end-date', type=str,
                            help='End date (YYYY-MM-DD)')
    usage_parser.add_argument('--detailed', action='store_true',
                            help='Show detailed zone-by-zone analysis')
    
    # Zone health monitoring
    health_parser = subparsers.add_parser('zone-health',
                                        help='Monitor zone health and identify issues')
    health_parser.add_argument('--days', type=int, default=30,
                             help='Days to analyze (default: 30)')
    
    # Daily comparison report
    comparison_parser = subparsers.add_parser('daily-comparison',
                                            help='Generate daily usage comparison report')
    comparison_parser.add_argument('--date', type=str,
                                 help='Date to analyze (YYYY-MM-DD, "today", or "yesterday", default: yesterday)')
    comparison_parser.add_argument('--detailed', action='store_true',
                                 help='Show detailed zone-by-zone analysis')
    comparison_parser.add_argument('--filter-anomalies', action='store_true',
                                 help='Replace too_high/too_low usage values with estimated values to filter out anomalies for cleaner trend analysis')
    
    # Flow meter performance
    flow_parser = subparsers.add_parser('flow-meter',
                                      help='Analyze flow meter performance')
    flow_parser.add_argument('--days', type=int, default=30,
                           help='Days to analyze (default: 30)')
    flow_parser.add_argument('--detailed', action='store_true',
                           help='Show detailed zone-by-zone performance')
    
    # Configure thresholds
    config_parser = subparsers.add_parser('configure',
                                        help='Configure deviation thresholds')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Validate thresholds
    if args.too_high_threshold <= 1.0:
        print(f"[ERROR] too-high-threshold must be > 1.0 (got {args.too_high_threshold})")
        return 1
    
    if args.too_low_threshold >= 1.0:
        print(f"[ERROR] too-low-threshold must be < 1.0 (got {args.too_low_threshold})")
        return 1
    
    # Set up logging system if requested
    logger = setup_logging(enable_logging=args.log)
    original_stdout = sys.stdout
    
    try:
        # Redirect stdout to our logger if logging is enabled
        if logger.logging_enabled:
            sys.stdout = logger
            print(f"[LOG] Logging enabled - output will be saved to: {logger.log_filename}")
        
        # Route to appropriate command handler
        command_handlers = {
            'usage-flags': cmd_usage_flags,
            'zone-health': cmd_zone_health,
            'daily-comparison': cmd_daily_comparison,
            'flow-meter': cmd_flow_meter_performance,
            'configure': cmd_configure_thresholds
        }
        
        handler = command_handlers.get(args.command)
        if handler:
            success = handler(args)
            result = 0 if success else 1
        else:
            print(f"[ERROR] Unknown command: {args.command}")
            result = 1
            
    finally:
        # Always restore original stdout and save log if enabled
        sys.stdout = original_stdout
        if logger.logging_enabled:
            logger.save_log()
    
    return result

if __name__ == "__main__":
    sys.exit(main())
