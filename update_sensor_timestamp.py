#!/usr/bin/env python3
"""
Update the sensor deactivation timestamp to match actual restoration time
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager
from datetime import datetime

def main():
    db = get_universal_database_manager()
    
    # The actual restoration time based on sensor history
    actual_restoration_time = '2025-10-27 13:30:30'
    
    print(f"Updating SENSOR_DEACTIVATED record to reflect actual restoration time: {actual_restoration_time}")
    
    db.adapter.execute_insert("""
        UPDATE status_changes
        SET detected_at = %s,
            change_description = 'Rain sensor stopped stopping irrigation - irrigation restored (actual time)'
        WHERE id = 4
    """, (actual_restoration_time,))
    
    # Verify
    result = db.adapter.execute_query("""
        SELECT id, change_type, detected_at, notification_sent
        FROM status_changes
        WHERE id = 4
    """)
    
    if result:
        print(f"✅ Updated record ID 4:")
        print(f"   Detected at: {result[0]['detected_at']}")
        print(f"   Notification sent: {result[0]['notification_sent']}")
        print("\n✅ Ready for automated_collector to send restoration email!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

