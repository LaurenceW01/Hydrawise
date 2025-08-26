#!/usr/bin/env python3
"""
Database Rebuild Utility
Recreates a clean database from the existing data
"""

import sqlite3
import shutil
import os

def rebuild_database():
    """Rebuild the database to fix SQLite Browser compatibility issues"""
    
    print("[SYMBOL] Rebuilding database for SQLite Browser compatibility...")
    
    # Backup original
    backup_path = 'database/irrigation_data_backup.db'
    shutil.copy2('database/irrigation_data.db', backup_path)
    print(f"[SYMBOL] Backup created: {backup_path}")
    
    # Read data from original
    source_conn = sqlite3.connect('database/irrigation_data.db')
    source_cursor = source_conn.cursor()
    
    # Get zones data
    source_cursor.execute('SELECT * FROM zones ORDER BY zone_id')
    zones_data = source_cursor.fetchall()
    
    # Get usage_baselines data
    try:
        source_cursor.execute('SELECT * FROM usage_baselines')
        baselines_data = source_cursor.fetchall()
    except:
        baselines_data = []
    
    source_conn.close()
    print(f"[RESULTS] Found {len(zones_data)} zones, {len(baselines_data)} baselines")
    
    # Create new clean database
    new_path = 'database/irrigation_data_clean.db'
    new_conn = sqlite3.connect(new_path)
    new_cursor = new_conn.cursor()
    
    # Read and execute schema
    with open('database/schema.sql', 'r') as f:
        schema_sql = f.read()
    
    # Execute schema (split by semicolon for multiple statements)
    statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
    for statement in statements:
        try:
            new_cursor.execute(statement)
        except Exception as e:
            if 'already exists' not in str(e):
                print(f"[WARNING]  Schema warning: {e}")
    
    # Insert zones data
    for zone in zones_data:
        new_cursor.execute('''
        INSERT INTO zones (zone_id, zone_name, zone_display_name, priority_level, 
                          flow_rate_gpm, typical_duration_minutes, plant_type, 
                          install_date, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', zone)
    
    # Insert baselines if any (skip if table doesn't exist)
    if baselines_data:
        try:
            new_cursor.execute('SELECT 1 FROM usage_baselines LIMIT 1')
            for baseline in baselines_data:
                new_cursor.execute('''
                INSERT INTO usage_baselines VALUES (?, ?, ?, ?, ?, ?)
                ''', baseline)
            print(f"[RESULTS] Inserted {len(baselines_data)} baselines")
        except sqlite3.OperationalError:
            print("[WARNING]  Skipping baselines - table not in schema")
    
    new_conn.commit()
    
    # Verify
    new_cursor.execute('SELECT COUNT(*) FROM zones')
    zone_count = new_cursor.fetchone()[0]
    print(f"[OK] New database created with {zone_count} zones")
    
    new_conn.close()
    
    # Replace original
    os.replace('database/irrigation_data.db', 'database/irrigation_data_old.db')
    os.replace(new_path, 'database/irrigation_data.db')
    
    print("[OK] Database rebuilt successfully!")
    print("   Original: irrigation_data_old.db")
    print("   Backup: irrigation_data_backup.db") 
    print("   Current: irrigation_data.db (clean)")

if __name__ == "__main__":
    rebuild_database()
