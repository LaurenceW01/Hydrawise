#!/usr/bin/env python3
"""
Universal Hydrawise Database Manager
Handles all database operations for irrigation monitoring system using the universal adapter
Supports both SQLite (local) and PostgreSQL (render.com) databases

Author: AI Assistant
Date: 2025-01-27
"""

import logging
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Any
import sys
import hashlib
import json

# Add project root to path for config imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.universal_database_adapter import UniversalDatabaseAdapter, get_universal_adapter
from database.db_config import get_database_config, is_postgresql, is_sqlite
from config.zone_configuration import ZoneConfiguration
from utils.timezone_utils import get_database_timestamp

# Import our data models
from hydrawise_web_scraper_refactored import ScheduledRun, ActualRun

# Configure logging
logger = logging.getLogger(__name__)

class UniversalDatabaseManager:
    """
    Universal database manager that works with both SQLite and PostgreSQL
    Replaces the original DatabaseManager with multi-database support
    """
    
    def __init__(self):
        """Initialize universal database manager"""
        self.config = get_database_config()
        self.zone_config = ZoneConfiguration()
        self.adapter = get_universal_adapter()
        
        # Initialize database schema if needed
        self.init_database()
        
        logger.info(f"UniversalDatabaseManager initialized for {self.config.db_type} database")
    
    def init_database(self):
        """Initialize database with appropriate schema"""
        try:
            # Check if database is already initialized
            if self.adapter.table_exists('zones'):
                logger.info("Database already initialized - checking for schema updates")
                self._migrate_schema()
                return
            
            # Initialize with appropriate schema
            if is_postgresql():
                schema_path = os.path.join(os.path.dirname(__file__), 'postgresql_schema.sql')
            else:
                schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            
            # Read and execute schema
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            self.adapter.execute_script(schema_sql)
            logger.info(f"Database schema initialized successfully")
            
            # Initialize with basic zone data
            self._initialize_zones()
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _migrate_schema(self):
        """Apply schema migrations if needed"""
        try:
            # Check for missing columns and add them
            self._add_missing_columns()
            logger.info("Schema migration completed")
        except Exception as e:
            logger.warning(f"Schema migration failed: {e}")
    
    def _add_missing_columns(self):
        """Add any missing columns to existing tables"""
        # This is a simplified migration - in production you'd want more sophisticated migration tracking
        
        # Check if rain_sensor_status_history table exists (from tracking system)
        if not self.adapter.table_exists('rain_sensor_status_history'):
            logger.info("Adding rain sensor status history table")
            
            if is_postgresql():
                sql = """
                CREATE TABLE rain_sensor_status_history (
                    id SERIAL PRIMARY KEY,
                    status_date DATE NOT NULL,
                    sensor_enabled BOOLEAN NOT NULL,
                    sensor_active BOOLEAN NOT NULL,
                    status_text TEXT,
                    raw_status_data TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(status_date, scraped_at)
                );
                CREATE INDEX idx_rain_sensor_status_date ON rain_sensor_status_history(status_date);
                """
            else:
                sql = """
                CREATE TABLE rain_sensor_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status_date DATE NOT NULL,
                    sensor_enabled BOOLEAN NOT NULL,
                    sensor_active BOOLEAN NOT NULL,
                    status_text TEXT,
                    raw_status_data TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(status_date, scraped_at)
                );
                CREATE INDEX idx_rain_sensor_status_date ON rain_sensor_status_history(status_date);
                """
            
            self.adapter.execute_script(sql)
        
        # Check if status_changes table exists
        if not self.adapter.table_exists('status_changes'):
            logger.info("Adding status changes table")
            
            if is_postgresql():
                sql = """
                CREATE TABLE status_changes (
                    id SERIAL PRIMARY KEY,
                    change_date DATE NOT NULL,
                    change_type TEXT NOT NULL CHECK (change_type IN (
                        'SENSOR_ENABLED', 'SENSOR_DISABLED', 'SENSOR_ACTIVATED', 'SENSOR_DEACTIVATED',
                        'SCHEDULE_CHANGED', 'ZONE_STATUS_CHANGED', 'SYSTEM_STATUS_CHANGED'
                    )),
                    zone_id INTEGER,
                    zone_name TEXT,
                    
                    previous_value TEXT,
                    new_value TEXT,
                    change_description TEXT NOT NULL,
                    
                    sensor_status TEXT,
                    weather_conditions TEXT,
                    system_context TEXT,
                    
                    notification_sent BOOLEAN DEFAULT FALSE,
                    notification_method TEXT,
                    notification_recipients TEXT,
                    notification_sent_at TIMESTAMP,
                    
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
                );
                CREATE INDEX idx_status_changes_date_type ON status_changes(change_date, change_type);
                CREATE INDEX idx_status_changes_zone ON status_changes(zone_id, change_date);
                """
            else:
                sql = """
                CREATE TABLE status_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    change_date DATE NOT NULL,
                    change_type TEXT NOT NULL CHECK (change_type IN (
                        'SENSOR_ENABLED', 'SENSOR_DISABLED', 'SENSOR_ACTIVATED', 'SENSOR_DEACTIVATED',
                        'SCHEDULE_CHANGED', 'ZONE_STATUS_CHANGED', 'SYSTEM_STATUS_CHANGED'
                    )),
                    zone_id INTEGER,
                    zone_name TEXT,
                    
                    previous_value TEXT,
                    new_value TEXT,
                    change_description TEXT NOT NULL,
                    
                    sensor_status TEXT,
                    weather_conditions TEXT,
                    system_context TEXT,
                    
                    notification_sent BOOLEAN DEFAULT FALSE,
                    notification_method TEXT,
                    notification_recipients TEXT,
                    notification_sent_at TIMESTAMP,
                    
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
                );
                CREATE INDEX idx_status_changes_date_type ON status_changes(change_date, change_type);
                CREATE INDEX idx_status_changes_zone ON status_changes(zone_id, change_date);
                """
            
            self.adapter.execute_script(sql)
    
    def _initialize_zones(self):
        """Initialize zones table with basic zone data"""
        try:
            # Check if zones already exist
            existing_zones = self.adapter.execute_query("SELECT COUNT(*) as count FROM zones")
            if existing_zones[0]['count'] > 0:
                logger.info("Zones already initialized")
                return
            
            # Get zones from configuration  
            zones_data = self.zone_config.get_zones_data()
            
            for zone_id, name, flow_rate_gpm, priority, plant_type in zones_data:
                # Insert zone with default values
                if is_postgresql():
                    query = """
                        INSERT INTO zones (zone_id, zone_name, zone_display_name, priority_level, 
                                         flow_rate_gpm, average_flow_rate, typical_duration_minutes, 
                                         plant_type, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (zone_id) DO NOTHING
                    """
                else:
                    query = """
                        INSERT OR IGNORE INTO zones (zone_id, zone_name, zone_display_name, priority_level, 
                                                   flow_rate_gpm, average_flow_rate, typical_duration_minutes, 
                                                   plant_type, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                
                # Get average flow rate from configuration
                average_flow_rate = self.zone_config.get_zone_flow_rate(zone_id)
                
                params = (
                    zone_id,
                    name,
                    name,  # Use name as display_name
                    priority,
                    flow_rate_gpm,
                    average_flow_rate,
                    3,  # typical_duration_minutes
                    plant_type,
                    f'Auto-initialized zone: {plant_type}'  # notes
                )
                
                self.adapter.execute_insert(query, params)
            
            logger.info(f"Initialized {len(zones_data)} zones in database")
            
        except Exception as e:
            logger.error(f"Failed to initialize zones: {e}")
            raise
    
    def insert_scheduled_runs(self, scheduled_runs: List[ScheduledRun], target_date: date = None) -> int:
        """
        Insert scheduled runs into database
        
        Args:
            scheduled_runs: List of ScheduledRun objects
            target_date: Date these runs are scheduled for
            
        Returns:
            Number of runs inserted
        """
        if not scheduled_runs:
            return 0
        
        inserted_count = 0
        
        try:
            for run in scheduled_runs:
                # Prepare data for insertion
                if is_postgresql():
                    query = """
                        INSERT INTO scheduled_runs (
                            zone_id, zone_name, schedule_date, scheduled_start_time,
                            scheduled_duration_minutes, expected_gallons, program_name,
                            source, raw_popup_text, popup_lines_json, parsed_summary,
                            is_rain_cancelled, rain_sensor_status, popup_status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (zone_id, scheduled_start_time) DO UPDATE SET
                            scheduled_duration_minutes = EXCLUDED.scheduled_duration_minutes,
                            expected_gallons = EXCLUDED.expected_gallons,
                            raw_popup_text = EXCLUDED.raw_popup_text,
                            popup_lines_json = EXCLUDED.popup_lines_json,
                            parsed_summary = EXCLUDED.parsed_summary,
                            is_rain_cancelled = EXCLUDED.is_rain_cancelled,
                            rain_sensor_status = EXCLUDED.rain_sensor_status,
                            popup_status = EXCLUDED.popup_status
                    """
                else:
                    query = """
                        INSERT OR REPLACE INTO scheduled_runs (
                            zone_id, zone_name, schedule_date, scheduled_start_time,
                            scheduled_duration_minutes, expected_gallons, program_name,
                            source, raw_popup_text, popup_lines_json, parsed_summary,
                            is_rain_cancelled, rain_sensor_status, popup_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                
                params = (
                    run.zone_id,
                    run.zone_name,
                    target_date or run.start_time.date(),
                    run.start_time,
                    run.duration_minutes,
                    run.expected_gallons,
                    getattr(run, 'program_name', None),
                    'web_scraper',
                    getattr(run, 'raw_popup_text', None),
                    getattr(run, 'popup_lines_json', None),
                    getattr(run, 'parsed_summary', None),
                    getattr(run, 'is_rain_cancelled', False),
                    getattr(run, 'rain_sensor_status', None),
                    getattr(run, 'popup_status', None)
                )
                
                self.adapter.execute_insert(query, params)
                inserted_count += 1
            
            logger.info(f"Inserted {inserted_count} scheduled runs for {target_date}")
            return inserted_count
            
        except Exception as e:
            logger.error(f"Failed to insert scheduled runs: {e}")
            raise
    
    def insert_actual_runs(self, actual_runs: List[ActualRun], target_date: date = None) -> int:
        """
        Insert actual runs into database
        
        Args:
            actual_runs: List of ActualRun objects
            target_date: Date these runs occurred
            
        Returns:
            Number of runs inserted
        """
        if not actual_runs:
            return 0
        
        inserted_count = 0
        
        try:
            for run in actual_runs:
                # Calculate end time
                end_time = run.start_time + timedelta(minutes=run.duration_minutes)
                
                if is_postgresql():
                    query = """
                        INSERT INTO actual_runs (
                            zone_id, zone_name, run_date, actual_start_time,
                            actual_duration_minutes, actual_gallons, status, failure_reason,
                            current_ma, end_time, source, raw_popup_text, popup_lines_json,
                            parsed_summary, abort_reason, usage_type, usage, usage_flag
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (zone_id, actual_start_time) DO UPDATE SET
                            actual_duration_minutes = EXCLUDED.actual_duration_minutes,
                            actual_gallons = EXCLUDED.actual_gallons,
                            status = EXCLUDED.status,
                            failure_reason = EXCLUDED.failure_reason,
                            current_ma = EXCLUDED.current_ma,
                            end_time = EXCLUDED.end_time,
                            raw_popup_text = EXCLUDED.raw_popup_text,
                            popup_lines_json = EXCLUDED.popup_lines_json,
                            parsed_summary = EXCLUDED.parsed_summary,
                            abort_reason = EXCLUDED.abort_reason,
                            usage_type = EXCLUDED.usage_type,
                            usage = EXCLUDED.usage,
                            usage_flag = EXCLUDED.usage_flag
                    """
                else:
                    query = """
                        INSERT OR REPLACE INTO actual_runs (
                            zone_id, zone_name, run_date, actual_start_time,
                            actual_duration_minutes, actual_gallons, status, failure_reason,
                            current_ma, end_time, source, raw_popup_text, popup_lines_json,
                            parsed_summary, abort_reason, usage_type, usage, usage_flag
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                
                params = (
                    run.zone_id,
                    run.zone_name,
                    target_date or run.start_time.date(),
                    run.start_time,
                    run.duration_minutes,
                    run.gallons_used,
                    run.status,
                    getattr(run, 'failure_reason', None),
                    getattr(run, 'current_ma', None),
                    end_time,
                    'web_scraper',
                    getattr(run, 'raw_popup_text', None),
                    getattr(run, 'popup_lines_json', None),
                    getattr(run, 'parsed_summary', None),
                    getattr(run, 'abort_reason', None),
                    getattr(run, 'usage_type', 'actual'),
                    run.gallons_used,  # usage field
                    getattr(run, 'usage_flag', 'normal')
                )
                
                self.adapter.execute_insert(query, params)
                inserted_count += 1
            
            logger.info(f"Inserted {inserted_count} actual runs for {target_date}")
            return inserted_count
            
        except Exception as e:
            logger.error(f"Failed to insert actual runs: {e}")
            raise
    
    def get_scheduled_runs(self, target_date: date, zone_id: int = None) -> List[Dict[str, Any]]:
        """Get scheduled runs for a specific date"""
        if is_postgresql():
            base_query = "SELECT * FROM scheduled_runs WHERE schedule_date = %s"
            params = [target_date]
            if zone_id:
                base_query += " AND zone_id = %s"
                params.append(zone_id)
        else:
            base_query = "SELECT * FROM scheduled_runs WHERE schedule_date = ?"
            params = [target_date]
            if zone_id:
                base_query += " AND zone_id = ?"
                params.append(zone_id)
        
        base_query += " ORDER BY scheduled_start_time"
        return self.adapter.execute_query(base_query, params)
    
    def get_actual_runs(self, target_date: date, zone_id: int = None) -> List[Dict[str, Any]]:
        """Get actual runs for a specific date"""
        if is_postgresql():
            base_query = "SELECT * FROM actual_runs WHERE run_date = %s"
            params = [target_date]
            if zone_id:
                base_query += " AND zone_id = %s"
                params.append(zone_id)
        else:
            base_query = "SELECT * FROM actual_runs WHERE run_date = ?"
            params = [target_date]
            if zone_id:
                base_query += " AND zone_id = ?"
                params.append(zone_id)
        
        base_query += " ORDER BY actual_start_time"
        return self.adapter.execute_query(base_query, params)
    
    def get_zones(self) -> List[Dict[str, Any]]:
        """Get all zones from database"""
        return self.adapter.execute_query("SELECT * FROM zones ORDER BY zone_id")
    
    def close(self):
        """Close database connection"""
        if self.adapter:
            self.adapter.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

# Convenience function to get a universal database manager
def get_universal_database_manager() -> UniversalDatabaseManager:
    """Get a configured universal database manager"""
    return UniversalDatabaseManager()

if __name__ == "__main__":
    # Test the universal database manager
    print("Testing Universal Database Manager...")
    
    try:
        with get_universal_database_manager() as db:
            print(f"Connected to {db.config.db_type} database")
            
            # Test basic operations
            zones = db.get_zones()
            print(f"Found {len(zones)} zones in database")
            
            if zones:
                print("Sample zone:", zones[0])
            
    except Exception as e:
        print(f"Error testing database manager: {e}")
