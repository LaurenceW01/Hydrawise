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
from config.water_usage_config import get_water_usage_thresholds
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
            # Fix rain sensor status history table schema if needed
            self._fix_rain_sensor_table_schema()
            # Check for missing columns and add them
            self._add_missing_columns()
            # Migrate failure_events table to events if needed
            self._migrate_failure_events_to_events()
            # Add enhancements to events table for improved event detection
            self._add_events_table_enhancements()
            logger.info("Schema migration completed")
        except Exception as e:
            logger.warning(f"Schema migration failed: {e}")
    
    def _fix_rain_sensor_table_schema(self):
        """Fix rain_sensor_status_history table schema if it has the wrong structure"""
        if self.adapter.table_exists('rain_sensor_status_history'):
            try:
                # Check if the table has the required columns by trying to query them
                test_query = "SELECT status_time, sensor_status, sensor_text_raw FROM rain_sensor_status_history LIMIT 1"
                self.adapter.execute_query(test_query)
                logger.debug("rain_sensor_status_history table schema is correct")
            except Exception as e:
                if "does not exist" in str(e) or "no such column" in str(e):
                    logger.info("Fixing rain_sensor_status_history table schema - missing required columns")
                    # Drop and recreate the table with correct schema
                    try:
                        self.adapter.execute_query("DROP TABLE rain_sensor_status_history")
                        logger.info("Dropped old rain_sensor_status_history table")
                        
                        # Create with correct schema
                        if is_postgresql():
                            sql = """
                            CREATE TABLE rain_sensor_status_history (
                                id SERIAL PRIMARY KEY,
                                status_date DATE NOT NULL,
                                status_time TIMESTAMP NOT NULL,
                                sensor_status TEXT NOT NULL,
                                is_stopping_irrigation BOOLEAN NOT NULL,
                                irrigation_suspended BOOLEAN NOT NULL,
                                sensor_text_raw TEXT,
                                collection_run_id TEXT,
                                sensor_enabled BOOLEAN NOT NULL,
                                sensor_active BOOLEAN NOT NULL,
                                raw_status_data TEXT,
                                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                
                                UNIQUE(status_date, status_time)
                            );
                            CREATE INDEX idx_rain_sensor_status_date ON rain_sensor_status_history(status_date);
                            """
                        else:
                            sql = """
                            CREATE TABLE rain_sensor_status_history (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                status_date DATE NOT NULL,
                                status_time TIMESTAMP NOT NULL,
                                sensor_status TEXT NOT NULL,
                                is_stopping_irrigation BOOLEAN NOT NULL,
                                irrigation_suspended BOOLEAN NOT NULL,
                                sensor_text_raw TEXT,
                                collection_run_id TEXT,
                                sensor_enabled BOOLEAN NOT NULL,
                                sensor_active BOOLEAN NOT NULL,
                                raw_status_data TEXT,
                                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                
                                UNIQUE(status_date, status_time)
                            );
                            CREATE INDEX idx_rain_sensor_status_date ON rain_sensor_status_history(status_date);
                            """
                        
                        self.adapter.execute_script(sql)
                        logger.info("Recreated rain_sensor_status_history table with correct schema")
                    except Exception as create_error:
                        logger.error(f"Failed to recreate rain_sensor_status_history table: {create_error}")
                else:
                    logger.debug(f"rain_sensor_status_history schema check failed for other reason: {e}")
    
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
                    status_time TIMESTAMP NOT NULL,
                    sensor_status TEXT NOT NULL,
                    is_stopping_irrigation BOOLEAN NOT NULL,
                    irrigation_suspended BOOLEAN NOT NULL,
                    sensor_text_raw TEXT,
                    collection_run_id TEXT,
                    sensor_enabled BOOLEAN NOT NULL,
                    sensor_active BOOLEAN NOT NULL,
                    raw_status_data TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(status_date, status_time)
                );
                CREATE INDEX idx_rain_sensor_status_date ON rain_sensor_status_history(status_date);
                """
            else:
                sql = """
                CREATE TABLE rain_sensor_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status_date DATE NOT NULL,
                    status_time TIMESTAMP NOT NULL,
                    sensor_status TEXT NOT NULL,
                    is_stopping_irrigation BOOLEAN NOT NULL,
                    irrigation_suspended BOOLEAN NOT NULL,
                    sensor_text_raw TEXT,
                    collection_run_id TEXT,
                    sensor_enabled BOOLEAN NOT NULL,
                    sensor_active BOOLEAN NOT NULL,
                    raw_status_data TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(status_date, status_time)
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
    
    def _add_events_table_enhancements(self):
        """Add new columns to events table for enhanced event detection"""
        try:
            # Check if events table exists
            if not self.adapter.table_exists('events'):
                logger.debug("Events table doesn't exist yet, skipping column additions")
                return
            
            # List of new columns to add
            new_columns = [
                ('event_time', 'TIMESTAMP', 'actual_start_time of the irrigation run that triggered this event'),
                ('estimated_gallons', 'REAL', 'Expected gallons for comparison (may differ from scheduled)'),
                ('actual_flow_rate', 'REAL', 'Calculated: actual_gallons / actual_duration_minutes'),
                ('expected_flow_rate', 'REAL', 'Zone average flow rate for comparison'),
                ('last_updated', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'When event was last modified')
            ]
            
            for column_name, column_type, comment in new_columns:
                try:
                    # Check if column already exists
                    if is_postgresql():
                        check_sql = """
                            SELECT column_name FROM information_schema.columns 
                            WHERE table_name = 'events' AND column_name = %s
                        """
                        result = self.adapter.execute_query(check_sql, (column_name,))
                    else:
                        # SQLite: Use PRAGMA table_info
                        check_sql = "PRAGMA table_info(events)"
                        result = self.adapter.execute_query(check_sql)
                        result = [row for row in result if row['name'] == column_name]
                    
                    if not result:
                        # Column doesn't exist, add it
                        add_sql = f"ALTER TABLE events ADD COLUMN {column_name} {column_type}"
                        self.adapter.execute_update(add_sql)
                        logger.info(f"Added column '{column_name}' to events table: {comment}")
                    else:
                        logger.debug(f"Column '{column_name}' already exists in events table")
                        
                except Exception as e:
                    logger.warning(f"Failed to add column '{column_name}' to events table: {e}")
                    # Don't fail the entire migration for individual column issues
            
            logger.info("Events table enhancement migration completed")
            
        except Exception as e:
            logger.error(f"Failed to enhance events table: {e}")
            # Don't raise the exception - this is not critical for system operation
    
    def _migrate_failure_events_to_events(self):
        """Migrate failure_events table to events table if needed"""
        try:
            # Use direct SQL queries to avoid potential recursion issues
            # Check if old failure_events table exists
            if is_postgresql():
                check_failure_events = """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'failure_events'
                    )
                """
                check_events = """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'events'
                    )
                """
            else:
                check_failure_events = """
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='failure_events'
                """
                check_events = """
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='events'
                """
            
            # Check table existence
            failure_events_result = self.adapter.execute_query(check_failure_events)
            events_result = self.adapter.execute_query(check_events)
            
            failure_events_exists = bool(failure_events_result and (
                failure_events_result[0].get('exists', False) if is_postgresql() 
                else len(failure_events_result) > 0
            ))
            
            events_exists = bool(events_result and (
                events_result[0].get('exists', False) if is_postgresql()
                else len(events_result) > 0
            ))
            
            if failure_events_exists and not events_exists:
                logger.info("Migrating failure_events table to events table")
                
                # Rename the table
                if is_postgresql():
                    # PostgreSQL supports ALTER TABLE RENAME - use execute_update for DDL
                    self.adapter.execute_update("ALTER TABLE failure_events RENAME TO events")
                    logger.info("Successfully renamed failure_events to events (PostgreSQL)")
                    
                    # Rename constraints and indexes
                    try:
                        # Rename constraints (PostgreSQL automatically renames some, but we need to handle others)
                        constraint_renames = [
                            "ALTER INDEX failure_events_pkey RENAME TO events_pkey",
                            "ALTER INDEX failure_events_failure_id_key RENAME TO events_failure_id_key", 
                            "ALTER INDEX failure_events_zone_id_fkey RENAME TO events_zone_id_fkey",
                            "ALTER INDEX failure_events_scheduled_run_id_fkey RENAME TO events_scheduled_run_id_fkey",
                            "ALTER INDEX failure_events_actual_run_id_fkey RENAME TO events_actual_run_id_fkey",
                            "ALTER INDEX idx_failure_events_date_severity RENAME TO idx_events_date_severity",
                            "ALTER INDEX idx_failure_events_detected_at RENAME TO idx_events_detected_at"
                        ]
                        
                        for rename_sql in constraint_renames:
                            try:
                                self.adapter.execute_update(rename_sql)
                                logger.debug(f"Renamed constraint/index: {rename_sql}")
                            except Exception as e:
                                # Some constraints might not exist or might have been auto-renamed
                                logger.debug(f"Could not rename constraint/index (may not exist): {rename_sql} - {e}")
                        
                        # Rename check constraints (these need special handling)
                        check_constraint_renames = [
                            "ALTER TABLE events RENAME CONSTRAINT failure_events_failure_type_check TO events_failure_type_check",
                            "ALTER TABLE events RENAME CONSTRAINT failure_events_severity_check TO events_severity_check", 
                            "ALTER TABLE events RENAME CONSTRAINT failure_events_plant_risk_check TO events_plant_risk_check"
                        ]
                        
                        for rename_sql in check_constraint_renames:
                            try:
                                self.adapter.execute_update(rename_sql)
                                logger.debug(f"Renamed check constraint: {rename_sql}")
                            except Exception as e:
                                # Some constraints might not exist or have different names
                                logger.debug(f"Could not rename check constraint (may not exist): {rename_sql} - {e}")
                                
                        logger.info("Successfully renamed constraints and indexes")
                        
                    except Exception as e:
                        logger.warning(f"Some constraints/indexes could not be renamed: {e}")
                        # Don't fail the migration for this
                else:
                    # SQLite requires more complex migration
                    # First, create the new events table with the correct schema
                    schema_sql = """
                    CREATE TABLE events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        failure_id TEXT UNIQUE NOT NULL,
                        zone_id INTEGER NOT NULL,
                        zone_name TEXT NOT NULL,
                        failure_date DATE NOT NULL,
                        failure_type TEXT NOT NULL CHECK (failure_type IN (
                            'MISSING_RUN', 'UNEXPECTED_RUN', 'FAILED_RUN', 
                            'WATER_VARIANCE', 'DURATION_VARIANCE', 'SENSOR_ABORT'
                        )),
                        severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'WARNING', 'INFO')),
                        description TEXT NOT NULL,
                        recommended_action TEXT,
                        plant_risk TEXT CHECK (plant_risk IN ('HIGH', 'MEDIUM', 'LOW')),
                        max_hours_without_water INTEGER,
                        scheduled_run_id INTEGER,
                        actual_run_id INTEGER,
                        scheduled_gallons REAL,
                        actual_gallons REAL,
                        water_deficit REAL,
                        hours_since_last_water REAL,
                        resolved BOOLEAN DEFAULT FALSE,
                        resolved_at TIMESTAMP,
                        resolution_method TEXT,
                        resolution_notes TEXT,
                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (zone_id) REFERENCES zones(zone_id),
                        FOREIGN KEY (scheduled_run_id) REFERENCES scheduled_runs(id),
                        FOREIGN KEY (actual_run_id) REFERENCES actual_runs(id)
                    )
                    """
                    
                    self.adapter.execute_update(schema_sql)
                    
                    # Copy data from old table to new table
                    copy_sql = """
                    INSERT INTO events (
                        failure_id, zone_id, zone_name, failure_date, failure_type,
                        severity, description, recommended_action, plant_risk,
                        max_hours_without_water, scheduled_run_id, actual_run_id,
                        scheduled_gallons, actual_gallons, water_deficit,
                        hours_since_last_water, resolved, resolved_at,
                        resolution_method, resolution_notes, detected_at
                    )
                    SELECT 
                        failure_id, zone_id, zone_name, failure_date, failure_type,
                        severity, description, recommended_action, plant_risk,
                        max_hours_without_water, scheduled_run_id, actual_run_id,
                        scheduled_gallons, actual_gallons, water_deficit,
                        hours_since_last_water, resolved, resolved_at,
                        resolution_method, resolution_notes, detected_at
                    FROM failure_events
                    """
                    
                    self.adapter.execute_update(copy_sql)
                    
                    # Drop the old table
                    self.adapter.execute_update("DROP TABLE failure_events")
                
                logger.info("Successfully migrated failure_events table to events table")
                
            elif events_exists and not failure_events_exists:
                logger.debug("Events table already exists, migration not needed")
            elif events_exists and failure_events_exists:
                logger.warning("Both failure_events and events tables exist, manual intervention may be needed")
            else:
                logger.debug("Neither failure_events nor events table exists, will be created from schema")
                
        except Exception as e:
            logger.error(f"Failed to migrate failure_events to events: {e}")
            import traceback
            logger.error(f"Migration error details: {traceback.format_exc()}")
            # Don't raise the exception - this is not critical for system operation
    
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
                            source, notes, raw_popup_text, popup_lines_json, parsed_summary,
                            is_rain_cancelled, rain_sensor_status, popup_status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (zone_id, scheduled_start_time) DO UPDATE SET
                            scheduled_duration_minutes = EXCLUDED.scheduled_duration_minutes,
                            expected_gallons = EXCLUDED.expected_gallons,
                            program_name = EXCLUDED.program_name,
                            notes = EXCLUDED.notes,
                            raw_popup_text = EXCLUDED.raw_popup_text,
                            popup_lines_json = EXCLUDED.popup_lines_json,
                            parsed_summary = EXCLUDED.parsed_summary,
                            is_rain_cancelled = EXCLUDED.is_rain_cancelled,
                            rain_sensor_status = EXCLUDED.rain_sensor_status,
                            popup_status = EXCLUDED.popup_status,
                            scraped_at = CURRENT_TIMESTAMP
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
                
                # Convert zone_id to integer if it's a string like "zone_1"
                zone_id = run.zone_id
                if isinstance(zone_id, str) and zone_id.startswith('zone_'):
                    zone_id = int(zone_id.replace('zone_', ''))
                elif isinstance(zone_id, str) and zone_id.isdigit():
                    zone_id = int(zone_id)
                
                # Process popup data - convert popup_lines to JSON if present
                raw_popup_text = getattr(run, 'raw_popup_text', None)
                popup_lines_json = None
                parsed_summary = getattr(run, 'parsed_summary', None)
                
                # Handle popup_lines conversion to JSON
                if hasattr(run, 'popup_lines') and run.popup_lines:
                    import json
                    popup_lines_json = json.dumps(run.popup_lines)
                elif hasattr(run, 'popup_lines_json'):
                    # If already converted to JSON, use as-is
                    popup_lines_json = getattr(run, 'popup_lines_json', None)
                
                params = (
                    zone_id,
                    run.zone_name,
                    target_date or run.start_time.date(),
                    run.start_time,
                    run.duration_minutes,
                    run.expected_gallons,
                    getattr(run, 'program_name', None),
                    'web_scraper',
                    getattr(run, 'notes', None),
                    raw_popup_text,
                    popup_lines_json,
                    parsed_summary,
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
    
    def get_zone_average_flow_rate(self, zone_id: int) -> Optional[float]:
        """Get the average flow rate for a specific zone from database
        
        Args:
            zone_id: The zone ID to look up
            
        Returns:
            Average flow rate in GPM, or None if not found
        """
        try:
            if is_postgresql():
                query = "SELECT average_flow_rate FROM zones WHERE zone_id = %s"
            else:
                query = "SELECT average_flow_rate FROM zones WHERE zone_id = ?"
            
            result = self.adapter.execute_query(query, (zone_id,))
            
            if result and result[0]['average_flow_rate'] is not None:
                flow_rate = float(result[0]['average_flow_rate'])
                logger.debug(f"Found average flow rate for zone {zone_id}: {flow_rate} GPM")
                return flow_rate
                    
        except Exception as e:
            logger.debug(f"Could not get average flow rate for zone {zone_id}: {e}")
            
        return None

    def insert_actual_runs(self, actual_runs: List[ActualRun], target_date: date = None) -> int:
        """
        Insert actual runs into database with usage calculation when actual_gallons is 0
        
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
                            current_ma, end_time, source, notes, raw_popup_text, popup_lines_json,
                            parsed_summary, water_efficiency, abort_reason, usage_type, usage, usage_flag
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (zone_id, actual_start_time) DO UPDATE SET
                            actual_duration_minutes = EXCLUDED.actual_duration_minutes,
                            actual_gallons = EXCLUDED.actual_gallons,
                            status = EXCLUDED.status,
                            failure_reason = EXCLUDED.failure_reason,
                            current_ma = EXCLUDED.current_ma,
                            end_time = EXCLUDED.end_time,
                            notes = EXCLUDED.notes,
                            raw_popup_text = EXCLUDED.raw_popup_text,
                            popup_lines_json = EXCLUDED.popup_lines_json,
                            parsed_summary = EXCLUDED.parsed_summary,
                            water_efficiency = EXCLUDED.water_efficiency,
                            abort_reason = EXCLUDED.abort_reason,
                            usage_type = EXCLUDED.usage_type,
                            usage = EXCLUDED.usage,
                            usage_flag = EXCLUDED.usage_flag,
                            scraped_at = CURRENT_TIMESTAMP
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
                
                # Convert zone_id to integer if it's a string like "zone_1"
                zone_id = run.zone_id
                if isinstance(zone_id, str) and zone_id.startswith('zone_'):
                    zone_id = int(zone_id.replace('zone_', ''))
                elif isinstance(zone_id, str) and zone_id.isdigit():
                    zone_id = int(zone_id)
                
                # Process popup data - convert popup_lines to JSON if present
                raw_popup_text = getattr(run, 'raw_popup_text', None)
                popup_lines_json = None
                parsed_summary = getattr(run, 'parsed_summary', None)
                
                # Handle popup_lines conversion to JSON
                if hasattr(run, 'popup_lines') and run.popup_lines:
                    import json
                    popup_lines_json = json.dumps(run.popup_lines)
                elif hasattr(run, 'popup_lines_json'):
                    # If already converted to JSON, use as-is
                    popup_lines_json = getattr(run, 'popup_lines_json', None)
                
                # Calculate usage value and determine usage flags based on actual_gallons
                # When actual_gallons is 0 or None, estimate from zone average flow rate * duration
                # When actual_gallons has value, check if it's too_high or too_low compared to expected
                actual_gallons = run.actual_gallons
                usage_value = actual_gallons
                usage_type = getattr(run, 'usage_type', 'actual')
                usage_flag = getattr(run, 'usage_flag', 'normal')
                
                # Get zone flow rate for calculations
                flow_rate = self.get_zone_average_flow_rate(zone_id)
                expected_gallons = None
                
                # Calculate expected gallons if we have flow rate data
                if flow_rate is not None and run.duration_minutes > 0:
                    expected_gallons = flow_rate * run.duration_minutes
                
                # Usage flag determination logic (matching SQLite WaterUsageEstimator logic)
                if actual_gallons is None or actual_gallons == 0:
                    # Zero or missing actual usage - estimate instead
                    if expected_gallons is not None:
                        usage_value = expected_gallons
                        usage_type = 'estimated'
                        usage_flag = 'zero_reported'
                        logger.debug(f"Zone {zone_id} ({run.zone_name}): Estimated usage {expected_gallons:.2f}g from {flow_rate} GPM * {run.duration_minutes} min (zero reported)")
                    else:
                        # No flow rate available for estimation
                        logger.warning(f"Zone {zone_id} ({run.zone_name}): No flow rate available for usage estimation")
                        usage_value = actual_gallons  # Will be 0 or None
                        usage_type = 'actual'
                        usage_flag = 'zero_reported'
                else:
                    # Actual gallons reported - check if within expected range
                    usage_value = actual_gallons
                    usage_type = 'actual'
                    
                    if expected_gallons is not None and expected_gallons > 0:
                        # Calculate usage ratio for comparison
                        usage_ratio = actual_gallons / expected_gallons
                        
                        # Get configurable thresholds from environment variables or defaults
                        HIGH_USAGE_MULTIPLIER, LOW_USAGE_MULTIPLIER = get_water_usage_thresholds()
                        
                        # Check if usage is too high (> configured threshold)
                        if usage_ratio > HIGH_USAGE_MULTIPLIER:
                            usage_flag = 'too_high'
                            logger.debug(f"Zone {zone_id} ({run.zone_name}): Usage {usage_ratio:.1f}x expected (too high: {actual_gallons:.1f}g vs {expected_gallons:.1f}g expected, threshold: {HIGH_USAGE_MULTIPLIER}x)")
                        # Check if usage is too low (< configured threshold)  
                        elif usage_ratio < LOW_USAGE_MULTIPLIER:
                            usage_flag = 'too_low'
                            logger.debug(f"Zone {zone_id} ({run.zone_name}): Usage {usage_ratio:.1f}x expected (too low: {actual_gallons:.1f}g vs {expected_gallons:.1f}g expected, threshold: {LOW_USAGE_MULTIPLIER}x)")
                        else:
                            # Usage is within normal range
                            usage_flag = 'normal'
                            logger.debug(f"Zone {zone_id} ({run.zone_name}): Usage {usage_ratio:.1f}x expected (normal: {actual_gallons:.1f}g vs {expected_gallons:.1f}g expected, thresholds: {LOW_USAGE_MULTIPLIER}x-{HIGH_USAGE_MULTIPLIER}x)")
                    else:
                        # No expected usage for comparison, use actual value as normal
                        usage_flag = 'normal'
                        logger.debug(f"Zone {zone_id} ({run.zone_name}): Using actual value {actual_gallons:.1f}g (no flow rate reference)")
                
                params = (
                    zone_id,
                    run.zone_name,
                    target_date or run.start_time.date(),
                    run.start_time,
                    run.duration_minutes,
                    actual_gallons,  # Keep original actual_gallons value
                    run.status,
                    getattr(run, 'failure_reason', None),
                    getattr(run, 'current_ma', None),
                    end_time,
                    'web_scraper',
                    getattr(run, 'notes', None),
                    raw_popup_text,
                    popup_lines_json,
                    parsed_summary,
                    getattr(run, 'water_efficiency', None),
                    getattr(run, 'abort_reason', None),
                    usage_type,  # Use calculated usage_type
                    usage_value,  # Use calculated usage_value (estimated when actual_gallons is 0)
                    usage_flag   # Use calculated usage_flag
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
    
    def delete_actual_runs_for_date(self, target_date: date) -> int:
        """Delete all actual runs for a specific date
        
        Args:
            target_date: Date to delete runs for
            
        Returns:
            Number of runs deleted
        """
        try:
            if is_postgresql():
                query = "DELETE FROM actual_runs WHERE run_date = %s"
            else:
                query = "DELETE FROM actual_runs WHERE run_date = ?"
            
            rows_affected = self.adapter.execute_delete(query, (target_date,))
            logger.info(f"Deleted {rows_affected} actual runs for {target_date}")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to delete actual runs for {target_date}: {e}")
            raise
    
    def delete_scheduled_runs_for_date(self, target_date: date) -> int:
        """Delete all scheduled runs for a specific date
        
        Args:
            target_date: Date to delete runs for
            
        Returns:
            Number of runs deleted
        """
        try:
            if is_postgresql():
                query = "DELETE FROM scheduled_runs WHERE schedule_date = %s"
            else:
                query = "DELETE FROM scheduled_runs WHERE schedule_date = ?"
            
            rows_affected = self.adapter.execute_delete(query, (target_date,))
            logger.info(f"Deleted {rows_affected} scheduled runs for {target_date}")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to delete scheduled runs for {target_date}: {e}")
            raise
    
    def log_collection_start(self, collection_date: date, collection_type: str, start_time: datetime) -> int:
        """
        Log the start of a collection operation and return the collection ID
        
        Args:
            collection_date: Date being collected
            collection_type: Type of collection (schedule_admin, actual_admin, etc.)
            start_time: When collection started
            
        Returns:
            int: Collection log ID for updating later
        """
        try:
            if is_postgresql():
                query = """
                    INSERT INTO collection_log 
                    (collection_date, collection_type, status, start_time, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """
            else:
                query = """
                    INSERT INTO collection_log 
                    (collection_date, collection_type, status, start_time, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """
            
            params = (collection_date, collection_type, 'IN_PROGRESS', start_time, datetime.now())
            
            if is_postgresql():
                result = self.adapter.execute_query(query, params)
                collection_id = result[0]['id'] if result else None
            else:
                collection_id = self.adapter.execute_insert(query, params)
            
            logger.info(f"Started collection log {collection_id} for {collection_type} on {collection_date}")
            return collection_id
            
        except Exception as e:
            logger.error(f"Failed to log collection start: {e}")
            return None
    
    def log_collection_end(self, collection_id: int, status: str, scheduled_count: int = 0, 
                          actual_count: int = 0, zones_processed: int = 0, 
                          errors: int = 0, error_details: str = None, warnings: str = None) -> None:
        """
        Update collection log with final results
        
        Args:
            collection_id: ID from log_collection_start
            status: SUCCESS, PARTIAL, or FAILED
            scheduled_count: Number of scheduled runs collected
            actual_count: Number of actual runs collected
            zones_processed: Number of zones processed
            errors: Number of errors encountered
            error_details: Details about errors
            warnings: Warning messages
        """
        try:
            if not collection_id:
                logger.warning("No collection_id provided, skipping collection end log")
                return
                
            end_time = datetime.now()
            
            if is_postgresql():
                query = """
                    UPDATE collection_log SET
                        status = %s,
                        scheduled_runs_collected = %s,
                        actual_runs_collected = %s,
                        zones_processed = %s,
                        end_time = %s,
                        processing_duration_seconds = EXTRACT(EPOCH FROM (%s - start_time)),
                        errors_encountered = %s,
                        error_details = %s,
                        warnings = %s
                    WHERE id = %s
                """
            else:
                query = """
                    UPDATE collection_log SET
                        status = ?,
                        scheduled_runs_collected = ?,
                        actual_runs_collected = ?,
                        zones_processed = ?,
                        end_time = ?,
                        processing_duration_seconds = (julianday(?) - julianday(start_time)) * 86400,
                        errors_encountered = ?,
                        error_details = ?,
                        warnings = ?
                    WHERE id = ?
                """
            
            params = (status, scheduled_count, actual_count, zones_processed, end_time, 
                     end_time, errors, error_details, warnings, collection_id)
            
            self.adapter.execute_update(query, params)
            
            logger.info(f"Updated collection log {collection_id}: {status} - {scheduled_count} scheduled, {actual_count} actual, {zones_processed} zones, {errors} errors")
            
        except Exception as e:
            logger.error(f"Failed to log collection end: {e}")
    
    def get_recent_collection_logs(self, days: int = 7) -> List[Dict]:
        """Get recent collection logs"""
        try:
            if is_postgresql():
                query = """
                    SELECT * FROM collection_log 
                    WHERE collection_date >= %s
                    ORDER BY start_time DESC
                """
            else:
                query = """
                    SELECT * FROM collection_log 
                    WHERE collection_date >= date('now', '-{} days')
                    ORDER BY start_time DESC
                """.format(days)
            
            if is_postgresql():
                cutoff_date = date.today() - timedelta(days=days)
                result = self.adapter.execute_query(query, (cutoff_date,))
            else:
                result = self.adapter.execute_query(query)
            
            return result if result else []
            
        except Exception as e:
            logger.error(f"Failed to get recent collection logs: {e}")
            return []

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
