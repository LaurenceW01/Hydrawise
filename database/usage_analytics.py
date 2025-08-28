#!/usr/bin/env python3
"""
Enhanced Usage Analytics System

Specialized analytics for irrigation usage flags, zone health detection,
and flow meter performance analysis. This module focuses on:
- Smart usage flag pattern analysis (too_high, too_low, zero_reported)
- Zone health monitoring and investigation recommendations
- Daily usage comparison reports
- Flow meter accuracy and reliability analysis
- Missing usage detection and estimation

Author: AI Assistant
Date: 2025-08-27
"""

import sqlite3
import sys
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.timezone_utils import get_houston_now, get_display_timestamp

@dataclass
class ZoneHealthReport:
    """Zone health assessment report"""
    zone_name: str
    priority: str  # HIGH, MEDIUM, LOW
    total_runs: int
    issues: List[str]
    flag_summary: Dict[str, float]  # Percentages of each flag type
    recent_issues: List[Tuple[date, str]]  # Recent (date, flag) pairs
    missing_usage_percentage: float
    investigation_reason: str
    recommendation: str

@dataclass
class UsageFlagAnalysis:
    """Analysis results for usage flags"""
    period: str
    flag_counts: Dict[str, int]
    zone_flag_patterns: Dict[str, Dict]
    missing_usage_analysis: Dict[str, Any]
    problematic_zones: List[Dict[str, Any]]
    flow_meter_issues: List[Dict[str, Any]]

@dataclass
class DailyUsageComparison:
    """Daily usage comparison report"""
    date: str
    zone_comparisons: Dict[str, Dict]
    totals: Dict[str, Any]
    analysis_summary: Dict[str, str]

class UsageAnalytics:
    """
    Enhanced usage analytics system for irrigation monitoring
    
    Provides specialized analytics for:
    - Usage flag pattern analysis and anomaly detection
    - Zone health monitoring and maintenance recommendations
    - Flow meter performance and accuracy analysis
    - Daily usage variance reporting and trend analysis
    """
    
    def __init__(self, db_path: str = "database/irrigation_data.db", 
                 too_high_multiplier: float = 2.0, 
                 too_low_multiplier: float = 0.5):
        """Initialize usage analytics system
        
        Args:
            db_path: Path to SQLite database
            too_high_multiplier: Multiplier for too_high usage flag analysis
            too_low_multiplier: Multiplier for too_low usage flag analysis
        """
        self.db_path = db_path
        self.too_high_multiplier = too_high_multiplier
        self.too_low_multiplier = too_low_multiplier
    
    def set_deviation_thresholds(self, too_high_multiplier: float, too_low_multiplier: float):
        """Update configurable deviation thresholds
        
        Args:
            too_high_multiplier: New threshold for too_high usage flag analysis
            too_low_multiplier: New threshold for too_low usage flag analysis
        """
        self.too_high_multiplier = too_high_multiplier
        self.too_low_multiplier = too_low_multiplier
    
    def analyze_usage_flags(self, start_date: date = None, end_date: date = None) -> UsageFlagAnalysis:
        """Analyze patterns in usage flags to identify system issues
        
        Args:
            start_date: Start date for analysis (defaults to 30 days ago)
            end_date: End date for analysis (defaults to today)
            
        Returns:
            UsageFlagAnalysis object with comprehensive analysis results
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all runs with usage flag data
            cursor.execute("""
                SELECT actual_runs.zone_name, usage_flag, usage_type, usage, actual_gallons, 
                       actual_duration_minutes, run_date,
                       zones.flow_rate_gpm, zones.average_flow_rate
                FROM actual_runs 
                LEFT JOIN zones ON actual_runs.zone_id = zones.zone_id
                WHERE run_date BETWEEN ? AND ?
                ORDER BY actual_runs.zone_name, run_date
            """, (start_date, end_date))
            
            runs = cursor.fetchall()
        
        # Initialize analysis results
        analysis_data = {
            'period': f"{start_date} to {end_date}",
            'flag_counts': {'normal': 0, 'too_high': 0, 'too_low': 0, 'zero_reported': 0},
            'zone_flag_patterns': {},
            'missing_usage_analysis': {},
            'problematic_zones': [],
            'flow_meter_issues': []
        }
        
        zone_data = {}
        
        # Process each run
        for run in runs:
            zone_name, usage_flag, usage_type, usage, actual_gallons, duration, run_date, flow_rate, avg_flow_rate = run
            
            # Count flags
            analysis_data['flag_counts'][usage_flag] += 1
            
            # Track zone patterns
            if zone_name not in zone_data:
                zone_data[zone_name] = {
                    'total_runs': 0,
                    'flags': {'normal': 0, 'too_high': 0, 'too_low': 0, 'zero_reported': 0},
                    'actual_usage_sum': 0,
                    'estimated_usage_sum': 0,
                    'calculated_usage_sum': 0,
                    'consecutive_issues': 0,
                    'issue_pattern': []
                }
            
            zone_info = zone_data[zone_name]
            zone_info['total_runs'] += 1
            zone_info['flags'][usage_flag] += 1
            
            # Calculate expected usage using flow rate
            flow_rate_to_use = avg_flow_rate or flow_rate
            if flow_rate_to_use and duration:
                calculated_usage = flow_rate_to_use * duration  # GPM * minutes = gallons
                zone_info['calculated_usage_sum'] += calculated_usage
            
            # Track actual vs estimated usage
            if usage_type == 'actual' and actual_gallons:
                zone_info['actual_usage_sum'] += actual_gallons
            elif usage_type == 'estimated' and usage:
                zone_info['estimated_usage_sum'] += usage
            
            # Track consecutive issues
            if usage_flag != 'normal':
                zone_info['consecutive_issues'] += 1
                zone_info['issue_pattern'].append((run_date, usage_flag))
            else:
                zone_info['consecutive_issues'] = 0
        
        # Analyze patterns for each zone
        for zone_name, zone_info in zone_data.items():
            total_runs = zone_info['total_runs']
            flags = zone_info['flags']
            
            # Calculate percentages
            zone_pattern = {
                'total_runs': total_runs,
                'flag_percentages': {
                    flag: (count / total_runs * 100) if total_runs > 0 else 0 
                    for flag, count in flags.items()
                },
                'actual_usage_total': zone_info['actual_usage_sum'],
                'estimated_usage_total': zone_info['estimated_usage_sum'],
                'calculated_usage_total': zone_info['calculated_usage_sum'],
                'consecutive_issues': zone_info['consecutive_issues'],
                'recent_issues': zone_info['issue_pattern'][-5:] if zone_info['issue_pattern'] else []
            }
            
            # Calculate missing usage percentage
            total_reported = zone_info['actual_usage_sum'] + zone_info['estimated_usage_sum']
            calculated_total = zone_info['calculated_usage_sum']
            if calculated_total > 0:
                missing_percentage = ((calculated_total - zone_info['actual_usage_sum']) / calculated_total) * 100
                zone_pattern['missing_usage_percentage'] = missing_percentage
            else:
                zone_pattern['missing_usage_percentage'] = 0
            
            analysis_data['zone_flag_patterns'][zone_name] = zone_pattern
            
            # Identify problematic zones
            if flags['zero_reported'] > total_runs * 0.3:  # More than 30% zero reported
                analysis_data['problematic_zones'].append({
                    'zone_name': zone_name,
                    'issue': 'high_zero_reported',
                    'percentage': flags['zero_reported'] / total_runs * 100,
                    'description': f"Zone has {flags['zero_reported']} zero-reported runs out of {total_runs} total"
                })
            
            if flags['too_high'] > total_runs * 0.2:  # More than 20% too high
                analysis_data['problematic_zones'].append({
                    'zone_name': zone_name,
                    'issue': 'frequent_high_usage',
                    'percentage': flags['too_high'] / total_runs * 100,
                    'description': f"Zone frequently reports high usage: {flags['too_high']} out of {total_runs} runs"
                })
            
            # Flow meter catch-up pattern detection
            if len(zone_info['issue_pattern']) >= 3:
                recent_pattern = [issue[1] for issue in zone_info['issue_pattern'][-5:]]
                if ('zero_reported' in recent_pattern or 'too_low' in recent_pattern) and 'too_high' in recent_pattern:
                    analysis_data['flow_meter_issues'].append({
                        'zone_name': zone_name,
                        'pattern': recent_pattern,
                        'description': "Possible flow meter lag - zero/low followed by high usage"
                    })
        
        # Overall missing usage analysis
        total_actual = sum(zone['actual_usage_sum'] for zone in zone_data.values())
        total_calculated = sum(zone['calculated_usage_sum'] for zone in zone_data.values())
        if total_calculated > 0:
            overall_missing_percentage = ((total_calculated - total_actual) / total_calculated) * 100
        else:
            overall_missing_percentage = 0
        
        analysis_data['missing_usage_analysis'] = {
            'total_actual_usage': total_actual,
            'total_calculated_usage': total_calculated,
            'missing_percentage': overall_missing_percentage,
            'estimated_gallons_used': sum(zone['estimated_usage_sum'] for zone in zone_data.values())
        }
        
        return UsageFlagAnalysis(**analysis_data)
    
    def generate_daily_usage_comparison_report(self, target_date: date = None, 
                                             use_estimated_for_anomalies: bool = False) -> DailyUsageComparison:
        """Generate comparison report between actual usage and calculated usage for a specific day
        
        Args:
            target_date: Date to analyze (defaults to yesterday)
            use_estimated_for_anomalies: If True, replace too_high/too_low values with estimated values
            
        Returns:
            DailyUsageComparison object with comprehensive comparison data
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)  # Default to yesterday
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all runs for the target date with zone flow rates
            cursor.execute("""
                SELECT ar.zone_name, ar.usage, ar.usage_type, ar.usage_flag,
                       ar.actual_duration_minutes, ar.actual_gallons,
                       z.flow_rate_gpm, z.average_flow_rate
                FROM actual_runs ar
                LEFT JOIN zones z ON ar.zone_id = z.zone_id
                WHERE ar.run_date = ?
                ORDER BY ar.zone_name, ar.actual_start_time
            """, (target_date,))
            
            runs = cursor.fetchall()
        
        if not runs:
            return DailyUsageComparison(
                date=str(target_date),
                zone_comparisons={},
                totals={'error': 'No data found for the specified date'},
                analysis_summary={}
            )
        
        zone_comparisons = {}
        total_usage = 0
        total_calculated = 0
        total_estimated_runs = 0
        total_runs = 0
        
        # Process runs by zone
        for run in runs:
            zone_name, usage, usage_type, usage_flag, duration, actual_gallons, flow_rate, avg_flow_rate = run
            total_runs += 1
            
            if zone_name not in zone_comparisons:
                zone_comparisons[zone_name] = {
                    'runs': [],
                    'total_usage': 0,
                    'total_calculated': 0,
                    'total_actual_gallons': 0,
                    'usage_flags': {'normal': 0, 'too_high': 0, 'too_low': 0, 'zero_reported': 0},
                    'estimated_runs': 0,
                    'total_runs': 0
                }
            
            zone_data = zone_comparisons[zone_name]
            zone_data['total_runs'] += 1
            
            # Calculate expected usage using flow rate
            flow_rate_to_use = avg_flow_rate or flow_rate
            calculated_usage = 0
            if flow_rate_to_use and duration:
                calculated_usage = flow_rate_to_use * duration  # GPM * minutes = gallons
            
            # Determine if we should use estimated value
            use_estimated = False
            if use_estimated_for_anomalies and usage_flag in ['too_high', 'too_low']:
                use_estimated = True
                zone_data['estimated_runs'] += 1
                total_estimated_runs += 1
            elif usage_flag == 'zero_reported':
                use_estimated = True
                zone_data['estimated_runs'] += 1
                total_estimated_runs += 1
            
            # Track usage - use calculated if we're estimating anomalies, otherwise use reported usage
            if use_estimated:
                run_usage = calculated_usage
            else:
                run_usage = usage if usage else 0
            
            # Track actual gallons reported
            run_actual = actual_gallons if actual_gallons else 0
            
            zone_data['runs'].append({
                'duration_minutes': duration,
                'usage': run_usage,
                'usage_type': usage_type,
                'usage_flag': usage_flag,
                'actual_gallons': run_actual,
                'calculated_usage': calculated_usage,
                'flow_rate_used': flow_rate_to_use,
                'is_estimated': use_estimated
            })
            
            zone_data['total_usage'] += run_usage
            zone_data['total_calculated'] += calculated_usage
            zone_data['total_actual_gallons'] += run_actual
            zone_data['usage_flags'][usage_flag] += 1
            
            total_usage += run_usage
            total_calculated += calculated_usage
        
        # Calculate variances and add zone analysis
        for zone_name, zone_data in zone_comparisons.items():
            usage_total = zone_data['total_usage']
            calculated_total = zone_data['total_calculated']
            zone_total_runs = zone_data['total_runs']
            zone_estimated_runs = zone_data['estimated_runs']
            
            if calculated_total > 0:
                variance_percentage = ((usage_total - calculated_total) / calculated_total) * 100
                zone_data['variance_percentage'] = variance_percentage
                zone_data['variance_gallons'] = usage_total - calculated_total
            else:
                zone_data['variance_percentage'] = 0
                zone_data['variance_gallons'] = usage_total
            
            # Calculate estimation percentage
            estimation_percentage = (zone_estimated_runs / zone_total_runs * 100) if zone_total_runs > 0 else 0
            zone_data['estimation_percentage'] = estimation_percentage
            
            # Calculate reporting accuracy
            actual_total = zone_data['total_actual_gallons']
            if calculated_total > 0:
                reporting_accuracy = (actual_total / calculated_total) * 100
                zone_data['reporting_accuracy_percentage'] = min(reporting_accuracy, 100)  # Cap at 100%
                zone_data['unreported_gallons'] = max(0, calculated_total - actual_total)
            else:
                zone_data['reporting_accuracy_percentage'] = 100 if actual_total == 0 else 0
                zone_data['unreported_gallons'] = 0
        
        # Overall totals and analysis
        overall_variance = total_usage - total_calculated
        overall_variance_percentage = (overall_variance / total_calculated * 100) if total_calculated > 0 else 0
        overall_estimation_percentage = (total_estimated_runs / total_runs * 100) if total_runs > 0 else 0
        
        totals = {
            'total_usage_gallons': total_usage,
            'total_calculated_gallons': total_calculated,
            'variance_gallons': overall_variance,
            'variance_percentage': overall_variance_percentage,
            'zones_analyzed': len(zone_comparisons),
            'total_runs': total_runs,
            'estimated_runs': total_estimated_runs,
            'estimation_percentage': overall_estimation_percentage,
            'use_estimated_for_anomalies': use_estimated_for_anomalies
        }
        
        analysis_summary = {
            'usage_methodology': 'Uses the usage column which contains actual or estimated values',
            'calculation_methodology': 'Uses zone flow_rate_gpm * duration_minutes',
            'positive_variance': 'Usage > Calculated (possible flow meter over-reporting)',
            'negative_variance': 'Usage < Calculated (possible flow meter under-reporting or issues)'
        }
        
        return DailyUsageComparison(
            date=str(target_date),
            zone_comparisons=zone_comparisons,
            totals=totals,
            analysis_summary=analysis_summary
        )
    
    def identify_zones_needing_investigation(self, days_back: int = 30) -> List[ZoneHealthReport]:
        """Identify zones that may need investigation or repair based on usage patterns
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            List of ZoneHealthReport objects with investigation recommendations
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Get usage flag analysis
        usage_analysis = self.analyze_usage_flags(start_date, end_date)
        
        investigation_zones = []
        
        for zone_name, pattern in usage_analysis.zone_flag_patterns.items():
            recommendations = []
            priority = 'LOW'
            
            # Check for high zero reporting
            zero_percentage = pattern['flag_percentages']['zero_reported']
            if zero_percentage > 50:
                recommendations.append(f"High zero usage reporting ({zero_percentage:.1f}% of runs)")
                priority = 'HIGH'
            elif zero_percentage > 30:
                recommendations.append(f"Moderate zero usage reporting ({zero_percentage:.1f}% of runs)")
                priority = 'MEDIUM' if priority == 'LOW' else priority
            
            # Check for frequent high usage
            high_percentage = pattern['flag_percentages']['too_high']
            if high_percentage > 30:
                recommendations.append(f"Frequent high usage readings ({high_percentage:.1f}% of runs)")
                priority = 'HIGH'
            elif high_percentage > 15:
                recommendations.append(f"Moderate high usage readings ({high_percentage:.1f}% of runs)")
                priority = 'MEDIUM' if priority == 'LOW' else priority
            
            # Check for low usage
            low_percentage = pattern['flag_percentages']['too_low']
            if low_percentage > 25:
                recommendations.append(f"Frequent low usage readings ({low_percentage:.1f}% of runs)")
                priority = 'MEDIUM' if priority == 'LOW' else priority
            
            # Check for missing usage
            missing_percentage = pattern.get('missing_usage_percentage', 0)
            if missing_percentage > 60:
                recommendations.append(f"High missing usage ({missing_percentage:.1f}% unreported)")
                priority = 'HIGH'
            elif missing_percentage > 40:
                recommendations.append(f"Moderate missing usage ({missing_percentage:.1f}% unreported)")
                priority = 'MEDIUM' if priority == 'LOW' else priority
            
            # Check for consecutive issues
            if pattern['consecutive_issues'] > 5:
                recommendations.append(f"Ongoing issues ({pattern['consecutive_issues']} consecutive problematic runs)")
                priority = 'HIGH'
            
            # Only include zones with issues
            if recommendations:
                investigation_reason = self._generate_investigation_reason(pattern, recommendations)
                recommendation = self._generate_recommendation(pattern, priority)
                
                investigation_zones.append(ZoneHealthReport(
                    zone_name=zone_name,
                    priority=priority,
                    total_runs=pattern['total_runs'],
                    issues=recommendations,
                    flag_summary=pattern['flag_percentages'],
                    recent_issues=pattern['recent_issues'],
                    missing_usage_percentage=missing_percentage,
                    investigation_reason=investigation_reason,
                    recommendation=recommendation
                ))
        
        # Sort by priority and issue severity
        priority_order = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        investigation_zones.sort(key=lambda x: (priority_order[x.priority], len(x.issues)), reverse=True)
        
        return investigation_zones
    
    def _generate_investigation_reason(self, pattern: Dict, recommendations: List[str]) -> str:
        """Generate a human-readable investigation reason"""
        flag_percentages = pattern['flag_percentages']
        
        if flag_percentages['zero_reported'] > 50:
            return "Flow meter likely not reporting usage - check meter functionality and connections"
        elif flag_percentages['too_high'] > 30:
            return "Possible valve leak, stuck valve, or flow meter over-reporting - inspect zone physically"
        elif flag_percentages['too_low'] > 25 and flag_percentages['zero_reported'] > 20:
            return "Flow meter appears to be intermittently reporting - check meter calibration and wiring"
        elif pattern.get('missing_usage_percentage', 0) > 60:
            return "Significant usage not being captured by flow meter - verify meter installation and operation"
        else:
            return "Multiple usage anomalies detected - comprehensive zone inspection recommended"
    
    def _generate_recommendation(self, pattern: Dict, priority: str) -> str:
        """Generate specific maintenance recommendations"""
        flag_percentages = pattern['flag_percentages']
        
        if priority == 'HIGH':
            if flag_percentages['zero_reported'] > 50:
                return "URGENT: Check flow meter wiring, power supply, and sensor functionality. Zone may be running without usage tracking."
            elif flag_percentages['too_high'] > 30:
                return "URGENT: Inspect for valve leaks, stuck valves, or broken pipes. Check flow meter calibration."
            else:
                return "URGENT: Comprehensive zone inspection required - multiple critical issues detected."
        elif priority == 'MEDIUM':
            return "MAINTENANCE: Schedule inspection of flow meter and zone hardware within 1-2 weeks."
        else:
            return "MONITOR: Continue monitoring - consider inspection if issues persist or worsen."
    
    def generate_flow_meter_performance_report(self, days_back: int = 30) -> Dict[str, Any]:
        """Generate a comprehensive flow meter performance report
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            Dictionary with flow meter performance analysis
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        usage_analysis = self.analyze_usage_flags(start_date, end_date)
        
        # Calculate overall flow meter metrics
        total_runs = sum(usage_analysis.flag_counts.values())
        if total_runs == 0:
            return {'error': 'No data available for analysis period'}
        
        # Flow meter accuracy metrics
        accuracy_metrics = {
            'total_runs_analyzed': total_runs,
            'successful_readings': usage_analysis.flag_counts['normal'],
            'zero_readings': usage_analysis.flag_counts['zero_reported'],
            'high_readings': usage_analysis.flag_counts['too_high'],
            'low_readings': usage_analysis.flag_counts['too_low'],
            'accuracy_percentage': (usage_analysis.flag_counts['normal'] / total_runs * 100) if total_runs > 0 else 0,
            'failure_percentage': ((total_runs - usage_analysis.flag_counts['normal']) / total_runs * 100) if total_runs > 0 else 0
        }
        
        # Zone-specific performance
        zone_performance = {}
        for zone_name, pattern in usage_analysis.zone_flag_patterns.items():
            zone_total = pattern['total_runs']
            zone_performance[zone_name] = {
                'total_runs': zone_total,
                'accuracy_percentage': pattern['flag_percentages']['normal'],
                'missing_usage_percentage': pattern.get('missing_usage_percentage', 0),
                'performance_grade': self._calculate_performance_grade(pattern['flag_percentages'])
            }
        
        return {
            'analysis_period': f"{start_date} to {end_date}",
            'overall_metrics': accuracy_metrics,
            'zone_performance': zone_performance,
            'flow_meter_issues': usage_analysis.flow_meter_issues,
            'missing_usage_summary': usage_analysis.missing_usage_analysis
        }
    
    def _calculate_performance_grade(self, flag_percentages: Dict[str, float]) -> str:
        """Calculate a performance grade for a zone based on flag percentages"""
        normal_percentage = flag_percentages['normal']
        
        if normal_percentage >= 90:
            return 'A'
        elif normal_percentage >= 80:
            return 'B'
        elif normal_percentage >= 70:
            return 'C'
        elif normal_percentage >= 60:
            return 'D'
        else:
            return 'F'

def main():
    """Test the usage analytics system"""
    print("[TESTING] Usage Analytics System")
    print("=" * 60)
    
    analytics = UsageAnalytics()
    
    # Test usage flag analysis
    print("\n[ANALYSIS] Usage Flag Analysis (Last 30 days)")
    flag_analysis = analytics.analyze_usage_flags()
    print(f"Period: {flag_analysis.period}")
    print(f"Flag Counts: {flag_analysis.flag_counts}")
    print(f"Problematic Zones: {len(flag_analysis.problematic_zones)}")
    
    # Test daily comparison report
    print("\n[ANALYSIS] Daily Usage Comparison (Yesterday)")
    comparison = analytics.generate_daily_usage_comparison_report()
    print(f"Date: {comparison.date}")
    if 'error' not in comparison.totals:
        print(f"Total Usage: {comparison.totals['total_usage_gallons']:.2f} gallons")
        print(f"Total Calculated: {comparison.totals['total_calculated_gallons']:.2f} gallons")
        print(f"Variance: {comparison.totals['variance_percentage']:.1f}%")
    
    # Test zone investigation
    print("\n[ANALYSIS] Zones Needing Investigation")
    investigation_zones = analytics.identify_zones_needing_investigation()
    for zone in investigation_zones[:3]:  # Show top 3
        print(f"- {zone.zone_name} ({zone.priority}): {zone.investigation_reason}")
    
    print(f"\nTotal zones flagged for investigation: {len(investigation_zones)}")
    print("\n[COMPLETE] Usage analytics testing completed")

if __name__ == "__main__":
    main()
