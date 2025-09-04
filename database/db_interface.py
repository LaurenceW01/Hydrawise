#!/usr/bin/env python3
"""
Database Interface Module for Hydrawise

Simple interface for reading and writing irrigation data to the database.
Wraps the IntelligentDataStorage class for easy use.

Author: AI Assistant
Date: 2025-08-23
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path

# Add parent directory to path to import our modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from database.universal_database_manager import get_universal_database_manager
from database.cloud_storage_sync import CloudStorageSync

logger = logging.getLogger(__name__)

class HydrawiseDB:
    """
    Simple database interface for Hydrawise irrigation data
    
    Provides easy methods to:
    - Write scheduled runs to DB
    - Write actual runs to DB  
    - Read scheduled runs from DB
    - Read actual runs from DB
    - Sync with cloud storage
    """
    
    def __init__(self, db_path: str = None, use_cloud_sync: bool = True):
        """
        Initialize database interface
        
        Args:
            db_path: Path to local database file (ignored for universal manager)
            use_cloud_sync: Whether to sync with Google Cloud Storage
        """
        self.use_cloud_sync = use_cloud_sync
        
        # Initialize universal database manager (handles both SQLite and PostgreSQL)
        self.storage = get_universal_database_manager()
        
        # Initialize cloud sync if enabled
        self.cloud_sync = None
        if use_cloud_sync:
            try:
                # Get bucket name from environment or use default
                bucket_name = os.getenv('GCS_BUCKET_NAME', 'hydrawise-database')
                credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                
                self.cloud_sync = CloudStorageSync(
                    bucket_name=bucket_name,
                    credentials_path=credentials_path
                )
                logger.info(f"Cloud storage sync enabled for bucket: {bucket_name}")
            except Exception as e:
                logger.warning(f"Cloud sync disabled: {e}")
                self.use_cloud_sync = False
        
        logger.info(f"Database interface initialized: {db_path}")
    
    # ========== WRITE METHODS ==========
    
    def write_scheduled_runs(self, scheduled_runs: List, target_date: date = None) -> int:
        """
        Write scheduled runs to database
        
        Args:
            scheduled_runs: List of ScheduledRun objects from web scraper
            target_date: Date the schedule was collected for (defaults to today)
            
        Returns:
            Number of runs successfully stored
        """
        if target_date is None:
            target_date = date.today()
            
        logger.info(f"Writing {len(scheduled_runs)} scheduled runs for {target_date}")
        
        # Sync down latest data before writing
        if self.use_cloud_sync:
            try:
                self.cloud_sync.sync_down()
                logger.info("Synced latest data from cloud before writing")
            except Exception as e:
                logger.warning(f"Cloud sync down failed: {e}")
        
        # Store the data using universal database manager
        stored_count = self.storage.insert_scheduled_runs(scheduled_runs, target_date)
        
        # Sync up after writing
        if self.use_cloud_sync and stored_count > 0:
            try:
                self.cloud_sync.sync_up()
                logger.info("Synced new data to cloud after writing")
            except Exception as e:
                logger.warning(f"Cloud sync up failed: {e}")
        
        logger.info(f"Successfully wrote {stored_count} scheduled runs to database")
        return stored_count
    
    def write_actual_runs(self, actual_runs: List, target_date: date = None) -> int:
        """
        Write actual runs to database
        
        Args:
            actual_runs: List of ActualRun objects from web scraper
            target_date: Date the runs occurred (defaults to today)
            
        Returns:
            Number of runs successfully stored
        """
        if target_date is None:
            target_date = date.today()
            
        logger.info(f"Writing {len(actual_runs)} actual runs for {target_date}")
        
        # Sync down latest data before writing
        if self.use_cloud_sync:
            try:
                self.cloud_sync.sync_down()
                logger.info("Synced latest data from cloud before writing")
            except Exception as e:
                logger.warning(f"Cloud sync down failed: {e}")
        
        # Store the data
        result = self.storage.insert_actual_runs(actual_runs, target_date)
        
        # Handle both old int return and new dict return for backwards compatibility
        if isinstance(result, dict):
            stored_count = result['new'] + result['updated']
        else:
            stored_count = result
            result = {'new': stored_count, 'updated': 0, 'unchanged': 0, 'total': len(actual_runs)}
        
        # Sync up after writing
        if self.use_cloud_sync and stored_count > 0:
            try:
                self.cloud_sync.sync_up()
                logger.info("Synced new data to cloud after writing")
            except Exception as e:
                logger.warning(f"Cloud sync up failed: {e}")
        
        logger.info(f"Successfully wrote actual runs to database: {result['new']} new, {result['updated']} updated")
        return result
    
    # ========== READ METHODS ==========
    
    def read_scheduled_runs(self, target_date: date = None, zone_name: str = None) -> List[Dict]:
        """
        Read scheduled runs from database
        
        Args:
            target_date: Date to read schedule for (defaults to today)
            zone_name: Optional filter by zone name
            
        Returns:
            List of scheduled run dictionaries
        """
        if target_date is None:
            target_date = date.today()
            
        # Sync down latest data before reading
        if self.use_cloud_sync:
            try:
                self.cloud_sync.sync_down()
                logger.debug("Synced latest data from cloud before reading")
            except Exception as e:
                logger.warning(f"Cloud sync down failed: {e}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                if zone_name:
                    cursor.execute("""
                        SELECT * FROM scheduled_runs 
                        WHERE schedule_date = ? AND zone_name = ?
                        ORDER BY scheduled_start_time
                    """, (target_date, zone_name))
                else:
                    cursor.execute("""
                        SELECT * FROM scheduled_runs 
                        WHERE schedule_date = ?
                        ORDER BY scheduled_start_time
                    """, (target_date,))
                
                results = [dict(row) for row in cursor.fetchall()]
                logger.info(f"Read {len(results)} scheduled runs for {target_date}")
                return results
                
        except Exception as e:
            logger.error(f"Failed to read scheduled runs: {e}")
            return []
    
    def read_actual_runs(self, target_date: date = None, zone_name: str = None) -> List[Dict]:
        """
        Read actual runs from database
        
        Args:
            target_date: Date to read actual runs for (defaults to today)
            zone_name: Optional filter by zone name
            
        Returns:
            List of actual run dictionaries
        """
        if target_date is None:
            target_date = date.today()
            
        # Sync down latest data before reading
        if self.use_cloud_sync:
            try:
                self.cloud_sync.sync_down()
                logger.debug("Synced latest data from cloud before reading")
            except Exception as e:
                logger.warning(f"Cloud sync down failed: {e}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                if zone_name:
                    cursor.execute("""
                        SELECT * FROM actual_runs 
                        WHERE run_date = ? AND zone_name = ?
                        ORDER BY actual_start_time
                    """, (target_date, zone_name))
                else:
                    cursor.execute("""
                        SELECT * FROM actual_runs 
                        WHERE run_date = ?
                        ORDER BY actual_start_time
                    """, (target_date,))
                
                results = [dict(row) for row in cursor.fetchall()]
                logger.info(f"Read {len(results)} actual runs for {target_date}")
                return results
                
        except Exception as e:
            logger.error(f"Failed to read actual runs: {e}")
            return []
    
    def read_schedule_summary(self, start_date: date = None, days: int = 7) -> Dict[str, Any]:
        """
        Read schedule summary for multiple days
        
        Args:
            start_date: Starting date (defaults to today)
            days: Number of days to include
            
        Returns:
            Dictionary with schedule summary data
        """
        if start_date is None:
            start_date = date.today()
            
        end_date = start_date + timedelta(days=days-1)
        
        # Sync down latest data before reading
        if self.use_cloud_sync:
            try:
                self.cloud_sync.sync_down()
                logger.debug("Synced latest data from cloud before reading summary")
            except Exception as e:
                logger.warning(f"Cloud sync down failed: {e}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get scheduled runs count by date
                cursor.execute("""
                    SELECT schedule_date, COUNT(*) as scheduled_count,
                           SUM(CASE WHEN is_rain_cancelled = 1 THEN 1 ELSE 0 END) as rain_cancelled_count,
                           SUM(scheduled_duration_minutes) as total_scheduled_minutes
                    FROM scheduled_runs 
                    WHERE schedule_date BETWEEN ? AND ?
                    GROUP BY schedule_date
                    ORDER BY schedule_date
                """, (start_date, end_date))
                
                scheduled_data = cursor.fetchall()
                
                # Get actual runs count by date
                cursor.execute("""
                    SELECT run_date, COUNT(*) as actual_count,
                           SUM(actual_duration_minutes) as total_actual_minutes,
                           SUM(actual_gallons) as total_gallons
                    FROM actual_runs 
                    WHERE run_date BETWEEN ? AND ?
                    GROUP BY run_date
                    ORDER BY run_date
                """, (start_date, end_date))
                
                actual_data = cursor.fetchall()
                
                summary = {
                    'date_range': f"{start_date} to {end_date}",
                    'scheduled_by_date': [
                        {
                            'date': row[0],
                            'scheduled_count': row[1],
                            'rain_cancelled_count': row[2],
                            'total_scheduled_minutes': row[3]
                        } for row in scheduled_data
                    ],
                    'actual_by_date': [
                        {
                            'date': row[0],
                            'actual_count': row[1],
                            'total_actual_minutes': row[2],
                            'total_gallons': row[3]
                        } for row in actual_data
                    ]
                }
                
                logger.info(f"Generated schedule summary for {start_date} to {end_date}")
                return summary
                
        except Exception as e:
            logger.error(f"Failed to read schedule summary: {e}")
            return {}
    
    # ========== UTILITY METHODS ==========
    
    def sync_with_cloud(self, direction: str = "both") -> bool:
        """
        Manually sync with cloud storage
        
        Args:
            direction: "up", "down", or "both"
            
        Returns:
            True if successful, False otherwise
        """
        if not self.use_cloud_sync:
            logger.warning("Cloud sync is disabled")
            return False
            
        try:
            if direction in ["down", "both"]:
                self.cloud_sync.sync_down()
                logger.info("Cloud sync down completed")
                
            if direction in ["up", "both"]:
                self.cloud_sync.sync_up()
                logger.info("Cloud sync up completed")
                
            return True
            
        except Exception as e:
            logger.error(f"Cloud sync failed: {e}")
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get information about the database
        
        Returns:
            Dictionary with database statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get table counts
                cursor.execute("SELECT COUNT(*) FROM scheduled_runs")
                scheduled_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM actual_runs")
                actual_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM zones")
                zones_count = cursor.fetchone()[0]
                
                # Get date range
                cursor.execute("SELECT MIN(schedule_date), MAX(schedule_date) FROM scheduled_runs")
                scheduled_date_range = cursor.fetchone()
                
                cursor.execute("SELECT MIN(run_date), MAX(run_date) FROM actual_runs")
                actual_date_range = cursor.fetchone()
                
                return {
                    'database_path': self.db_path,
                    'cloud_sync_enabled': self.use_cloud_sync,
                    'scheduled_runs_count': scheduled_count,
                    'actual_runs_count': actual_count,
                    'zones_count': zones_count,
                    'scheduled_date_range': scheduled_date_range,
                    'actual_date_range': actual_date_range
                }
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {}


def main():
    """Test the database interface"""
    print("[DATABASE]  Testing Hydrawise Database Interface")
    print("=" * 50)
    
    try:
        # Initialize database interface
        print("[RESULTS] Initializing database interface...")
        db = HydrawiseDB(use_cloud_sync=False)  # Disable cloud sync for testing
        
        # Get database info
        print("\n[LOG] Database Information:")
        info = db.get_database_info()
        for key, value in info.items():
            print(f"   {key}: {value}")
        
        # Test reading data
        print(f"\n[SYMBOL] Reading today's scheduled runs...")
        scheduled = db.read_scheduled_runs()
        print(f"   Found {len(scheduled)} scheduled runs")
        
        if scheduled:
            print("   Sample scheduled run:")
            sample = scheduled[0]
            print(f"      Zone: {sample.get('zone_name')}")
            print(f"      Time: {sample.get('scheduled_start_time')}")
            print(f"      Duration: {sample.get('scheduled_duration_minutes')} min")
        
        print(f"\n[SYMBOL] Reading today's actual runs...")
        actual = db.read_actual_runs()
        print(f"   Found {len(actual)} actual runs")
        
        if actual:
            print("   Sample actual run:")
            sample = actual[0]
            print(f"      Zone: {sample.get('zone_name')}")
            print(f"      Time: {sample.get('actual_start_time')}")
            print(f"      Duration: {sample.get('actual_duration_minutes')} min")
            print(f"      Gallons: {sample.get('actual_gallons')}")
        
        # Test summary
        print(f"\n[RESULTS] Schedule summary (last 7 days):")
        summary = db.read_schedule_summary()
        print(f"   Date range: {summary.get('date_range')}")
        print(f"   Scheduled data points: {len(summary.get('scheduled_by_date', []))}")
        print(f"   Actual data points: {len(summary.get('actual_by_date', []))}")
        
        print("\n[OK] Database interface test completed successfully!")
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
