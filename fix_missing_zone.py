#!/usr/bin/env python3
"""
Fix Missing Zone Script

Adds the missing "Left Side Turf (MP)" zone to prevent database lock issues
"""

import sys
import os
import sqlite3

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.intelligent_data_storage import IntelligentDataStorage

def fix_missing_zone():
    """Add the missing zone to the database"""
    
    print("Fixing missing zone: Left Side Turf (MP)")
    
    try:
        storage = IntelligentDataStorage('database/irrigation_data.db')
        
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if zone exists
            cursor.execute('SELECT zone_id FROM zones WHERE zone_name = ?', ('Left Side Turf (MP)',))
            if cursor.fetchone():
                print("Zone already exists: Left Side Turf (MP)")
                return True
                
            # Add the missing zone
            cursor.execute('''
                INSERT INTO zones (zone_id, zone_name, zone_display_name, priority_level, plant_type, notes)
                VALUES (18, 'Left Side Turf (MP)', 'Left Side Turf (MP)', 'LOW', 'turf', 'Added for missing zone')
            ''')
            conn.commit()
            print("Successfully added missing zone: Left Side Turf (MP)")
            return True
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    fix_missing_zone()
