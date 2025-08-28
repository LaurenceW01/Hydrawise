#!/usr/bin/env python3
"""
Intelligent Data Storage Module for Hydrawise

Enhanced storage of scheduled and actual run data with all popup information
to enable precise matching and mismatch detection.

Author: AI Assistant
Date: 2025
"""

import json
import logging
import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Any
from database.database_manager import DatabaseManager
from database.water_usage_estimator import WaterUsageEstimator
from utils.timezone_utils import get_database_timestamp, to_houston_time

logger = logging.getLogger(__name__)

class IntelligentDataStorage(DatabaseManager):
    """Enhanced database manager with intelligent data storage capabilities"""
    
    def __init__(self, *args, high_usage_multiplier: float = None, low_usage_multiplier: float = None, **kwargs):
        """Initialize with water usage estimator and zone lookup cache
        
        Args:
            high_usage_multiplier: Multiplier for too_high usage flag (defaults to 2.0)
            low_usage_multiplier: Multiplier for too_low usage flag (defaults to 0.5)
        """
        super().__init__(*args, **kwargs)
        self.usage_estimator = WaterUsageEstimator(
            self.db_path, 
            high_usage_multiplier=high_usage_multiplier, 
            low_usage_multiplier=low_usage_multiplier
        )
        self._zone_cache = {}  # Cache zone ID lookups to reduce database calls
        self._load_zone_cache()
    
    def set_usage_deviation_thresholds(self, high_usage_multiplier: float, low_usage_multiplier: float):
        """Update the usage deviation thresholds for the water usage estimator
        
        Args:
            high_usage_multiplier: New threshold for too_high usage flag
            low_usage_multiplier: New threshold for too_low usage flag
        """
        self.usage_estimator.set_deviation_thresholds(high_usage_multiplier, low_usage_multiplier)
    
    def get_usage_deviation_thresholds(self) -> Tuple[float, float]:
        """Get current usage deviation thresholds
        
        Returns:
            Tuple of (high_usage_multiplier, low_usage_multiplier)
        """
        return self.usage_estimator.get_deviation_thresholds()
    
    def _load_zone_cache(self):
        """Load zone ID mappings into cache to avoid database calls during transactions"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT zone_id, zone_name, zone_display_name FROM zones")
                
                for zone_id, zone_name, zone_display_name in cursor.fetchall():
                    # Cache both zone_name and zone_display_name
                    self._zone_cache[zone_name] = zone_id
                    if zone_display_name and zone_display_name != zone_name:
                        self._zone_cache[zone_display_name] = zone_id
                    
                    # Add common variations to handle scraped name differences
                    self._add_zone_name_variations(zone_name, zone_id)
                        
            logger.info(f"Loaded {len(self._zone_cache)} zone name mappings into cache")
            
        except Exception as e:
            logger.error(f"Failed to load zone cache: {e}")
    
    def _add_zone_name_variations(self, zone_name: str, zone_id: int):
        """Add common zone name variations to cache"""
        # Handle common differences between config and scraped names
        variations = [
            zone_name.replace(" and ", " & "),     # "and" vs "&"
            zone_name.replace(" & ", " and "),     # "&" vs "and"
            zone_name.replace("/", " / "),         # Spacing around "/"
            zone_name.replace(" / ", "/"),         # Remove spacing around "/"
            zone_name + " (M)",                    # Manual indicator
            zone_name + " (S)",                    # Sensor indicator  
            zone_name + " (M/D)",                  # Manual/Drip indicator
            zone_name + " (D)",                    # Drip indicator
            zone_name.replace(" (M)", ""),         # Remove indicators
            zone_name.replace(" (S)", ""),
            zone_name.replace(" (M/D)", ""),
            zone_name.replace(" (D)", ""),
        ]
        
        for variation in variations:
            if variation != zone_name and variation not in self._zone_cache:
                self._zone_cache[variation] = zone_id
    
    def _get_zone_id_cached(self, zone_name: str) -> Optional[int]:
        """Get zone ID using cache to avoid database calls during transactions"""
        # Try exact match first
        if zone_name in self._zone_cache:
            return self._zone_cache[zone_name]
        
        # Try fuzzy matching for common variations
        zone_lower = zone_name.lower().strip()
        for cached_name, zone_id in self._zone_cache.items():
            if cached_name.lower().strip() == zone_lower:
                # Cache this variation for future use
                self._zone_cache[zone_name] = zone_id
                return zone_id
        
        # If not found, we'll need to create it, but NOT during an active transaction
        return None
    
    def store_scheduled_runs_enhanced(self, scheduled_runs: List, collection_date: date = None) -> Dict[str, int]:
        """
        Store scheduled runs with enhanced popup data extraction and intelligent duplicate detection
        
        Args:
            scheduled_runs: List of ScheduledRun objects with popup data
            collection_date: Date the schedule was collected for
            
        Returns:
            Dictionary with counts: {'new': int, 'updated': int, 'unchanged': int, 'total': int}
        """
        if collection_date is None:
            collection_date = date.today()
            
        counts = {'new': 0, 'updated': 0, 'unchanged': 0, 'total': len(scheduled_runs)}
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for run in scheduled_runs:
                try:
                    zone_id = self.get_zone_id_by_name(run.zone_name)
                    
                    # Extract detailed popup data
                    popup_analysis = self._analyze_popup_data(run)
                    
                    # Calculate expected gallons from flow rate if available
                    expected_gallons = popup_analysis.get('expected_gallons')
                    if not expected_gallons and zone_id:
                        expected_gallons = self._calculate_expected_gallons(zone_id, run.duration_minutes)
                    
                    # Check if this exact run already exists
                    cursor.execute("""
                        SELECT zone_id, scheduled_duration_minutes, expected_gallons, 
                               raw_popup_text, parsed_summary
                        FROM scheduled_runs 
                        WHERE zone_id = ? AND schedule_date = ? AND scheduled_start_time = ?
                    """, (zone_id, collection_date, run.start_time))
                    
                    existing_run = cursor.fetchone()
                    
                    # New data to be stored
                    new_data = (
                        zone_id,
                        run.zone_name,
                        collection_date,
                        run.start_time,
                        popup_analysis.get('duration_minutes', run.duration_minutes),
                        expected_gallons,
                        run.notes or "",
                        popup_analysis.get('raw_popup_text'),
                        popup_analysis.get('popup_lines_json'),
                        popup_analysis.get('parsed_summary'),
                        popup_analysis.get('is_rain_cancelled', False),
                        popup_analysis.get('rain_sensor_status'),
                        popup_analysis.get('status'),
                        get_database_timestamp(),  # Houston time for created_at
                        get_database_timestamp()   # Houston time for scraped_at
                    )
                    
                    if existing_run is None:
                        # New run - insert
                        cursor.execute("""
                            INSERT INTO scheduled_runs 
                            (zone_id, zone_name, schedule_date, scheduled_start_time, 
                             scheduled_duration_minutes, expected_gallons, notes,
                             raw_popup_text, popup_lines_json, parsed_summary,
                             is_rain_cancelled, rain_sensor_status, popup_status,
                             created_at, scraped_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, new_data)
                        
                        counts['new'] += 1
                        logger.info(f"NEW scheduled run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')}")
                        
                    else:
                        # Run exists - check if data has changed
                        existing_zone_id, existing_duration, existing_gallons, existing_popup, existing_summary = existing_run
                        
                        new_duration = popup_analysis.get('duration_minutes', run.duration_minutes)
                        new_popup = popup_analysis.get('raw_popup_text')
                        new_summary = popup_analysis.get('parsed_summary')
                        
                        # Check if any important data has changed
                        data_changed = (
                            existing_duration != new_duration or
                            existing_gallons != expected_gallons or
                            existing_popup != new_popup or
                            existing_summary != new_summary
                        )
                        
                        if data_changed:
                            # Update existing run
                            cursor.execute("""
                                UPDATE scheduled_runs 
                                SET scheduled_duration_minutes=?, expected_gallons=?, notes=?,
                                    raw_popup_text=?, popup_lines_json=?, parsed_summary=?,
                                    is_rain_cancelled=?, rain_sensor_status=?, popup_status=?,
                                    scraped_at=?
                                WHERE zone_id=? AND schedule_date=? AND scheduled_start_time=?
                            """, (
                                new_duration, expected_gallons, run.notes or "",
                                new_popup, popup_analysis.get('popup_lines_json'),
                                new_summary, popup_analysis.get('is_rain_cancelled', False),
                                popup_analysis.get('rain_sensor_status'), popup_analysis.get('status'),
                                get_database_timestamp(),  # Updated scraped_at time
                                zone_id, collection_date, run.start_time
                            ))
                            
                            counts['updated'] += 1
                            logger.info(f"UPDATED scheduled run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')}")
                        else:
                            # No changes
                            counts['unchanged'] += 1
                            logger.debug(f"UNCHANGED scheduled run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')}")
                    
                except Exception as e:
                    logger.error(f"Failed to store scheduled run for {run.zone_name}: {e}")
                    
            conn.commit()
            
        logger.info(f"Stored scheduled runs for {collection_date}: {counts['new']} new, {counts['updated']} updated, {counts['unchanged']} unchanged")
        return counts
        
    def store_actual_runs_enhanced(self, actual_runs: List, collection_date: date = None) -> Dict[str, int]:
        """
        Store actual runs with enhanced popup data extraction
        
        Args:
            actual_runs: List of ActualRun objects with popup data
            collection_date: Date the runs occurred
            
        Returns:
            Dictionary with counts: {'new': int, 'updated': int, 'unchanged': int, 'total': int}
        """
        if collection_date is None:
            collection_date = date.today()
            
        counts = {'new': 0, 'updated': 0, 'unchanged': 0, 'total': len(actual_runs)}
        
        # Pre-process runs to identify any unknown zones and create them BEFORE the main transaction
        unknown_zones = []
        for run in actual_runs:
            zone_id = self._get_zone_id_cached(run.zone_name)
            if zone_id is None:
                unknown_zones.append(run.zone_name)
        
        # Create unknown zones outside the main transaction
        if unknown_zones:
            logger.info(f"Creating {len(unknown_zones)} unknown zones before processing runs")
            for zone_name in set(unknown_zones):  # Remove duplicates
                new_zone_id = self._create_unknown_zone(zone_name)
                self._zone_cache[zone_name] = new_zone_id
        
        # Now process all runs with cached zone IDs in batches to prevent long locks
        batch_size = 20  # Process in smaller batches to reduce lock time
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for i, run in enumerate(actual_runs):
                try:
                    zone_id = self._get_zone_id_cached(run.zone_name)
                    if zone_id is None:
                        logger.error(f"Zone ID still not found for {run.zone_name} after creation")
                        continue
                    
                    # Extract detailed popup data
                    popup_analysis = self._analyze_popup_data(run)
                    
                    # Calculate end time
                    end_time = run.start_time + timedelta(minutes=run.duration_minutes)
                    
                    # Check if this exact run already exists
                    cursor.execute("""
                        SELECT id, actual_gallons, actual_duration_minutes, status
                        FROM actual_runs 
                        WHERE zone_id = ? AND run_date = ? AND actual_start_time = ?
                    """, (zone_id, collection_date, run.start_time))
                    
                    existing_run = cursor.fetchone()
                    
                    if existing_run:
                        # Check if data has changed (compare key fields)
                        existing_gallons = existing_run[1] or 0.0
                        existing_duration = existing_run[2] or 0
                        existing_status = existing_run[3] or ""
                        
                        new_gallons = popup_analysis.get('actual_gallons', run.actual_gallons) or 0.0
                        new_duration = popup_analysis.get('duration_minutes', run.duration_minutes) or 0
                        new_status = popup_analysis.get('status', run.status) or ""
                        
                        # Compare with tolerance for floating point
                        gallons_changed = abs(existing_gallons - new_gallons) > 0.1
                        duration_changed = existing_duration != new_duration
                        status_changed = existing_status.strip() != new_status.strip()
                        
                        if gallons_changed or duration_changed or status_changed:
                            # Calculate updated water usage estimation data
                            expected_gallons = self.usage_estimator.calculate_expected_usage(zone_id, new_duration)
                            usage_type, usage_flag, reason = self.usage_estimator.determine_usage_type_and_flag(new_gallons, expected_gallons)
                            usage_value = self.usage_estimator.calculate_usage_value(usage_type, new_gallons, expected_gallons)
                            
                            # Update existing record with water usage estimation
                            cursor.execute("""
                                UPDATE actual_runs SET
                                    actual_duration_minutes = ?, actual_gallons = ?, status = ?,
                                    failure_reason = ?, end_time = ?, notes = ?,
                                    raw_popup_text = ?, popup_lines_json = ?, parsed_summary = ?,
                                    current_ma = ?, water_efficiency = ?, abort_reason = ?,
                                    usage_type = ?, usage = ?, usage_flag = ?, scraped_at = ?
                                WHERE id = ?
                            """, (
                                new_duration, new_gallons, new_status,
                                run.failure_reason, end_time, run.notes or "",
                                popup_analysis.get('raw_popup_text'),
                                popup_analysis.get('popup_lines_json'),
                                popup_analysis.get('parsed_summary'),
                                popup_analysis.get('current_ma'),
                                popup_analysis.get('water_efficiency'),
                                popup_analysis.get('abort_reason'),
                                usage_type, usage_value, usage_flag,
                                get_database_timestamp(),  # Update scraped_at
                                existing_run[0]  # id
                            ))
                            counts['updated'] += 1
                            logger.info(f"Updated actual run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')} - {new_gallons:.1f} gal ({usage_type})")
                        else:
                            # No changes, skip update
                            counts['unchanged'] += 1
                            logger.debug(f"Unchanged actual run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')}")
                    else:
                        # Calculate water usage estimation data
                        actual_gallons = popup_analysis.get('actual_gallons', run.actual_gallons)
                        duration_minutes = popup_analysis.get('duration_minutes', run.duration_minutes)
                        
                        # Get expected usage based on average flow rate
                        expected_gallons = self.usage_estimator.calculate_expected_usage(zone_id, duration_minutes)
                        
                        # Determine usage type, flag, and final usage value
                        usage_type, usage_flag, reason = self.usage_estimator.determine_usage_type_and_flag(actual_gallons, expected_gallons)
                        usage_value = self.usage_estimator.calculate_usage_value(usage_type, actual_gallons, expected_gallons)
                        
                        # Insert new record with water usage estimation
                        cursor.execute("""
                            INSERT INTO actual_runs 
                            (zone_id, zone_name, run_date, actual_start_time, actual_duration_minutes,
                             actual_gallons, status, failure_reason, end_time, notes,
                             raw_popup_text, popup_lines_json, parsed_summary, current_ma,
                             water_efficiency, abort_reason, usage_type, usage, usage_flag, created_at, scraped_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            zone_id,
                            run.zone_name,
                            collection_date,
                            run.start_time,
                            duration_minutes,
                            actual_gallons,
                            popup_analysis.get('status', run.status),
                            run.failure_reason,
                            end_time,
                            run.notes or "",
                            popup_analysis.get('raw_popup_text'),
                            popup_analysis.get('popup_lines_json'),
                            popup_analysis.get('parsed_summary'),
                            popup_analysis.get('current_ma'),
                            popup_analysis.get('water_efficiency'),
                            popup_analysis.get('abort_reason'),
                            usage_type,
                            usage_value,
                            usage_flag,
                            get_database_timestamp(),  # Houston time for created_at
                            get_database_timestamp()   # Houston time for scraped_at
                        ))
                        counts['new'] += 1
                        logger.info(f"Stored new actual run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')} - {actual_gallons:.1f} gal ({usage_type})")
                    
                except Exception as e:
                    logger.error(f"Failed to process actual run for {run.zone_name}: {e}")
                
                # Commit in batches to prevent long-running locks
                if (i + 1) % batch_size == 0:
                    conn.commit()
                    logger.debug(f"Committed batch {i + 1}/{len(actual_runs)} runs")
                    
            # Final commit for any remaining runs
            conn.commit()
            
        logger.info(f"Processed {counts['total']} actual runs for {collection_date}: {counts['new']} new, {counts['updated']} updated, {counts['unchanged']} unchanged")
        return counts
    
    def update_existing_runs_usage_estimation(self, target_date: str = None) -> Dict[str, Any]:
        """
        Update water usage estimation for existing runs that don't have usage_type set
        
        Args:
            target_date: Date in YYYY-MM-DD format (optional, processes all if None)
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Updating water usage estimation for existing runs...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build query based on whether target_date is specified
                where_clause = ""
                params = []
                if target_date:
                    where_clause = "AND run_date = ?"
                    params.append(target_date)
                
                # Get runs that need usage estimation
                cursor.execute(f"""
                    SELECT id, zone_id, zone_name, actual_duration_minutes, actual_gallons, run_date
                    FROM actual_runs 
                    WHERE (usage_type IS NULL OR usage IS NULL)
                    AND actual_duration_minutes > 0
                    {where_clause}
                    ORDER BY run_date DESC, zone_id, actual_start_time
                """, params)
                
                runs_to_update = cursor.fetchall()
                
            if not runs_to_update:
                return {
                    'success': True,
                    'message': 'No runs found that need usage estimation updates',
                    'total_runs': 0,
                    'updated_runs': 0
                }
            
            logger.info(f"Found {len(runs_to_update)} runs needing usage estimation updates")
            
            # Process each run
            updated_count = 0
            for run_id, zone_id, zone_name, duration_minutes, actual_gallons, run_date in runs_to_update:
                result = self.usage_estimator.update_run_usage_data(
                    run_id, zone_id, duration_minutes, actual_gallons
                )
                
                if result.get('success'):
                    updated_count += 1
                    logger.debug(f"Updated usage for {zone_name} on {run_date}: {result.get('usage_type')}")
                else:
                    logger.warning(f"Failed to update usage for run {run_id}: {result.get('error')}")
            
            logger.info(f"Successfully updated water usage estimation for {updated_count}/{len(runs_to_update)} runs")
            
            return {
                'success': True,
                'target_date': target_date,
                'total_runs': len(runs_to_update),
                'updated_runs': updated_count,
                'message': f'Updated {updated_count} runs with water usage estimation'
            }
            
        except Exception as e:
            logger.error(f"Failed to update existing runs usage estimation: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        
    def _analyze_popup_data(self, run_obj) -> Dict[str, Any]:
        """
        Analyze popup data from a run object and extract key information
        
        Args:
            run_obj: ScheduledRun or ActualRun object with popup data
            
        Returns:
            Dictionary with analyzed popup data
        """
        analysis = {
            'raw_popup_text': None,
            'popup_lines_json': None,
            'parsed_summary': None,
            'duration_minutes': getattr(run_obj, 'duration_minutes', 0),
            'actual_gallons': getattr(run_obj, 'actual_gallons', None),
            'expected_gallons': getattr(run_obj, 'expected_gallons', None),
            'current_ma': None,
            'status': getattr(run_obj, 'status', 'Unknown'),
            'is_rain_cancelled': False,
            'rain_sensor_status': None,
            'abort_reason': None,
            'water_efficiency': None
        }
        
        # Extract popup data if available
        if hasattr(run_obj, 'raw_popup_text'):
            analysis['raw_popup_text'] = run_obj.raw_popup_text
            
        if hasattr(run_obj, 'parsed_summary'):
            analysis['parsed_summary'] = run_obj.parsed_summary
            
        if hasattr(run_obj, 'popup_lines') and run_obj.popup_lines:
            analysis['popup_lines_json'] = json.dumps(run_obj.popup_lines)
            
            # Analyze each popup line for specific data
            for line_data in run_obj.popup_lines:
                line_type = line_data.get('type', '').lower()
                parsed_value = line_data.get('parsed_value')
                line_text = line_data.get('text', '').lower()
                
                # Extract specific data based on line type
                if line_type == 'duration' and parsed_value is not None:
                    analysis['duration_minutes'] = float(parsed_value)
                    
                elif line_type == 'water_usage' and parsed_value is not None:
                    if hasattr(run_obj, 'actual_gallons'):  # Actual run
                        analysis['actual_gallons'] = float(parsed_value)
                    else:  # Scheduled run
                        analysis['expected_gallons'] = float(parsed_value)
                        
                elif line_type == 'current' and parsed_value is not None:
                    analysis['current_ma'] = float(parsed_value)
                    
                elif line_type == 'status':
                    analysis['status'] = line_data.get('text', 'Unknown')
                    
                    # Check for rain cancellation indicators
                    if any(phrase in line_text for phrase in [
                        'not scheduled to run',
                        'aborted due to sensor input',
                        'aborted due to high daily rainfall',
                        'rain sensor'
                    ]):
                        analysis['is_rain_cancelled'] = True
                        analysis['rain_sensor_status'] = line_data.get('text')
                        
                        if 'aborted due to' in line_text:
                            analysis['abort_reason'] = line_data.get('text')
                            
                        # Set duration to 0 for cancelled runs
                        analysis['duration_minutes'] = 0
        
        # Calculate water efficiency if we have both expected and actual
        if (analysis.get('expected_gallons') and 
            analysis.get('actual_gallons') and 
            analysis['expected_gallons'] > 0):
            analysis['water_efficiency'] = (analysis['actual_gallons'] / analysis['expected_gallons']) * 100
            
        return analysis
        
    def _calculate_expected_gallons(self, zone_id: int, duration_minutes: float) -> Optional[float]:
        """Calculate expected gallons based on zone flow rate and duration"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT flow_rate_gpm FROM zones WHERE zone_id = ?", (zone_id,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    flow_rate_gpm = result[0]
                    return flow_rate_gpm * (duration_minutes / 60.0)
                    
        except Exception as e:
            logger.debug(f"Could not calculate expected gallons for zone {zone_id}: {e}")
            
        return None

def main():
    """Test intelligent data storage"""
    print("Testing Intelligent Data Storage")
    print("=" * 50)
    
    # Initialize enhanced storage
    storage = IntelligentDataStorage()
    
    print("Enhanced database manager initialized successfully!")
    print("Ready to store scheduled and actual runs with full popup analysis")

if __name__ == "__main__":
    main()
