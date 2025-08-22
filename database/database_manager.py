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
import hashlib
import json

# Import our data models
from hydrawise_web_scraper import ScheduledRun, ActualRun

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages all database operations for irrigation monitoring"""
    
    def __init__(self, db_path: str = "database/irrigation_data.db"):
        """Initialize database manager with SQLite database"""
        self.db_path = db_path
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
        """Apply schema migrations for popup data fields and enhanced matching"""
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
            
        conn.commit()
        logger.info("Schema migration completed successfully")
                
    def _initialize_zones(self):
        """Initialize zones table with known irrigation zones"""
        # Based on your flow rate data from config/failure_detection_rules.py
        zones_data = [
            (1, "Front Right Turf", 2.5, "LOW", "turf"),
            (2, "Front Turf Across Sidewalk", 4.5, "LOW", "turf"), 
            (3, "Front Left Turf", 3.2, "LOW", "turf"),
            (4, "Front Planters & Pots", 1.0, "HIGH", "planters"),
            (5, "Rear Left Turf", 2.2, "LOW", "turf"),
            (6, "Rear Right Turf", 5.3, "LOW", "turf"),
            (8, "Rear Left Beds at Fence (S)", 11.3, "HIGH", "beds"),
            (9, "Rear Right Beds at Fence (S)", 8.3, "HIGH", "beds"),
            (10, "Rear Left Pots, Baskets & Planters (M)", 3.9, "HIGH", "planters"),
            (11, "Rear Right Pots, Baskets & Planters (M)", 5.7, "HIGH", "planters"),
            (12, "Rear Bed/Planters at Pool (M)", 1.3, "MEDIUM", "beds"),
            (13, "Front Right Bed Across Drive", 1.2, "MEDIUM", "beds"),
            (14, "Rear Right Bed at House and Pool (M/D)", 3.0, "MEDIUM", "beds"),
            (15, "Rear Left Bed at House", 1.2, "MEDIUM", "beds"),
            (16, "Front Color (S)", 10.9, "HIGH", "color"),
            (17, "Front Left Beds", 2.6, "MEDIUM", "beds"),
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for zone_id, name, flow_rate, priority, plant_type in zones_data:
                cursor.execute("""
                    INSERT OR IGNORE INTO zones 
                    (zone_id, zone_name, zone_display_name, priority_level, flow_rate_gpm, plant_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (zone_id, name, name, priority, flow_rate, plant_type))
                
            conn.commit()
            logger.info(f"Initialized {len(zones_data)} zones")
            
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
