#!/usr/bin/env python3
"""
Test Sensor Restoration Email Logic

This script tests the new sensor restoration notification functionality
without actually sending emails or requiring the full system to be running.

It simulates various sensor status change scenarios and verifies that:
1. Restoration emails are sent once when sensor deactivates
2. Critical alerts are sent every time when sensor is active
3. No duplicate restoration emails during same non-stopping period
4. New restoration email sent after sensor reactivates and deactivates again
"""

import sys
import os
from datetime import date, datetime

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.comprehensive_status_monitor import ComprehensiveStatusMonitor, ChangeDetectionResult, CurrentStatusAlert
from database.universal_database_manager import get_universal_database_manager
from utils.timezone_utils import get_houston_now

def setup_test_database():
    """Clean up any test data from previous runs"""
    print("\n[SETUP] Cleaning test data from status_changes table...")
    try:
        db = get_universal_database_manager()
        # Delete test sensor change records
        db.adapter.execute_insert("""
            DELETE FROM status_changes 
            WHERE change_type IN ('SENSOR_ACTIVATED', 'SENSOR_DEACTIVATED')
            AND change_date >= CURRENT_DATE - INTERVAL '7 days'
        """, ())
        print("[SETUP] Test data cleaned successfully")
    except Exception as e:
        print(f"[SETUP ERROR] Failed to clean test data: {e}")

def insert_test_sensor_change(change_type: str, notification_sent: bool = False):
    """Insert a test sensor change record"""
    db = get_universal_database_manager()
    now = get_houston_now()
    
    if change_type == 'SENSOR_ACTIVATED':
        desc = 'Rain sensor started stopping irrigation'
    else:
        desc = 'Rain sensor stopped stopping irrigation - irrigation restored'
    
    change_id = db.adapter.execute_insert("""
        INSERT INTO status_changes (
            change_date, change_type, change_description,
            previous_value, new_value, sensor_status,
            notification_sent, detected_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        now.date().isoformat(),
        change_type,
        desc,
        'True' if change_type == 'SENSOR_DEACTIVATED' else 'False',
        'False' if change_type == 'SENSOR_DEACTIVATED' else 'True',
        f'Test {change_type}',
        notification_sent,
        now.isoformat()
    ))
    
    return change_id

def test_scenario_1_sensor_deactivation_first_time():
    """Test: Sensor deactivates - should send restoration email"""
    print("\n" + "="*70)
    print("TEST SCENARIO 1: Sensor Deactivates (First Time)")
    print("="*70)
    print("Expected: Should send restoration email (notification not yet sent)")
    
    # Insert SENSOR_DEACTIVATED record with notification_sent=FALSE
    change_id = insert_test_sensor_change('SENSOR_DEACTIVATED', notification_sent=False)
    print(f"[TEST] Inserted SENSOR_DEACTIVATED record (ID: {change_id}, notification_sent=FALSE)")
    
    # Test the email decision logic
    monitor = ComprehensiveStatusMonitor()
    
    # Create mock objects
    change_results = ChangeDetectionResult(
        changes_detected=0, changes_by_type={}, affected_zones=[],
        total_gallons_lost=0, requires_immediate_alert=False
    )
    current_alerts = []  # No critical alerts (sensor not stopping)
    
    # Check if email should be sent
    should_send = monitor.should_send_immediate_email(
        change_results, current_alerts,
        sensor_status_changed=True,
        sensor_change_type='SENSOR_DEACTIVATED',
        sensor_change_id=change_id
    )
    
    print(f"\n[RESULT] should_send_immediate_email returned: {should_send}")
    if should_send:
        print("✅ PASS: Email would be sent for restoration")
    else:
        print("❌ FAIL: Email would NOT be sent (but should be!)")
    
    return should_send

def test_scenario_2_sensor_deactivation_already_notified():
    """Test: Sensor still deactivated - should NOT send duplicate email"""
    print("\n" + "="*70)
    print("TEST SCENARIO 2: Sensor Still Deactivated (Already Notified)")
    print("="*70)
    print("Expected: Should NOT send email (restoration already notified)")
    
    # Mark the previous deactivation as notified
    db = get_universal_database_manager()
    now = get_houston_now()
    # First, get the most recent SENSOR_DEACTIVATED ID
    result = db.adapter.execute_query("""
        SELECT id FROM status_changes
        WHERE change_type = 'SENSOR_DEACTIVATED'
        ORDER BY detected_at DESC
        LIMIT 1
    """)
    if result:
        recent_id = result[0]['id']
        db.adapter.execute_insert("""
            UPDATE status_changes
            SET notification_sent = TRUE,
                notification_sent_at = %s
            WHERE id = %s
        """, (now.isoformat(), recent_id))
    print("[TEST] Marked most recent SENSOR_DEACTIVATED as notified")
    
    # Test the email decision logic
    monitor = ComprehensiveStatusMonitor()
    
    # Create mock objects
    change_results = ChangeDetectionResult(
        changes_detected=0, changes_by_type={}, affected_zones=[],
        total_gallons_lost=0, requires_immediate_alert=False
    )
    current_alerts = []  # No critical alerts
    
    # Simulate NO change detected (sensor still not stopping)
    should_send = monitor.should_send_immediate_email(
        change_results, current_alerts,
        sensor_status_changed=False,  # No change this time
        sensor_change_type=None,
        sensor_change_id=None
    )
    
    print(f"\n[RESULT] should_send_immediate_email returned: {should_send}")
    if not should_send:
        print("✅ PASS: Email would NOT be sent (no duplicate)")
    else:
        print("❌ FAIL: Email would be sent (duplicate!)")
    
    return not should_send  # Return True if passed (no email)

def test_scenario_3_sensor_activation():
    """Test: Sensor activates - should send critical alert"""
    print("\n" + "="*70)
    print("TEST SCENARIO 3: Sensor Activates (Starts Stopping)")
    print("="*70)
    print("Expected: Should send critical activation email")
    
    # Insert SENSOR_ACTIVATED record
    change_id = insert_test_sensor_change('SENSOR_ACTIVATED', notification_sent=False)
    print(f"[TEST] Inserted SENSOR_ACTIVATED record (ID: {change_id})")
    
    # Test the email decision logic
    monitor = ComprehensiveStatusMonitor()
    
    # Create mock objects
    change_results = ChangeDetectionResult(
        changes_detected=0, changes_by_type={}, affected_zones=[],
        total_gallons_lost=0, requires_immediate_alert=False
    )
    # Create critical alert (sensor is stopping irrigation)
    current_alerts = [
        CurrentStatusAlert(
            alert_type='sensor_active',
            severity='critical',
            message='Rain sensor is actively stopping ALL irrigation',
            affected_zones=['ALL_ZONES'],
            expected_gallons_lost=50.0,
            sensor_status='Sensor is stopping irrigation'
        )
    ]
    
    # Check if email should be sent
    should_send = monitor.should_send_immediate_email(
        change_results, current_alerts,
        sensor_status_changed=True,
        sensor_change_type='SENSOR_ACTIVATED',
        sensor_change_id=change_id
    )
    
    print(f"\n[RESULT] should_send_immediate_email returned: {should_send}")
    if should_send:
        print("✅ PASS: Email would be sent for sensor activation")
    else:
        print("❌ FAIL: Email would NOT be sent (but should be!)")
    
    return should_send

def test_scenario_4_sensor_still_active():
    """Test: Sensor still active - should send ongoing critical alert"""
    print("\n" + "="*70)
    print("TEST SCENARIO 4: Sensor Still Active (Ongoing Critical)")
    print("="*70)
    print("Expected: Should send email EVERY time (ongoing critical alert)")
    
    # Test the email decision logic
    monitor = ComprehensiveStatusMonitor()
    
    # Create mock objects
    change_results = ChangeDetectionResult(
        changes_detected=0, changes_by_type={}, affected_zones=[],
        total_gallons_lost=0, requires_immediate_alert=False
    )
    # Create critical alert (sensor is still stopping irrigation)
    current_alerts = [
        CurrentStatusAlert(
            alert_type='sensor_active',
            severity='critical',
            message='Rain sensor is actively stopping ALL irrigation',
            affected_zones=['ALL_ZONES'],
            expected_gallons_lost=50.0,
            sensor_status='Sensor is stopping irrigation'
        )
    ]
    
    # Check if email should be sent (no change, but critical alert exists)
    should_send = monitor.should_send_immediate_email(
        change_results, current_alerts,
        sensor_status_changed=False,  # No change - still active
        sensor_change_type=None,
        sensor_change_id=None
    )
    
    print(f"\n[RESULT] should_send_immediate_email returned: {should_send}")
    if should_send:
        print("✅ PASS: Email would be sent (ongoing critical alert)")
    else:
        print("❌ FAIL: Email would NOT be sent (but should be for ongoing critical!)")
    
    return should_send

def test_scenario_5_full_cycle():
    """Test: Full cycle - activate, deactivate, verify new restoration email can be sent"""
    print("\n" + "="*70)
    print("TEST SCENARIO 5: Full Cycle (Activate → Deactivate Again)")
    print("="*70)
    print("Expected: New restoration email should be allowed after reactivation")
    
    # Sensor deactivates again (after being active)
    change_id = insert_test_sensor_change('SENSOR_DEACTIVATED', notification_sent=False)
    print(f"[TEST] Inserted new SENSOR_DEACTIVATED record (ID: {change_id})")
    
    # Test the email decision logic
    monitor = ComprehensiveStatusMonitor()
    
    # Create mock objects
    change_results = ChangeDetectionResult(
        changes_detected=0, changes_by_type={}, affected_zones=[],
        total_gallons_lost=0, requires_immediate_alert=False
    )
    current_alerts = []  # No critical alerts
    
    # Check if email should be sent for new deactivation
    should_send = monitor.should_send_immediate_email(
        change_results, current_alerts,
        sensor_status_changed=True,
        sensor_change_type='SENSOR_DEACTIVATED',
        sensor_change_id=change_id
    )
    
    print(f"\n[RESULT] should_send_immediate_email returned: {should_send}")
    if should_send:
        print("✅ PASS: Email would be sent for new restoration after reactivation")
    else:
        print("❌ FAIL: Email would NOT be sent (but should be for new cycle!)")
    
    return should_send

def test_email_content_generation():
    """Test: Email content generation for different scenarios"""
    print("\n" + "="*70)
    print("TEST SCENARIO 6: Email Content Generation")
    print("="*70)
    
    monitor = ComprehensiveStatusMonitor()
    today = date.today()
    
    change_results = ChangeDetectionResult(
        changes_detected=0, changes_by_type={}, affected_zones=[],
        total_gallons_lost=0, requires_immediate_alert=False
    )
    
    # Test 1: Restoration email content
    print("\n[TEST 6A] Generating RESTORATION email content...")
    email = monitor.generate_comprehensive_email_content(
        change_results, [], today, 
        sensor_status_changed=True,
        sensor_change_type='SENSOR_DEACTIVATED'
    )
    print(f"Subject: {email['subject']}")
    print("Body preview:")
    print(email['body'][:300] + "...")
    if "IRRIGATION RESTORED" in email['subject'] and "GOOD NEWS" in email['body']:
        print("✅ PASS: Restoration email content looks correct")
        result_1 = True
    else:
        print("❌ FAIL: Restoration email content incorrect")
        result_1 = False
    
    # Test 2: Activation email content
    print("\n[TEST 6B] Generating ACTIVATION email content...")
    critical_alert = CurrentStatusAlert(
        alert_type='sensor_active', severity='critical',
        message='Rain sensor is actively stopping ALL irrigation',
        affected_zones=['ALL_ZONES'], expected_gallons_lost=50.0
    )
    email = monitor.generate_comprehensive_email_content(
        change_results, [critical_alert], today,
        sensor_status_changed=True,
        sensor_change_type='SENSOR_ACTIVATED'
    )
    print(f"Subject: {email['subject']}")
    print("Body preview:")
    print(email['body'][:300] + "...")
    if "ACTIVATED" in email['subject'] and "CRITICAL" in email['body']:
        print("✅ PASS: Activation email content looks correct")
        result_2 = True
    else:
        print("❌ FAIL: Activation email content incorrect")
        result_2 = False
    
    # Test 3: Ongoing critical email content
    print("\n[TEST 6C] Generating ONGOING CRITICAL email content...")
    email = monitor.generate_comprehensive_email_content(
        change_results, [critical_alert], today,
        sensor_status_changed=False,
        sensor_change_type=None
    )
    print(f"Subject: {email['subject']}")
    print("Body preview:")
    print(email['body'][:300] + "...")
    if "actively stopping" in email['subject'].lower() and "ONGOING" in email['body']:
        print("✅ PASS: Ongoing critical email content looks correct")
        result_3 = True
    else:
        print("❌ FAIL: Ongoing critical email content incorrect")
        result_3 = False
    
    return result_1 and result_2 and result_3

def main():
    """Run all test scenarios"""
    print("="*70)
    print("SENSOR RESTORATION EMAIL LOGIC TESTS")
    print("="*70)
    print("\nThis test suite verifies the sensor restoration notification logic")
    print("without actually sending emails or running the full collector.\n")
    
    # Setup
    setup_test_database()
    
    # Run tests
    results = []
    results.append(("Scenario 1: First Deactivation", test_scenario_1_sensor_deactivation_first_time()))
    results.append(("Scenario 2: Already Notified", test_scenario_2_sensor_deactivation_already_notified()))
    results.append(("Scenario 3: Activation", test_scenario_3_sensor_activation()))
    results.append(("Scenario 4: Ongoing Critical", test_scenario_4_sensor_still_active()))
    results.append(("Scenario 5: Full Cycle", test_scenario_5_full_cycle()))
    results.append(("Scenario 6: Email Content", test_email_content_generation()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Implementation is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

