#!/usr/bin/env python3
"""
Hydrawise Database Manager

Handles all database operations for irrigation monitoring system including:
- Database initialization and schema management
- Data insertion for scheduled and actual runs
- Variance analysis and failure detection
- Query utilities for analysis and reporting

Author: AI Assistant
Date: 2025-08-21
"""

import sqlite3
import logging
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import sys

# Add project root to path for config imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.zone_configuration import ZoneConfiguration
import hashlib
import json

# Import our data models
from hydrawise_web_scraper_refactored import ScheduledRun, ActualRun

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages all database operations for irrigation monitoring"""
    
    def __init__(self, db_path: str = "database/irrigation_data.db"):
        """Initialize database manager with SQLite database"""
        self.db_path = db_path
        self.zone_config = ZoneConfiguration()
        self.ensure_directory()
        self.init_database()
        
    def ensure_directory(self):
        """Ensure database directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
    def init_database(self):
        """Initialize database with schema if it doesn't exist"""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        
        with sqlite3.connect(self.db_path) as conn:
            # Check if database is already initialized
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='zones'")
            existing_db = cursor.fetchone() is not None
            
            if existing_db:
                logger.info("Database already initialized - checking for schema updates")
                self._migrate_schema(conn)
                return
                
            # Read and execute schema
            try:
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()
                    
                # Execute schema (split by ';' and execute each statement)
                statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
                for statement in statements:
                    if statement:  # Skip empty statements
                        cursor.execute(statement)
                        
                conn.commit()
                logger.info(f"Database initialized successfully at {self.db_path}")
                
                # Initialize with basic zone data
                self._initialize_zones()
                
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise
                
    def _migrate_schema(self, conn):
        """Apply schema migrations for popup data fields, enhanced matching, and water usage estimation"""
        cursor = conn.cursor()
        
        # Check if popup data columns exist in scheduled_runs
        cursor.execute("PRAGMA table_info(scheduled_runs)")
        scheduled_columns = [row[1] for row in cursor.fetchall()]
        
        if 'raw_popup_text' not in scheduled_columns:
            logger.info("Adding popup data columns to scheduled_runs table")
            cursor.execute("ALTER TABLE scheduled_runs ADD COLUMN raw_popup_text TEXT")
            cursor.execute("ALTER TABLE scheduled_runs ADD COLUMN popup_lines_json TEXT") 
            cursor.execute("ALTER TABLE scheduled_runs ADD COLUMN parsed_summary TEXT")
            
        if 'is_rain_cancelled' not in scheduled_columns:
            logger.info("Adding rain cancellation tracking to scheduled_runs table")
            cursor.execute("ALTER TABLE scheduled_runs ADD COLUMN is_rain_cancelled BOOLEAN DEFAULT FALSE")
            cursor.execute("ALTER TABLE scheduled_runs ADD COLUMN rain_sensor_status TEXT")
            cursor.execute("ALTER TABLE scheduled_runs ADD COLUMN popup_status TEXT")
            
        # Check if popup data columns exist in actual_runs
        cursor.execute("PRAGMA table_info(actual_runs)")
        actual_columns = [row[1] for row in cursor.fetchall()]
        
        if 'raw_popup_text' not in actual_columns:
            logger.info("Adding popup data columns to actual_runs table")
            cursor.execute("ALTER TABLE actual_runs ADD COLUMN raw_popup_text TEXT")
            cursor.execute("ALTER TABLE actual_runs ADD COLUMN popup_lines_json TEXT")
            cursor.execute("ALTER TABLE actual_runs ADD COLUMN parsed_summary TEXT")
            
        if 'water_efficiency' not in actual_columns:
            logger.info("Adding enhanced analysis columns to actual_runs table")
            cursor.execute("ALTER TABLE actual_runs ADD COLUMN water_efficiency REAL")
            cursor.execute("ALTER TABLE actual_runs ADD COLUMN abort_reason TEXT")
            
        # Update current_ma to REAL if it's INTEGER
        cursor.execute("PRAGMA table_info(actual_runs)")
        current_ma_info = [row for row in cursor.fetchall() if row[1] == 'current_ma']
        if current_ma_info and 'INTEGER' in current_ma_info[0][2].upper():
            logger.info("Updating current_ma column type to REAL for decimal precision")
            # SQLite doesn't support ALTER COLUMN, so we'll handle this in the application
        
        # Add water usage estimation columns to zones table
        cursor.execute("PRAGMA table_info(zones)")
        zones_columns = [row[1] for row in cursor.fetchall()]
        
        if 'average_flow_rate' not in zones_columns:
            logger.info("Adding average_flow_rate column to zones table for water usage estimation")
            cursor.execute("ALTER TABLE zones ADD COLUMN average_flow_rate REAL")
        
        # Add water usage estimation columns to actual_runs table
        if 'usage_type' not in actual_columns:
            logger.info("Adding water usage estimation columns to actual_runs table")
            cursor.execute("ALTER TABLE actual_runs ADD COLUMN usage_type TEXT CHECK (usage_type IN ('actual', 'estimated')) DEFAULT 'actual'")
            cursor.execute("ALTER TABLE actual_runs ADD COLUMN usage REAL")  # Contains either actual_gallons or estimated value
            cursor.execute("ALTER TABLE actual_runs ADD COLUMN usage_flag TEXT CHECK (usage_flag IN ('normal', 'too_high', 'too_low', 'zero_reported')) DEFAULT 'normal'")
        
        # Add cost tracking tables for Houston water bill analysis
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='water_rate_configs'")
        if not cursor.fetchone():
            logger.info("Adding cost tracking tables for water bill analysis")
            
            # Create water rate configs table
            cursor.execute("""
                CREATE TABLE water_rate_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    effective_date DATE NOT NULL,
                    billing_period_start_day INTEGER DEFAULT 1,
                    manual_watering_gallons_per_day REAL DEFAULT 45.0,
                    basic_service_water REAL NOT NULL,
                    basic_service_wastewater REAL NOT NULL,
                    basic_service_total REAL NOT NULL,
                    config_json TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(effective_date)
                )
            """)
            
            # Create billing period costs table
            cursor.execute("""
                CREATE TABLE billing_period_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    billing_period_start DATE NOT NULL,
                    billing_period_end DATE NOT NULL,
                    calculation_date DATE NOT NULL,
                    irrigation_gallons REAL DEFAULT 0,
                    manual_watering_gallons REAL DEFAULT 0,
                    total_gallons REAL NOT NULL,
                    usage_tier INTEGER NOT NULL,
                    tier_range_min INTEGER NOT NULL,
                    tier_range_max INTEGER NOT NULL,
                    water_rate_per_gallon REAL NOT NULL,
                    wastewater_rate_per_gallon REAL NOT NULL,
                    basic_service_charge REAL NOT NULL,
                    water_usage_cost REAL NOT NULL,
                    wastewater_usage_cost REAL NOT NULL,
                    total_usage_cost REAL NOT NULL,
                    estimated_total_cost REAL NOT NULL,
                    days_elapsed INTEGER NOT NULL,
                    total_days_in_period INTEGER NOT NULL,
                    percent_complete REAL NOT NULL,
                    projected_irrigation_gallons REAL,
                    projected_manual_gallons REAL,
                    projected_total_gallons REAL,
                    projected_tier INTEGER,
                    projected_total_cost REAL,
                    daily_irrigation_average REAL,
                    rate_config_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (rate_config_id) REFERENCES water_rate_configs(id),
                    UNIQUE(billing_period_start, calculation_date)
                )
            """)
            
            # Create daily cost snapshots table
            cursor.execute("""
                CREATE TABLE daily_cost_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date DATE NOT NULL,
                    billing_period_start DATE NOT NULL,
                    billing_period_end DATE NOT NULL,
                    irrigation_gallons_to_date REAL DEFAULT 0,
                    manual_watering_gallons_to_date REAL DEFAULT 0,
                    total_gallons_to_date REAL NOT NULL,
                    estimated_cost_to_date REAL NOT NULL,
                    usage_tier INTEGER NOT NULL,
                    daily_irrigation_gallons REAL DEFAULT 0,
                    daily_manual_watering_gallons REAL DEFAULT 0,
                    daily_cost_increase REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(snapshot_date, billing_period_start)
                )
            """)
            
            # Create cost analysis events table
            cursor.execute("""
                CREATE TABLE cost_analysis_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_date DATE NOT NULL,
                    event_type TEXT NOT NULL CHECK (event_type IN (
                        'TIER_CHANGE', 'COST_MILESTONE', 'USAGE_ALERT', 'BILLING_PERIOD_END', 
                        'PROJECTION_UPDATE', 'RATE_CHANGE'
                    )),
                    billing_period_start DATE NOT NULL,
                    event_description TEXT NOT NULL,
                    previous_value REAL,
                    current_value REAL,
                    threshold_value REAL,
                    total_usage_at_event REAL,
                    estimated_cost_at_event REAL,
                    tier_at_event INTEGER,
                    severity TEXT CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')) DEFAULT 'INFO',
                    automated BOOLEAN DEFAULT TRUE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for cost tracking tables
            cursor.execute("CREATE INDEX idx_water_rate_configs_effective_date ON water_rate_configs(effective_date)")
            cursor.execute("CREATE INDEX idx_billing_period_costs_period ON billing_period_costs(billing_period_start, billing_period_end)")
            cursor.execute("CREATE INDEX idx_billing_period_costs_calc_date ON billing_period_costs(calculation_date)")
            cursor.execute("CREATE INDEX idx_daily_cost_snapshots_date ON daily_cost_snapshots(snapshot_date)")
            cursor.execute("CREATE INDEX idx_daily_cost_snapshots_period ON daily_cost_snapshots(billing_period_start, snapshot_date)")
            cursor.execute("CREATE INDEX idx_cost_analysis_events_date_type ON cost_analysis_events(event_date, event_type)")
            cursor.execute("CREATE INDEX idx_cost_analysis_events_period ON cost_analysis_events(billing_period_start, event_date)")
            
            logger.info("Cost tracking tables created successfully")
        
        # Migrate actual_duration_minutes from INTEGER to REAL for fractional minutes
        # Check if we need to migrate the column type
        cursor.execute("PRAGMA table_info(actual_runs)")
        duration_column_info = [row for row in cursor.fetchall() if row[1] == 'actual_duration_minutes']
        if duration_column_info and 'INTEGER' in duration_column_info[0][2].upper():
            logger.info("Migrating actual_duration_minutes from INTEGER to REAL for fractional minute support")
            
            # SQLite doesn't support ALTER COLUMN TYPE directly, so we need to:
            # 1. Create a new column with REAL type
            # 2. Copy data from old column to new column  
            # 3. Drop old column and rename new column
            # But SQLite also doesn't support DROP COLUMN before version 3.35.0
            # So we'll use a table recreation approach
            
            # Clean up any existing temp table from failed previous migration
            cursor.execute("DROP TABLE IF EXISTS actual_runs_temp")
            
            # Create a temporary table with the new schema
            cursor.execute("""
                CREATE TABLE actual_runs_temp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_id INTEGER NOT NULL,
                    zone_name TEXT NOT NULL,
                    run_date DATE NOT NULL,
                    actual_start_time TIMESTAMP NOT NULL,
                    actual_duration_minutes REAL NOT NULL,  -- Changed from INTEGER to REAL
                    actual_gallons REAL,
                    status TEXT NOT NULL DEFAULT 'Normal watering cycle',
                    failure_reason TEXT,
                    current_ma REAL,
                    end_time TIMESTAMP,
                    source TEXT DEFAULT 'web_scraper' CHECK (source IN ('web_scraper', 'api', 'manual')),
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    raw_popup_text TEXT,
                    popup_lines_json TEXT,
                    parsed_summary TEXT,
                    water_efficiency REAL,
                    abort_reason TEXT,
                    usage_type TEXT CHECK (usage_type IN ('actual', 'estimated')) DEFAULT 'actual',
                    usage REAL,
                    usage_flag TEXT CHECK (usage_flag IN ('normal', 'too_high', 'too_low', 'zero_reported')) DEFAULT 'normal',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (zone_id) REFERENCES zones(zone_id),
                    UNIQUE(zone_id, actual_start_time)
                )
            """)
            
            # Copy all data from old table to new table (duration will be auto-converted to REAL)
            # Handle any NULL or invalid usage_type values by setting defaults
            cursor.execute("""
                INSERT INTO actual_runs_temp 
                SELECT 
                    id, zone_id, zone_name, run_date, actual_start_time, actual_duration_minutes,
                    actual_gallons, status, failure_reason, current_ma, end_time, source, scraped_at,
                    notes, raw_popup_text, popup_lines_json, parsed_summary, water_efficiency, abort_reason,
                    COALESCE(usage_type, 'actual') as usage_type,  -- Default NULL values to 'actual'
                    usage,
                    COALESCE(usage_flag, 'normal') as usage_flag,  -- Default NULL values to 'normal'
                    created_at
                FROM actual_runs
            """)
            
            # Drop views that depend on actual_runs table
            cursor.execute("DROP VIEW IF EXISTS v_daily_summary")
            cursor.execute("DROP VIEW IF EXISTS v_active_failures") 
            cursor.execute("DROP VIEW IF EXISTS v_zone_performance")
            
            # Drop the old table
            cursor.execute("DROP TABLE actual_runs")
            
            # Rename the temp table to the original name
            cursor.execute("ALTER TABLE actual_runs_temp RENAME TO actual_runs")
            
            # Recreate the views (from schema.sql)
            cursor.execute("""
                CREATE VIEW v_daily_summary AS
                SELECT 
                    date('now') as today,
                    z.zone_name,
                    z.priority_level,
                    
                    -- Scheduled data
                    COUNT(DISTINCT sr.id) as scheduled_runs,
                    COALESCE(SUM(sr.scheduled_duration_minutes), 0) as scheduled_minutes,
                    COALESCE(SUM(sr.expected_gallons), 0) as scheduled_gallons,
                    
                    -- Actual data  
                    COUNT(DISTINCT ar.id) as actual_runs,
                    COALESCE(SUM(ar.actual_duration_minutes), 0) as actual_minutes,
                    COALESCE(SUM(ar.actual_gallons), 0) as actual_gallons,
                    
                    -- Variance
                    (COUNT(DISTINCT ar.id) - COUNT(DISTINCT sr.id)) as run_variance,
                    (COALESCE(SUM(ar.actual_gallons), 0) - COALESCE(SUM(sr.expected_gallons), 0)) as water_variance
                    
                FROM zones z
                LEFT JOIN scheduled_runs sr ON z.zone_id = sr.zone_id AND sr.schedule_date = date('now')
                LEFT JOIN actual_runs ar ON z.zone_id = ar.zone_id AND ar.run_date = date('now')
                GROUP BY z.zone_id, z.zone_name, z.priority_level
            """)
            
            cursor.execute("""
                CREATE VIEW v_active_failures AS
                SELECT 
                    fe.*,
                    z.priority_level,
                    z.flow_rate_gpm,
                    CASE 
                        WHEN fe.detected_at > datetime('now', '-1 hour') THEN 'IMMEDIATE'
                        WHEN fe.detected_at > datetime('now', '-6 hours') THEN 'URGENT' 
                        ELSE 'REVIEW'
                    END as urgency_level
                FROM failure_events fe
                JOIN zones z ON fe.zone_id = z.zone_id
                WHERE fe.resolved = FALSE
                ORDER BY 
                    CASE fe.severity 
                        WHEN 'CRITICAL' THEN 1 
                        WHEN 'WARNING' THEN 2 
                        ELSE 3 
                    END,
                    fe.detected_at DESC
            """)
            
            cursor.execute("""
                CREATE VIEW v_zone_performance AS
                SELECT 
                    z.zone_name,
                    z.priority_level,
                    COUNT(DISTINCT dv.analysis_date) as days_analyzed,
                    AVG(dv.water_efficiency_percent) as avg_efficiency,
                    SUM(CASE WHEN dv.variance_severity = 'CRITICAL' THEN 1 ELSE 0 END) as critical_days,
                    SUM(CASE WHEN dv.variance_severity = 'WARNING' THEN 1 ELSE 0 END) as warning_days,
                    AVG(dv.water_variance_gallons) as avg_water_variance,
                    MAX(dv.analyzed_at) as last_analysis
                FROM zones z
                LEFT JOIN daily_variance dv ON z.zone_id = dv.zone_id 
                    AND dv.analysis_date >= date('now', '-30 days')
                GROUP BY z.zone_id, z.zone_name, z.priority_level
            """)
            
            # Recreate the index for actual_runs
            cursor.execute("CREATE INDEX idx_actual_runs_date_zone ON actual_runs(run_date, zone_id)")
            cursor.execute("CREATE INDEX idx_actual_runs_start_time ON actual_runs(actual_start_time)")
            
            logger.info("Successfully migrated actual_duration_minutes to REAL type")
            
        # Check if collection_status table exists for completion tracking
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collection_status'")
        collection_status_exists = cursor.fetchone() is not None
        
        if not collection_status_exists:
            logger.info("Creating collection_status table for completion tracking")
            cursor.execute("""
                CREATE TABLE collection_status (
                    date TEXT PRIMARY KEY,
                    schedules_complete BOOLEAN DEFAULT FALSE,
                    runs_complete BOOLEAN DEFAULT FALSE,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
        conn.commit()
        logger.info("Schema migration completed successfully")
                
    def _initialize_zones(self):
        """Initialize zones table with configured irrigation zones"""
        logger.info("Initializing zones from configuration...")
        
        # Get zone data from configuration
        zones_data = self.zone_config.get_zones_data()
        average_flow_rates = self.zone_config.get_average_flow_rates()
        
        if not zones_data:
            logger.warning("No zone configuration found - database will have empty zones table")
            return
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for zone_id, name, flow_rate_gpm, priority, plant_type in zones_data:
                # Get the average flow rate for this zone from configuration
                avg_flow_rate = average_flow_rates.get(zone_id, flow_rate_gpm)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO zones 
                    (zone_id, zone_name, zone_display_name, priority_level, flow_rate_gpm, plant_type, average_flow_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (zone_id, name, name, priority, flow_rate_gpm, plant_type, avg_flow_rate))
                
            # Update average flow rates for existing zones
            self._update_average_flow_rates_from_config()
                
            conn.commit()
            logger.info(f"Initialized {len(zones_data)} zones from configuration")
    
    def _update_average_flow_rates_from_config(self):
        """Update average flow rates for existing zones from configuration"""
        flow_rate_updates = self.zone_config.get_average_flow_rates()
        
        if not flow_rate_updates:
            logger.info("No average flow rates configured - skipping update")
            return
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for zone_id, avg_rate in flow_rate_updates.items():
                cursor.execute("""
                    UPDATE zones 
                    SET average_flow_rate = ?
                    WHERE zone_id = ?
                """, (avg_rate, zone_id))
            
            conn.commit()
            logger.info(f"Updated average flow rates for {len(flow_rate_updates)} zones from configuration")
    
    def update_zone_average_flow_rate(self, zone_id: int, average_flow_rate: float):
        """Update average flow rate for a specific zone
        
        Args:
            zone_id: Zone ID to update
            average_flow_rate: New average flow rate in GPM
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE zones 
                SET average_flow_rate = ?, updated_at = CURRENT_TIMESTAMP
                WHERE zone_id = ?
            """, (average_flow_rate, zone_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                # Also update the configuration
                self.zone_config.update_flow_rate(zone_id, average_flow_rate)
                logger.info(f"Updated average flow rate for zone {zone_id}: {average_flow_rate} GPM")
                return True
            else:
                logger.warning(f"Zone {zone_id} not found for flow rate update")
                return False
            
    def get_zone_id_by_name(self, zone_name: str) -> Optional[int]:
        """Get zone ID by matching zone name (fuzzy matching)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Try exact match first
            cursor.execute("SELECT zone_id FROM zones WHERE zone_name = ? OR zone_display_name = ?", 
                          (zone_name, zone_name))
            result = cursor.fetchone()
            if result:
                return result[0]
                
            # Try fuzzy matching for common variations
            cursor.execute("SELECT zone_id, zone_name FROM zones")
            all_zones = cursor.fetchall()
            
            for zone_id, db_name in all_zones:
                # Remove common suffixes and normalize
                normalized_input = zone_name.lower().replace(" (m)", "").replace(" (s)", "").replace(" (m/d)", "")
                normalized_db = db_name.lower().replace(" (m)", "").replace(" (s)", "").replace(" (m/d)", "")
                
                if normalized_input in normalized_db or normalized_db in normalized_input:
                    return zone_id
                    
            # If no match found, create a new zone entry
            logger.warning(f"Zone '{zone_name}' not found in database, creating new entry")
            return self._create_unknown_zone(zone_name)
            
    def _create_unknown_zone(self, zone_name: str) -> int:
        """Create a new zone entry for unknown zones encountered during scraping"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get next available zone ID
            cursor.execute("SELECT MAX(zone_id) FROM zones")
            max_id = cursor.fetchone()[0] or 0
            new_zone_id = max_id + 1
            
            # Determine priority based on name patterns
            if any(word in zone_name.lower() for word in ['turf', 'grass', 'lawn']):
                priority = 'LOW'
                plant_type = 'turf'
            elif any(word in zone_name.lower() for word in ['planters', 'pots', 'color']):
                priority = 'HIGH'
                plant_type = 'planters'
            else:
                priority = 'MEDIUM'
                plant_type = 'beds'
                
            cursor.execute("""
                INSERT INTO zones (zone_id, zone_name, zone_display_name, priority_level, plant_type, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (new_zone_id, zone_name, zone_name, priority, plant_type, "Auto-created from scraper"))
            
            conn.commit()
            logger.info(f"Created new zone: {new_zone_id} - {zone_name}")
            return new_zone_id
            
    def store_scheduled_runs(self, scheduled_runs: List[ScheduledRun], collection_date: date = None) -> int:
        """Store scheduled runs in database with popup line data"""
        if collection_date is None:
            collection_date = date.today()
            
        stored_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for run in scheduled_runs:
                try:
                    zone_id = self.get_zone_id_by_name(run.zone_name)
                    
                    # Calculate expected gallons if we have flow rate
                    expected_gallons = None
                    if zone_id:
                        cursor.execute("SELECT flow_rate_gpm FROM zones WHERE zone_id = ?", (zone_id,))
                        flow_rate = cursor.fetchone()
                        if flow_rate and flow_rate[0]:
                            expected_gallons = flow_rate[0] * (run.duration_minutes / 60.0)
                    
                    # Extract popup data if available
                    raw_popup_text = getattr(run, 'raw_popup_text', None)
                    popup_lines_json = None
                    parsed_summary = getattr(run, 'parsed_summary', None)
                    
                    if hasattr(run, 'popup_lines') and run.popup_lines:
                        popup_lines_json = json.dumps(run.popup_lines)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO scheduled_runs 
                        (zone_id, zone_name, schedule_date, scheduled_start_time, 
                         scheduled_duration_minutes, expected_gallons, notes,
                         raw_popup_text, popup_lines_json, parsed_summary)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        zone_id,
                        run.zone_name,
                        collection_date,
                        run.start_time,
                        run.duration_minutes,
                        expected_gallons,
                        run.notes or "",
                        raw_popup_text,
                        popup_lines_json,
                        parsed_summary
                    ))
                    
                    stored_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to store scheduled run for {run.zone_name}: {e}")
                    
            conn.commit()
            
        logger.info(f"Stored {stored_count}/{len(scheduled_runs)} scheduled runs for {collection_date}")
        return stored_count
        
    def store_actual_runs(self, actual_runs: List[ActualRun], collection_date: date = None) -> int:
        """Store actual runs in database with popup line data"""
        if collection_date is None:
            collection_date = date.today()
            
        stored_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for run in actual_runs:
                try:
                    zone_id = self.get_zone_id_by_name(run.zone_name)
                    
                    # Calculate end time
                    end_time = run.start_time + timedelta(minutes=run.duration_minutes)
                    
                    # Extract popup data if available
                    raw_popup_text = getattr(run, 'raw_popup_text', None)
                    popup_lines_json = None
                    parsed_summary = getattr(run, 'parsed_summary', None)
                    
                    if hasattr(run, 'popup_lines') and run.popup_lines:
                        popup_lines_json = json.dumps(run.popup_lines)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO actual_runs 
                        (zone_id, zone_name, run_date, actual_start_time, actual_duration_minutes,
                         actual_gallons, status, failure_reason, end_time, notes,
                         raw_popup_text, popup_lines_json, parsed_summary)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        zone_id,
                        run.zone_name,
                        collection_date,
                        run.start_time,
                        run.duration_minutes,
                        run.actual_gallons,
                        run.status,
                        run.failure_reason,
                        end_time,
                        run.notes or "",
                        raw_popup_text,
                        popup_lines_json,
                        parsed_summary
                    ))
                    
                    stored_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to store actual run for {run.zone_name}: {e}")
                    
            conn.commit()
            
        logger.info(f"Stored {stored_count}/{len(actual_runs)} actual runs for {collection_date}")
        return stored_count
        
    def calculate_daily_variance(self, analysis_date: date = None) -> Dict[str, Any]:
        """Calculate and store daily variance analysis"""
        if analysis_date is None:
            analysis_date = date.today()
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all zones that had scheduled or actual runs
            cursor.execute("""
                SELECT DISTINCT z.zone_id, z.zone_name, z.priority_level
                FROM zones z
                WHERE z.zone_id IN (
                    SELECT zone_id FROM scheduled_runs WHERE schedule_date = ?
                    UNION
                    SELECT zone_id FROM actual_runs WHERE run_date = ?
                )
            """, (analysis_date, analysis_date))
            
            zones = cursor.fetchall()
            variance_results = []
            
            for zone_id, zone_name, priority in zones:
                # Get scheduled totals
                cursor.execute("""
                    SELECT 
                        COUNT(*) as scheduled_count,
                        COALESCE(SUM(scheduled_duration_minutes), 0) as scheduled_minutes,
                        COALESCE(SUM(expected_gallons), 0) as scheduled_gallons
                    FROM scheduled_runs 
                    WHERE zone_id = ? AND schedule_date = ?
                """, (zone_id, analysis_date))
                
                scheduled_data = cursor.fetchone()
                
                # Get actual totals
                cursor.execute("""
                    SELECT 
                        COUNT(*) as actual_count,
                        COALESCE(SUM(actual_duration_minutes), 0) as actual_minutes,
                        COALESCE(SUM(actual_gallons), 0) as actual_gallons
                    FROM actual_runs 
                    WHERE zone_id = ? AND run_date = ?
                """, (zone_id, analysis_date))
                
                actual_data = cursor.fetchone()
                
                # Calculate variance
                run_variance = actual_data[0] - scheduled_data[0]
                duration_variance = actual_data[1] - scheduled_data[1] 
                water_variance = actual_data[2] - scheduled_data[2]
                
                efficiency = 0
                if scheduled_data[2] > 0:
                    efficiency = (actual_data[2] / scheduled_data[2]) * 100
                    
                # Determine severity
                severity = 'NORMAL'
                has_failures = False
                has_warnings = False
                
                if run_variance < 0:  # Missing runs
                    severity = 'CRITICAL'
                    has_failures = True
                elif abs(water_variance) > (scheduled_data[2] * 0.25):  # >25% water variance
                    severity = 'WARNING'
                    has_warnings = True
                elif abs(duration_variance) > 2:  # >2 minute duration variance
                    severity = 'WARNING'
                    has_warnings = True
                    
                # Store variance record
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_variance
                    (analysis_date, zone_id, zone_name, scheduled_runs_count, scheduled_total_minutes,
                     scheduled_total_gallons, actual_runs_count, actual_total_minutes, actual_total_gallons,
                     run_count_variance, duration_variance_minutes, water_variance_gallons,
                     water_efficiency_percent, has_failures, has_warnings, variance_severity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    analysis_date, zone_id, zone_name,
                    scheduled_data[0], scheduled_data[1], scheduled_data[2],
                    actual_data[0], actual_data[1], actual_data[2],
                    run_variance, duration_variance, water_variance, efficiency,
                    has_failures, has_warnings, severity
                ))
                
                variance_results.append({
                    'zone_name': zone_name,
                    'priority': priority,
                    'run_variance': run_variance,
                    'water_variance': water_variance,
                    'efficiency': efficiency,
                    'severity': severity
                })
                
            conn.commit()
            
        logger.info(f"Calculated variance for {len(zones)} zones on {analysis_date}")
        return {
            'analysis_date': analysis_date,
            'zones_analyzed': len(zones),
            'variance_results': variance_results
        }
        
    def log_collection_session(self, collection_type: str, scheduled_count: int, 
                             actual_count: int, errors: int = 0, details: str = None) -> None:
        """Log a data collection session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO collection_log 
                (collection_date, collection_type, status, scheduled_runs_collected,
                 actual_runs_collected, start_time, end_time, errors_encountered, error_details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date.today(),
                collection_type,
                'SUCCESS' if errors == 0 else 'PARTIAL' if scheduled_count > 0 or actual_count > 0 else 'FAILED',
                scheduled_count,
                actual_count,
                datetime.now(),
                datetime.now(),
                errors,
                details
            ))
            
            conn.commit()
            
    def get_recent_collections(self, days: int = 7) -> List[Dict]:
        """Get recent data collection history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM collection_log 
                WHERE collection_date >= date('now', '-{} days')
                ORDER BY start_time DESC
            """.format(days))
            
            return [dict(row) for row in cursor.fetchall()]
            
    def get_daily_summary(self, target_date: date = None) -> Dict[str, Any]:
        """Get comprehensive daily summary"""
        if target_date is None:
            target_date = date.today()
            
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Use the daily summary view
            cursor.execute("SELECT * FROM v_daily_summary")
            summary_data = [dict(row) for row in cursor.fetchall()]
            
            # Get failure counts
            cursor.execute("""
                SELECT severity, COUNT(*) as count
                FROM failure_events 
                WHERE failure_date = ? AND resolved = FALSE
                GROUP BY severity
            """, (target_date,))
            
            failure_counts = {row['severity']: row['count'] for row in cursor.fetchall()}
            
            return {
                'date': target_date,
                'zone_summaries': summary_data,
                'failure_counts': failure_counts,
                'total_zones': len(summary_data),
                'zones_with_issues': len([z for z in summary_data if z['run_variance'] != 0])
            }
            
    def get_active_failures(self) -> List[Dict]:
        """Get all active failures requiring attention"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM v_active_failures")
            return [dict(row) for row in cursor.fetchall()]
            
    def close(self):
        """Close database connection"""
        # SQLite connections are opened per query, so nothing to close
        pass
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def main():
    """Test the database manager"""
    print("Testing Database Manager")
    print("=" * 50)
    
    # Initialize database
    db = DatabaseManager()
    
    # Test zone lookup
    zone_id = db.get_zone_id_by_name("Front Planters & Pots")
    print(f"Zone ID for 'Front Planters & Pots': {zone_id}")
    
    # Get recent collections
    collections = db.get_recent_collections(7)
    print(f"Recent collections: {len(collections)}")
    
    # Get daily summary
    summary = db.get_daily_summary()
    print(f"Daily summary for {summary['date']}: {summary['total_zones']} zones")
    
    print("Database manager test completed successfully!")

if __name__ == "__main__":
    main()
