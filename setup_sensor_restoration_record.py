#!/usr/bin/env python3
"""
Setup Script: Insert Sensor Restoration Record for Today

This script creates a SENSOR_DEACTIVATED record in the database for today's
sensor restoration event that already occurred before the new code was deployed.

This ensures that the next time automated_collector runs, it will:
1. Detect the existing SENSOR_DEACTIVATED record
2. See that notification_sent = FALSE
3. Send the restoration email once
4. Mark notification_sent = TRUE

Run this once to setup the initial state, then the system will take over.
"""

import sys
import os
from datetime import date

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager
from utils.timezone_utils import get_houston_now, get_database_timestamp

def check_existing_sensor_changes():
    """Check what sensor change records already exist for today"""
    print("\n[CHECK] Examining existing sensor change records for today...")
    
    try:
        db = get_universal_database_manager()
        today = get_houston_now().date()
        
        results = db.adapter.execute_query("""
            SELECT id, change_type, change_description, notification_sent, 
                   detected_at, change_date
            FROM status_changes
            WHERE change_type IN ('SENSOR_ACTIVATED', 'SENSOR_DEACTIVATED')
              AND change_date = %s
            ORDER BY detected_at DESC
        """, (today.isoformat(),))
        
        if not results:
            print(f"[CHECK] No sensor change records found for {today}")
            return None
        
        print(f"[CHECK] Found {len(results)} sensor change record(s) for {today}:")
        for record in results:
            status = "SENT" if record['notification_sent'] else "NOT SENT"
            print(f"  - ID: {record['id']}, Type: {record['change_type']}, Notification: {status}")
            print(f"    Description: {record['change_description']}")
            print(f"    Detected at: {record['detected_at']}")
        
        return results
        
    except Exception as e:
        print(f"[ERROR] Failed to check existing records: {e}")
        return None

def check_sensor_history():
    """Check the rain_sensor_status_history to understand what happened"""
    print("\n[CHECK] Examining rain sensor status history for today...")
    
    try:
        db = get_universal_database_manager()
        today = get_houston_now().date()
        
        results = db.adapter.execute_query("""
            SELECT status_time, sensor_status, is_stopping_irrigation, 
                   irrigation_suspended, scraped_at
            FROM rain_sensor_status_history
            WHERE status_date = %s
            ORDER BY scraped_at DESC
            LIMIT 10
        """, (today.isoformat(),))
        
        if not results:
            print(f"[CHECK] No sensor status history found for {today}")
            return None
        
        print(f"[CHECK] Recent sensor status history for {today}:")
        for i, record in enumerate(results):
            stopping = "STOPPING" if record['is_stopping_irrigation'] else "NOT STOPPING"
            print(f"  {i+1}. {record['scraped_at']}: {stopping} irrigation")
            print(f"     Status: {record['sensor_status']}")
        
        # Check if there was a change from stopping to not stopping
        if len(results) >= 2:
            recent = results[0]
            previous = results[1]
            
            if not recent['is_stopping_irrigation'] and previous['is_stopping_irrigation']:
                print("\n[DETECTED] Sensor changed from STOPPING to NOT STOPPING!")
                print(f"  Previous: STOPPING (at {previous['scraped_at']})")
                print(f"  Current:  NOT STOPPING (at {recent['scraped_at']})")
                return {
                    'change_detected': True,
                    'change_time': recent['scraped_at'],
                    'previous_status': previous['sensor_status'],
                    'current_status': recent['sensor_status']
                }
        
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to check sensor history: {e}")
        return None

def insert_sensor_deactivation_record():
    """Insert SENSOR_DEACTIVATED record for today's restoration event"""
    print("\n[INSERT] Creating SENSOR_DEACTIVATED record for today...")
    
    try:
        db = get_universal_database_manager()
        now = get_houston_now()
        
        # Insert the record
        change_id = db.adapter.execute_insert("""
            INSERT INTO status_changes (
                change_date, change_type, change_description,
                previous_value, new_value, sensor_status,
                notification_sent, notification_method, detected_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            now.date().isoformat(),                                    # change_date
            'SENSOR_DEACTIVATED',                                      # change_type
            'Rain sensor stopped stopping irrigation - irrigation restored',  # change_description
            'True',                                                    # previous_value (was stopping)
            'False',                                                   # new_value (now not stopping)
            'Sensor is not stopping irrigation',                       # sensor_status
            False,                                                     # notification_sent (FALSE so email will be sent)
            None,                                                      # notification_method (will be 'email' after sent)
            get_database_timestamp()                                   # detected_at (now)
        ))
        
        print(f"[SUCCESS] Created SENSOR_DEACTIVATED record (ID: {change_id})")
        print(f"[INFO] Notification status: NOT SENT (will trigger email on next run)")
        
        return change_id
        
    except Exception as e:
        print(f"[ERROR] Failed to insert sensor deactivation record: {e}")
        return None

def verify_setup():
    """Verify the setup is correct for the next automated_collector run"""
    print("\n[VERIFY] Checking if setup is ready for automated_collector...")
    
    try:
        db = get_universal_database_manager()
        today = get_houston_now().date()
        
        # Check for SENSOR_DEACTIVATED record with notification_sent = FALSE
        results = db.adapter.execute_query("""
            SELECT id, change_type, notification_sent, detected_at
            FROM status_changes
            WHERE change_type = 'SENSOR_DEACTIVATED'
              AND change_date = %s
              AND notification_sent = FALSE
            ORDER BY detected_at DESC
            LIMIT 1
        """, (today.isoformat(),))
        
        if results:
            record = results[0]
            print(f"[VERIFY] ✅ Found SENSOR_DEACTIVATED record ready for notification")
            print(f"  Record ID: {record['id']}")
            print(f"  Detected at: {record['detected_at']}")
            print(f"  Notification sent: {record['notification_sent']}")
            print("\n[READY] When automated_collector runs next:")
            print("  1. It will detect sensor_info['change_detected'] = False (no NEW change)")
            print("  2. But comprehensive monitor will check database and find unsent SENSOR_DEACTIVATED")
            print("  3. Email decision logic will see notification_sent = FALSE")
            print("  4. Restoration email will be sent")
            print("  5. Record will be marked notification_sent = TRUE")
            print("  6. Future runs will NOT send duplicate emails")
            return True
        else:
            print("[VERIFY] ❌ No SENSOR_DEACTIVATED record found or already notified")
            return False
        
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        return False

def main():
    """Main setup process"""
    print("="*70)
    print("SENSOR RESTORATION RECORD SETUP")
    print("="*70)
    print("\nThis script will prepare the database for the next automated_collector run")
    print("by inserting a SENSOR_DEACTIVATED record for today's restoration event.\n")
    
    # Step 1: Check what currently exists
    existing_changes = check_existing_sensor_changes()
    
    # Step 2: Check sensor history
    sensor_history = check_sensor_history()
    
    # Step 3: Determine if we need to insert a record
    if existing_changes:
        # Check if there's already a SENSOR_DEACTIVATED record today
        deactivation_exists = any(
            r['change_type'] == 'SENSOR_DEACTIVATED' 
            for r in existing_changes
        )
        
        if deactivation_exists:
            deactivation_record = next(
                r for r in existing_changes 
                if r['change_type'] == 'SENSOR_DEACTIVATED'
            )
            
            if not deactivation_record['notification_sent']:
                print("\n[INFO] SENSOR_DEACTIVATED record already exists and notification not sent.")
                print("[INFO] No action needed - system is ready.")
                verify_setup()
                return 0
            else:
                print("\n[WARNING] SENSOR_DEACTIVATED record exists but notification already sent.")
                print("[WARNING] If you need to re-send, you'll need to manually update the database.")
                return 1
    
    # Step 4: Insert the record
    print("\n[ACTION] No SENSOR_DEACTIVATED record found for today.")
    print("[ACTION] Creating record to trigger restoration email on next run...")
    
    change_id = insert_sensor_deactivation_record()
    
    if not change_id:
        print("\n[FAILURE] Failed to create sensor deactivation record.")
        return 1
    
    # Step 5: Verify setup
    if verify_setup():
        print("\n[SUCCESS] Setup complete! You can now:")
        print("  1. Commit the code changes")
        print("  2. Restart automated_collector.py")
        print("  3. The restoration email will be sent on the next collection run")
        return 0
    else:
        print("\n[FAILURE] Setup verification failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

