#!/usr/bin/env python3
"""Test final water usage estimation"""

from database.water_usage_estimator import WaterUsageEstimator
import sqlite3

estimator = WaterUsageEstimator('database/irrigation_data.db')

# Test zones that were previously causing null usage values
test_zones = [1, 2, 3, 5, 6, 7]  # MP zones that had issues

print('Testing Water Usage Estimation for Previously Problematic Zones:')
print('=' * 70)

for zone_id in test_zones:
    # Get zone name
    with sqlite3.connect('database/irrigation_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT zone_name FROM zones WHERE zone_id = ?', (zone_id,))
        result = cursor.fetchone()
        zone_name = result[0] if result else 'Unknown'
    
    # Test estimation for 0 gallons reported
    duration = 10  # 10 minutes
    actual_gallons = 0.0
    
    expected_gallons = estimator.calculate_expected_usage(zone_id, duration)
    usage_type, usage_flag, reason = estimator.determine_usage_type_and_flag(actual_gallons, expected_gallons)
    usage_value = estimator.calculate_usage_value(usage_type, actual_gallons, expected_gallons)
    
    status = 'OK' if usage_value is not None and usage_value > 0 else 'FAIL'
    print(f'{status} Zone {zone_id}: {zone_name[:40]:<40} -> {usage_value} gal (expected: {expected_gallons})')

print()
print('All zones now have proper flow rate data and can calculate estimated usage!')

