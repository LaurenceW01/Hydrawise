#!/usr/bin/env python3
"""
Fix Test Records

Remove test sensor change records that were created during testing
and don't reflect actual sensor state.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager

def main():
    print("Fixing test sensor change records...")
    
    db = get_universal_database_manager()
    
    # Delete the test SENSOR_ACTIVATED record (ID 3) and the test SENSOR_DEACTIVATED (ID 2)
    # These were created during testing and don't reflect actual sensor state
    print("\nDeleting test records (IDs 2 and 3)...")
    db.adapter.execute_insert("""
        DELETE FROM status_changes
        WHERE id IN (2, 3)
    """, ())
    
    # Verify what's left
    results = db.adapter.execute_query("""
        SELECT id, change_type, notification_sent, detected_at, change_description
        FROM status_changes
        WHERE change_type IN ('SENSOR_ACTIVATED', 'SENSOR_DEACTIVATED')
        ORDER BY detected_at DESC
    """)
    
    print("\nRemaining sensor change records:")
    if results:
        for record in results:
            status = "SENT" if record['notification_sent'] else "NOT SENT"
            print(f"  ID {record['id']}: {record['change_type']} - {status}")
            print(f"    Detected: {record['detected_at']}")
            print(f"    Description: {record['change_description']}")
    else:
        print("  No records found!")
    
    print("\n✅ Test records cleaned up!")
    print("\nNow the most recent record should be:")
    print("  ID 4: SENSOR_DEACTIVATED (13:30:30) - NOT SENT")
    print("\nThis matches reality: sensor stopped stopping irrigation at 13:30")
    print("and the restoration notification hasn't been sent yet.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())


