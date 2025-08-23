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
from utils.timezone_utils import get_database_timestamp, to_houston_time

logger = logging.getLogger(__name__)

class IntelligentDataStorage(DatabaseManager):
    """Enhanced database manager with intelligent data storage capabilities"""
    
    def store_scheduled_runs_enhanced(self, scheduled_runs: List, collection_date: date = None) -> int:
        """
        Store scheduled runs with enhanced popup data extraction
        
        Args:
            scheduled_runs: List of ScheduledRun objects with popup data
            collection_date: Date the schedule was collected for
            
        Returns:
            Number of runs successfully stored
        """
        if collection_date is None:
            collection_date = date.today()
            
        stored_count = 0
        
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
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO scheduled_runs 
                        (zone_id, zone_name, schedule_date, scheduled_start_time, 
                         scheduled_duration_minutes, expected_gallons, notes,
                         raw_popup_text, popup_lines_json, parsed_summary,
                         is_rain_cancelled, rain_sensor_status, popup_status,
                         created_at, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
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
                    ))
                    
                    stored_count += 1
                    logger.info(f"Stored scheduled run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')}")
                    
                except Exception as e:
                    logger.error(f"Failed to store scheduled run for {run.zone_name}: {e}")
                    
            conn.commit()
            
        logger.info(f"Stored {stored_count}/{len(scheduled_runs)} scheduled runs for {collection_date}")
        return stored_count
        
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
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for run in actual_runs:
                try:
                    zone_id = self.get_zone_id_by_name(run.zone_name)
                    
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
                            # Update existing record
                            cursor.execute("""
                                UPDATE actual_runs SET
                                    actual_duration_minutes = ?, actual_gallons = ?, status = ?,
                                    failure_reason = ?, end_time = ?, notes = ?,
                                    raw_popup_text = ?, popup_lines_json = ?, parsed_summary = ?,
                                    current_ma = ?, water_efficiency = ?, abort_reason = ?,
                                    scraped_at = ?
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
                                get_database_timestamp(),  # Update scraped_at
                                existing_run[0]  # id
                            ))
                            counts['updated'] += 1
                            logger.info(f"Updated actual run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')} - {new_gallons:.1f} gal")
                        else:
                            # No changes, skip update
                            counts['unchanged'] += 1
                            logger.debug(f"Unchanged actual run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')}")
                    else:
                        # Insert new record
                        cursor.execute("""
                            INSERT INTO actual_runs 
                            (zone_id, zone_name, run_date, actual_start_time, actual_duration_minutes,
                             actual_gallons, status, failure_reason, end_time, notes,
                             raw_popup_text, popup_lines_json, parsed_summary, current_ma,
                             water_efficiency, abort_reason, created_at, scraped_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            zone_id,
                            run.zone_name,
                            collection_date,
                            run.start_time,
                            popup_analysis.get('duration_minutes', run.duration_minutes),
                            popup_analysis.get('actual_gallons', run.actual_gallons),
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
                            get_database_timestamp(),  # Houston time for created_at
                            get_database_timestamp()   # Houston time for scraped_at
                        ))
                        counts['new'] += 1
                        logger.info(f"Stored new actual run: {run.zone_name} at {run.start_time.strftime('%I:%M %p')} - {popup_analysis.get('actual_gallons', 0):.1f} gal")
                    
                except Exception as e:
                    logger.error(f"Failed to process actual run for {run.zone_name}: {e}")
                    
            conn.commit()
            
        logger.info(f"Processed {counts['total']} actual runs for {collection_date}: {counts['new']} new, {counts['updated']} updated, {counts['unchanged']} unchanged")
        return counts
        
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
                    analysis['duration_minutes'] = int(parsed_value)
                    
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
        
    def _calculate_expected_gallons(self, zone_id: int, duration_minutes: int) -> Optional[float]:
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
