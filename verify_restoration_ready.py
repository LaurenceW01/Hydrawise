#!/usr/bin/env python3
"""
Verification Script: Check if restoration notification is ready to be sent

This script verifies:
1. Database has unsent SENSOR_DEACTIVATED record
2. New code would detect and send the restoration email
3. Email configuration is set up correctly

Run this BEFORE restarting automated_collector to confirm everything is ready.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager
from utils.timezone_utils import get_houston_now
from datetime import datetime

def check_database_record():
    """Check if there's an unsent SENSOR_DEACTIVATED record in the database"""
    print("\n" + "="*70)
    print("STEP 1: Database Record Check")
    print("="*70)
    
    try:
        db = get_universal_database_manager()
        
        # Get all sensor change records to see the full picture
        all_results = db.adapter.execute_query("""
            SELECT id, change_type, notification_sent, change_date, detected_at, change_description
            FROM status_changes
            WHERE change_type IN ('SENSOR_ACTIVATED', 'SENSOR_DEACTIVATED')
            ORDER BY detected_at DESC
            LIMIT 5
        """)
        
        print("\nRecent sensor change records in database:")
        if all_results:
            for record in all_results:
                status = "✅ SENT" if record['notification_sent'] else "❌ NOT SENT"
                print(f"  ID {record['id']}: {record['change_type']} - {status}")
                print(f"    Detected: {record['detected_at']}")
                print(f"    Description: {record['change_description']}")
        else:
            print("  No sensor change records found!")
            return False
        
        # Check specifically for the most recent unsent SENSOR_DEACTIVATED
        results = db.adapter.execute_query("""
            SELECT id, change_type, notification_sent, change_date, detected_at
            FROM status_changes
            WHERE change_type IN ('SENSOR_ACTIVATED', 'SENSOR_DEACTIVATED')
            ORDER BY detected_at DESC
            LIMIT 2
        """)
        
        if not results:
            print("\n❌ FAIL: No sensor change records found at all")
            return False
        
        most_recent = results[0]
        
        print(f"\nMost recent sensor change:")
        print(f"  Type: {most_recent['change_type']}")
        print(f"  Notification sent: {most_recent['notification_sent']}")
        print(f"  Detected at: {most_recent['detected_at']}")
        
        # Check if it's SENSOR_DEACTIVATED and not sent
        if most_recent['change_type'] == 'SENSOR_ACTIVATED':
            print("\n❌ FAIL: Most recent record is SENSOR_ACTIVATED")
            print("   This means sensor is currently stopping irrigation")
            print("   No restoration email should be sent")
            return False
        
        if most_recent['change_type'] == 'SENSOR_DEACTIVATED':
            if not most_recent['notification_sent']:
                print(f"\n✅ PASS: Found unsent SENSOR_DEACTIVATED record (ID: {most_recent['id']})")
                print("   This restoration notification is ready to be sent!")
                return True
            else:
                print("\n❌ FAIL: SENSOR_DEACTIVATED record already has notification_sent=TRUE")
                print("   Restoration email was already sent")
                return False
        
        return False
        
    except Exception as e:
        print(f"\n❌ ERROR: Database check failed: {e}")
        return False

def check_sensor_history():
    """Check current sensor status from history"""
    print("\n" + "="*70)
    print("STEP 2: Current Sensor Status Check")
    print("="*70)
    
    try:
        db = get_universal_database_manager()
        today = get_houston_now().date()
        
        results = db.adapter.execute_query("""
            SELECT status_time, is_stopping_irrigation, sensor_status, scraped_at
            FROM rain_sensor_status_history
            WHERE status_date = %s
            ORDER BY scraped_at DESC
            LIMIT 3
        """, (today.isoformat(),))
        
        if not results:
            print(f"\n⚠️  WARNING: No sensor status history for {today}")
            return True
        
        print(f"\nMost recent sensor status readings for {today}:")
        for i, record in enumerate(results):
            stopping = "STOPPING" if record['is_stopping_irrigation'] else "NOT STOPPING"
            print(f"  {i+1}. {record['scraped_at']}: {stopping}")
            print(f"     Status: {record['sensor_status']}")
        
        latest = results[0]
        if latest['is_stopping_irrigation']:
            print("\n❌ FAIL: Sensor is currently STOPPING irrigation")
            print("   Restoration email should not be sent while sensor is active")
            return False
        else:
            print("\n✅ PASS: Sensor is currently NOT STOPPING irrigation")
            print("   This matches the expected state for restoration notification")
            return True
        
    except Exception as e:
        print(f"\n❌ ERROR: Sensor history check failed: {e}")
        return False

def test_new_code_logic():
    """Test if the new code logic would detect the unsent restoration"""
    print("\n" + "="*70)
    print("STEP 3: New Code Logic Test")
    print("="*70)
    
    try:
        from utils.comprehensive_status_monitor import ComprehensiveStatusMonitor
        
        monitor = ComprehensiveStatusMonitor()
        
        # Call the new method
        unsent_restoration = monitor._check_for_unsent_restoration()
        
        if unsent_restoration:
            print(f"\n✅ PASS: New code WOULD detect unsent restoration!")
            print(f"   Record ID: {unsent_restoration['id']}")
            print(f"   Detected at: {unsent_restoration['detected_at']}")
            print(f"   Notification sent: {unsent_restoration['notification_sent']}")
            return True
        else:
            print("\n❌ FAIL: New code would NOT detect unsent restoration")
            print("   Either no unsent record exists, or sensor is currently active")
            return False
        
    except Exception as e:
        print(f"\n❌ ERROR: Code logic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_email_config():
    """Check if email notifications are configured"""
    print("\n" + "="*70)
    print("STEP 4: Email Configuration Check")
    print("="*70)
    
    try:
        # Check environment variables
        email_enabled = os.getenv('EMAIL_NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
        recipients = os.getenv('EMAIL_RECIPIENTS', '').split(',')
        recipients = [r.strip() for r in recipients if r.strip()]
        smtp_username = os.getenv('SMTP_USERNAME', '')
        smtp_password = os.getenv('SMTP_PASSWORD', '')
        
        print(f"\nEmail configuration from environment:")
        print(f"  EMAIL_NOTIFICATIONS_ENABLED: {email_enabled}")
        print(f"  EMAIL_RECIPIENTS: {len(recipients)} recipient(s)")
        if recipients:
            for r in recipients:
                print(f"    - {r}")
        print(f"  SMTP_USERNAME: {'✅ Set' if smtp_username else '❌ Not set'}")
        print(f"  SMTP_PASSWORD: {'✅ Set' if smtp_password else '❌ Not set'}")
        
        if not email_enabled:
            print("\n⚠️  WARNING: Email notifications are DISABLED")
            print("   Emails will not be sent even if restoration is detected")
            return False
        
        if not recipients:
            print("\n❌ FAIL: No email recipients configured")
            return False
        
        if not smtp_username or not smtp_password:
            print("\n❌ FAIL: SMTP credentials not configured")
            return False
        
        print("\n✅ PASS: Email configuration looks good")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: Email config check failed: {e}")
        return False

def main():
    """Run all verification checks"""
    print("="*70)
    print("RESTORATION NOTIFICATION READINESS VERIFICATION")
    print("="*70)
    print("\nThis script verifies that the restoration email will be sent")
    print("when you restart automated_collector.py\n")
    
    results = {
        "database_record": check_database_record(),
        "sensor_status": check_sensor_history(),
        "new_code_logic": test_new_code_logic(),
        "email_config": check_email_config()
    }
    
    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name.replace('_', ' ').title()}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    
    if all_passed:
        print("✅ ALL CHECKS PASSED!")
        print("\nREADY TO RESTART automated_collector.py")
        print("\nWhat will happen on next collection run:")
        print("  1. Comprehensive monitoring checks database for unsent restorations")
        print("  2. Finds SENSOR_DEACTIVATED record with notification_sent=FALSE")
        print("  3. Sends restoration email to configured recipients")
        print("  4. Marks record as notification_sent=TRUE")
        print("  5. Future runs will not send duplicate emails")
        print("\nYou can now safely restart the automated collector service!")
        return 0
    else:
        print("⚠️  SOME CHECKS FAILED")
        print("\nPlease review the failed checks above before restarting.")
        print("The restoration email may not be sent until issues are resolved.")
        return 1

if __name__ == "__main__":
    sys.exit(main())


