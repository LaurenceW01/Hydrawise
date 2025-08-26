#!/usr/bin/env python3
"""
Water Usage Estimation Module

Implements intelligent water usage estimation for irrigation systems:
- Uses average flow rates to estimate water usage when actual usage is 0
- Flags unusual consumption (too high or too low)
- Calculates estimated vs actual usage for analysis

Author: AI Assistant
Date: 2025-01-27
"""

import logging
import sqlite3
import sys
import os
from typing import Dict, Optional, Tuple, Any
from datetime import datetime
from pytz import timezone

# Add project root to path for config imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.zone_configuration import get_zone_average_flow_rate

# Houston timezone for consistent timestamps
HOUSTON_TZ = timezone('America/Chicago')

logger = logging.getLogger(__name__)

class WaterUsageEstimator:
    """
    Handles water usage estimation and validation logic
    
    Key Features:
    - Estimates water usage for zones reporting 0 gallons
    - Validates reported usage against expected values
    - Flags high/low usage based on flow rate calculations
    - Updates actual_runs table with usage_type and usage columns
    """
    
    # Thresholds for determining if usage is unusual
    HIGH_USAGE_MULTIPLIER = 1.5  # Usage > 1.5x expected is considered too high
    LOW_USAGE_MULTIPLIER = 0.5   # Usage < 0.5x expected is considered too low
    
    def __init__(self, db_path: str):
        """Initialize the water usage estimator
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        
    def get_zone_average_flow_rate(self, zone_id: int) -> Optional[float]:
        """Get the average flow rate for a specific zone from configuration
        
        Args:
            zone_id: The zone ID to look up
            
        Returns:
            Average flow rate in GPM, or None if not found
        """
        try:
            # First try configuration
            flow_rate = get_zone_average_flow_rate(zone_id)
            if flow_rate is not None:
                return flow_rate
            
            # Fallback to database query if not in configuration
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT average_flow_rate 
                    FROM zones 
                    WHERE zone_id = ?
                """, (zone_id,))
                
                result = cursor.fetchone()
                if result and result[0] is not None:
                    logger.debug(f"Using database flow rate for zone {zone_id}: {result[0]} GPM")
                    return float(result[0])
                    
        except Exception as e:
            logger.error(f"Failed to get average flow rate for zone {zone_id}: {e}")
            
        return None
    
    def calculate_expected_usage(self, zone_id: int, duration_minutes: float) -> Optional[float]:
        """Calculate expected water usage based on zone flow rate and duration
        
        Args:
            zone_id: The zone ID
            duration_minutes: Duration the zone ran in minutes (can be fractional)
            
        Returns:
            Expected water usage in gallons, or None if calculation not possible
        """
        average_flow_rate = self.get_zone_average_flow_rate(zone_id)
        if average_flow_rate is None:
            logger.warning(f"No average flow rate found for zone {zone_id}")
            return None
            
        if duration_minutes <= 0:
            return 0.0
            
        # Expected usage = flow rate (GPM) * duration (minutes)
        expected_usage = average_flow_rate * duration_minutes
        logger.debug(f"Zone {zone_id}: {average_flow_rate} GPM * {duration_minutes} min = {expected_usage:.2f} gal")
        
        return expected_usage
    
    def determine_usage_type_and_flag(self, actual_gallons: Optional[float], expected_gallons: Optional[float]) -> Tuple[str, str, str]:
        """Determine usage type and flag for unusual consumption
        
        Args:
            actual_gallons: Reported water usage (can be None or 0)
            expected_gallons: Expected usage based on flow rate calculation
            
        Returns:
            Tuple of (usage_type, usage_flag, reason) where:
            - usage_type: 'actual' or 'estimated'
            - usage_flag: 'normal', 'too_high', 'too_low', or 'zero_reported'
            - reason: Human-readable explanation
        """
        # Handle missing expected usage
        if expected_gallons is None or expected_gallons <= 0:
            if actual_gallons is None or actual_gallons == 0:
                return 'estimated', 'zero_reported', 'No flow rate data available for estimation'
            return 'actual', 'normal', 'Using reported value (no flow rate reference)'
        
        # Handle zero or missing actual usage - estimate instead
        if actual_gallons is None or actual_gallons == 0:
            return 'estimated', 'zero_reported', 'Estimated due to zero reported usage'
        
        # Calculate usage ratio for actual reported values
        usage_ratio = actual_gallons / expected_gallons
        
        # Check if usage is too high (> 1.5x expected)
        if usage_ratio > self.HIGH_USAGE_MULTIPLIER:
            return 'actual', 'too_high', f'Usage {usage_ratio:.1f}x expected (>{self.HIGH_USAGE_MULTIPLIER}x threshold)'
        
        # Check if usage is too low (< 0.5x expected)  
        if usage_ratio < self.LOW_USAGE_MULTIPLIER:
            return 'actual', 'too_low', f'Usage {usage_ratio:.1f}x expected (<{self.LOW_USAGE_MULTIPLIER}x threshold)'
        
        # Usage is within normal range
        return 'actual', 'normal', f'Usage {usage_ratio:.1f}x expected (normal range)'
    
    def calculate_usage_value(self, usage_type: str, actual_gallons: Optional[float], expected_gallons: Optional[float]) -> Optional[float]:
        """Calculate the usage value to store in the usage column
        
        Args:
            usage_type: The determined usage type
            actual_gallons: Reported water usage
            expected_gallons: Expected usage based on flow rate
            
        Returns:
            Value to store in usage column (actual or estimated)
        """
        if usage_type == 'estimated':
            # Use estimated value when actual is 0 or missing
            # If expected_gallons is None (no flow rate data), return 0.0 instead of None
            return expected_gallons if expected_gallons is not None else 0.0
        else:
            # Use actual reported value for all other cases (actual, too_high, too_low)
            return actual_gallons
    
    def update_run_usage_data(self, run_id: int, zone_id: int, duration_minutes: float, actual_gallons: Optional[float]) -> Dict[str, Any]:
        """Update a single run's usage data with estimation logic
        
        Args:
            run_id: The actual_runs record ID to update
            zone_id: Zone ID for flow rate lookup
            duration_minutes: Duration the zone ran
            actual_gallons: Reported water usage
            
        Returns:
            Dictionary with update results and analysis
        """
        try:
            # Calculate expected usage
            expected_gallons = self.calculate_expected_usage(zone_id, duration_minutes)
            
            # Determine usage type, flag, and reasoning
            usage_type, usage_flag, reason = self.determine_usage_type_and_flag(actual_gallons, expected_gallons)
            
            # Calculate final usage value
            usage_value = self.calculate_usage_value(usage_type, actual_gallons, expected_gallons)
            
            # Update the database record
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE actual_runs 
                    SET usage_type = ?, usage = ?, usage_flag = ?, updated_at = ?
                    WHERE id = ?
                """, (usage_type, usage_value, usage_flag, self._get_houston_timestamp(), run_id))
                
                if cursor.rowcount == 0:
                    logger.warning(f"No rows updated for run_id {run_id}")
                    
                conn.commit()
            
            # Return analysis results
            return {
                'success': True,
                'run_id': run_id,
                'zone_id': zone_id,
                'actual_gallons': actual_gallons,
                'expected_gallons': expected_gallons,
                'usage_type': usage_type,
                'usage_flag': usage_flag,
                'usage_value': usage_value,
                'reason': reason,
                'duration_minutes': duration_minutes
            }
            
        except Exception as e:
            logger.error(f"Failed to update usage data for run {run_id}: {e}")
            return {
                'success': False,
                'run_id': run_id,
                'error': str(e)
            }
    
    def process_runs_for_date(self, target_date: str) -> Dict[str, Any]:
        """Process all runs for a specific date to update usage estimation
        
        Args:
            target_date: Date in YYYY-MM-DD format
            
        Returns:
            Summary of processing results
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all runs for the target date that need processing
                cursor.execute("""
                    SELECT id, zone_id, zone_name, actual_duration_minutes, actual_gallons
                    FROM actual_runs 
                    WHERE run_date = ? 
                    AND actual_duration_minutes > 0
                    ORDER BY zone_id, actual_start_time
                """, (target_date,))
                
                runs = cursor.fetchall()
                
            if not runs:
                return {
                    'success': True,
                    'date': target_date,
                    'total_runs': 0,
                    'message': 'No runs found for processing'
                }
            
            # Process each run
            results = []
            estimated_count = 0
            actual_count = 0
            too_high_count = 0
            too_low_count = 0
            zero_reported_count = 0
            
            for run_id, zone_id, zone_name, duration_minutes, actual_gallons in runs:
                result = self.update_run_usage_data(run_id, zone_id, duration_minutes, actual_gallons)
                results.append(result)
                
                if result.get('success'):
                    usage_type = result.get('usage_type')
                    usage_flag = result.get('usage_flag')
                    
                    if usage_type == 'estimated':
                        estimated_count += 1
                    elif usage_type == 'actual':
                        actual_count += 1
                    
                    if usage_flag == 'too_high':
                        too_high_count += 1
                    elif usage_flag == 'too_low':
                        too_low_count += 1
                    elif usage_flag == 'zero_reported':
                        zero_reported_count += 1
            
            # Summary
            total_processed = len([r for r in results if r.get('success')])
            
            logger.info(f"Processed {total_processed}/{len(runs)} runs for {target_date}")
            logger.info(f"  Usage Type - Estimated: {estimated_count}, Actual: {actual_count}")
            logger.info(f"  Usage Flags - Too High: {too_high_count}, Too Low: {too_low_count}, Zero Reported: {zero_reported_count}")
            
            return {
                'success': True,
                'date': target_date,
                'total_runs': len(runs),
                'processed_runs': total_processed,
                'estimated_count': estimated_count,
                'actual_count': actual_count,
                'too_high_count': too_high_count,
                'too_low_count': too_low_count,
                'zero_reported_count': zero_reported_count,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"Failed to process runs for {target_date}: {e}")
            return {
                'success': False,
                'date': target_date,
                'error': str(e)
            }
    
    def get_usage_summary(self, start_date: str, end_date: str = None) -> Dict[str, Any]:
        """Get a summary of usage types for a date range
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (optional, defaults to start_date)
            
        Returns:
            Summary statistics for the date range
        """
        if end_date is None:
            end_date = start_date
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        usage_type,
                        COUNT(*) as count,
                        SUM(usage) as total_usage,
                        AVG(usage) as avg_usage,
                        SUM(actual_gallons) as total_actual
                    FROM actual_runs 
                    WHERE run_date BETWEEN ? AND ?
                    AND actual_duration_minutes > 0
                    AND usage_type IS NOT NULL
                    GROUP BY usage_type
                    ORDER BY count DESC
                """, (start_date, end_date))
                
                usage_stats = {}
                for row in cursor.fetchall():
                    usage_type, count, total_usage, avg_usage, total_actual = row
                    usage_stats[usage_type] = {
                        'count': count,
                        'total_usage': total_usage or 0,
                        'avg_usage': avg_usage or 0,
                        'total_actual': total_actual or 0
                    }
                
                # Get overall totals
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_runs,
                        SUM(usage) as total_estimated_usage,
                        SUM(actual_gallons) as total_actual_usage
                    FROM actual_runs 
                    WHERE run_date BETWEEN ? AND ?
                    AND actual_duration_minutes > 0
                """, (start_date, end_date))
                
                totals = cursor.fetchone()
                
                return {
                    'success': True,
                    'date_range': f"{start_date} to {end_date}",
                    'total_runs': totals[0] if totals else 0,
                    'total_estimated_usage': totals[1] if totals else 0,
                    'total_actual_usage': totals[2] if totals else 0,
                    'usage_stats': usage_stats
                }
                
        except Exception as e:
            logger.error(f"Failed to get usage summary: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_houston_timestamp(self) -> str:
        """Get current timestamp in Houston timezone for database storage"""
        return datetime.now(HOUSTON_TZ).strftime('%Y-%m-%d %H:%M:%S')


def main():
    """Example usage and testing"""
    estimator = WaterUsageEstimator('database/irrigation_data.db')
    
    # Example: Process runs for a specific date
    from datetime import date, timedelta
    yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Processing water usage estimation for {yesterday}...")
    result = estimator.process_runs_for_date(yesterday)
    
    if result['success']:
        print(f"✅ Processed {result['processed_runs']} runs")
        print(f"   Estimated: {result['estimated_count']}")
        print(f"   Actual: {result['actual_count']}")
        print(f"   Too High: {result['too_high_count']}")
        print(f"   Too Low: {result['too_low_count']}")
    else:
        print(f"❌ Processing failed: {result.get('error')}")
    
    # Get usage summary
    summary = estimator.get_usage_summary(yesterday)
    if summary['success']:
        print(f"\n📊 Usage Summary for {yesterday}:")
        for usage_type, stats in summary['usage_stats'].items():
            print(f"   {usage_type}: {stats['count']} runs, {stats['total_usage']:.1f} gallons")


if __name__ == "__main__":
    main()
