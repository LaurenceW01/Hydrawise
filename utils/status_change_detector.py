#!/usr/bin/env python3
"""
Status Change Detection Module for Hydrawise Scheduled Runs

Detects changes in scheduled run popup status by comparing current runs
against the most recent recorded runs for each zone in the database.

Handles detection of:
- "Aborted due to high daily rainfall"
- "Aborted due to sensor input"  
- "Water cycle suspended"
- Restoration to "Normal watering cycle"

Author: AI Assistant
Date: 2025-08-26
"""

import logging
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass

from utils.timezone_utils import get_houston_now, get_database_timestamp
from hydrawise_web_scraper_refactored import ScheduledRun
from database.universal_database_manager import get_universal_database_manager

logger = logging.getLogger(__name__)

@dataclass
class StatusChange:
    """Represents a detected status change"""
    zone_id: int
    zone_name: str
    current_run_date: date
    current_scheduled_start_time: datetime
    current_status_type: str
    current_popup_text: str
    previous_run_date: date
    previous_scheduled_start_time: datetime
    previous_status_type: str
    previous_popup_text: str
    change_type: str
    irrigation_prevented: bool
    expected_gallons_lost: float
    change_detected_at: datetime
    time_since_last_record_hours: Optional[float]

class StatusChangeDetector:
    """
    Detects status changes in scheduled runs by comparing against database records
    
    Uses priority-based classification to avoid false positives from timing information
    that appears in all popup types (time, duration fields).
    """
    
    def __init__(self):
        """
        Initialize status change detector
        """
        self.logger = logger
    
    def classify_popup_status(self, popup_text: str) -> str:
        """
        Classify the status type based on popup text content
        Uses priority-based matching to avoid false positives
        
        Args:
            popup_text: Raw popup text from scheduled run
            
        Returns:
            Status type: rainfall_abort, sensor_abort, user_suspended, normal_cycle, etc.
        """
        if not popup_text:
            return "unknown"
        
        popup_lower = popup_text.lower()
        
        # Priority 1: Explicit abort/suspension messages (most specific first)
        if "aborted due to high daily rainfall" in popup_lower:
            return "rainfall_abort"
        elif "aborted due to sensor input" in popup_lower:
            return "sensor_abort"
        elif "water cycle suspended" in popup_lower:
            return "user_suspended"
        elif "not scheduled to run" in popup_lower:
            return "not_scheduled"
        
        # Priority 2: Explicit normal operation indicators
        elif "normal watering cycle" in popup_lower:
            return "normal_cycle"
        
        # Priority 3: Look for other status indicators
        elif "aborted" in popup_lower or "cancelled" in popup_lower:
            return "other_abort"  # Catch other abort types we haven't seen yet
        elif "suspended" in popup_lower or "paused" in popup_lower:
            return "other_suspended"  # Catch other suspension types
        
        # Priority 4: If we see scheduling info WITHOUT abort/suspend keywords, assume normal
        elif ("time:" in popup_lower and "duration:" in popup_lower and 
              not any(keyword in popup_lower for keyword in ["aborted", "suspended", "cancelled", "not scheduled"])):
            return "normal_cycle"
        
        # Default: Unknown status
        else:
            return "unknown"
    
    def classify_status_change(self, prev_type: str, curr_type: str) -> str:
        """
        Classify the type of status change that occurred
        
        Args:
            prev_type: Previous status type
            curr_type: Current status type
            
        Returns:
            Change type: rainfall_abort, sensor_abort, user_suspended, normal_restored, etc.
        """
        if prev_type == curr_type:
            return "no_change"
        
        # Changes TO problem states
        elif curr_type == "rainfall_abort":
            return "rainfall_abort"
        elif curr_type == "sensor_abort":
            return "sensor_abort" 
        elif curr_type == "user_suspended":
            return "user_suspended"
        elif curr_type in ["not_scheduled", "other_abort", "other_suspended"]:
            return "irrigation_prevented"
        
        # Changes FROM problem states TO normal
        elif (prev_type in ["rainfall_abort", "sensor_abort", "user_suspended", "not_scheduled", "other_abort", "other_suspended"] 
              and curr_type == "normal_cycle"):
            return "normal_restored"
        
        # Other changes
        else:
            return "other_change"
    
    def prevents_irrigation(self, status_type: str) -> bool:
        """
        Determine if this status type prevents irrigation
        
        Args:
            status_type: Status type to check
            
        Returns:
            True if this status prevents irrigation
        """
        preventing_statuses = [
            "rainfall_abort", 
            "sensor_abort", 
            "user_suspended", 
            "not_scheduled",
            "other_abort",
            "other_suspended"
        ]
        return status_type in preventing_statuses
    
    def get_most_recent_scheduled_run_for_zone(self, zone_id: int, exclude_current_run: ScheduledRun = None) -> Optional[ScheduledRun]:
        """
        Get the most recent scheduled run recorded for a specific zone BEFORE the current run's date
        
        CRITICAL FIX: Now filters by schedule_date < current_run.schedule_date to ensure
        we only compare against truly PREVIOUS runs, not future runs that happen to have
        later scraped_at timestamps.
        
        Args:
            zone_id: The zone to look up
            exclude_current_run: Current run to exclude from search (REQUIRED for status change detection)
            
        Returns:
            Most recent PREVIOUS ScheduledRun object or None if no previous runs exist
        """
        try:
            db_manager = get_universal_database_manager()
            
            # Get most recent scheduled run for this zone
            # If exclude_current_run is provided, find the most recent run that doesn't match
            if exclude_current_run:
                # Build exclusion criteria based on the current run's properties
                exclusion_criteria = []
                exclusion_params = [zone_id]
                
                if hasattr(exclude_current_run, 'schedule_date') and exclude_current_run.schedule_date:
                    exclusion_criteria.append("schedule_date != %s")
                    exclusion_params.append(exclude_current_run.schedule_date.isoformat() if hasattr(exclude_current_run.schedule_date, 'isoformat') else str(exclude_current_run.schedule_date))
                
                if hasattr(exclude_current_run, 'start_time') and exclude_current_run.start_time:
                    exclusion_criteria.append("scheduled_start_time != %s")
                    exclusion_params.append(exclude_current_run.start_time)
                
                exclusion_clause = " AND " + " AND ".join(exclusion_criteria) if exclusion_criteria else ""
                
                results = db_manager.adapter.execute_query(f"""
                    SELECT 
                        id, zone_id, zone_name, schedule_date, scheduled_start_time,
                        scheduled_duration_minutes, expected_gallons, program_name,
                        notes, raw_popup_text, popup_lines_json, parsed_summary,
                        is_rain_cancelled, rain_sensor_status, popup_status,
                        scraped_at, created_at
                    FROM scheduled_runs 
                    WHERE zone_id = %s{exclusion_clause}
                    AND schedule_date < %s
                    ORDER BY scraped_at DESC, scheduled_start_time DESC
                    LIMIT 1
                """, exclusion_params + [exclude_current_run.schedule_date.isoformat()])
            else:
                # Get most recent run (no exclusions) - should not be used for status change detection
                # This branch is kept for compatibility but should not be called for status changes
                results = db_manager.adapter.execute_query("""
                    SELECT 
                        id, zone_id, zone_name, schedule_date, scheduled_start_time,
                        scheduled_duration_minutes, expected_gallons, program_name,
                        notes, raw_popup_text, popup_lines_json, parsed_summary,
                        is_rain_cancelled, rain_sensor_status, popup_status,
                        scraped_at, created_at
                    FROM scheduled_runs 
                    WHERE zone_id = %s
                    ORDER BY scraped_at DESC, scheduled_start_time DESC
                    LIMIT 1
                """, (zone_id,))
            
            if results:
                row = results[0]
                # Convert row to ScheduledRun object with correct parameters
                # Handle datetime parsing - could be string or datetime object
                start_time = row['scheduled_start_time']
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time)
                
                run = ScheduledRun(
                    zone_id=str(row['zone_id']),
                    zone_name=row['zone_name'],
                    start_time=start_time,
                    duration_minutes=row['scheduled_duration_minutes'],
                    expected_gallons=row['expected_gallons'],
                    notes=row['notes'] or ""
                )
                
                # Add additional attributes
                # Handle schedule_date parsing - could be string or date object
                schedule_date = row['schedule_date']
                if isinstance(schedule_date, str):
                    run.schedule_date = datetime.fromisoformat(schedule_date).date()
                else:
                    run.schedule_date = schedule_date
                    
                run.program_name = row['program_name']
                run.raw_popup_text = row['raw_popup_text']
                run.popup_lines_json = row['popup_lines_json']
                run.parsed_summary = row['parsed_summary']
                run.is_rain_cancelled = bool(row['is_rain_cancelled']) if row['is_rain_cancelled'] is not None else False
                run.rain_sensor_status = row['rain_sensor_status']
                run.popup_status = row['popup_status']
                
                return run
            return None
                
        except Exception as e:
            self.logger.error(f"Error getting most recent run for zone {zone_id}: {e}")
            return None
    
    def detect_status_change(self, previous_run: ScheduledRun, current_run: ScheduledRun) -> Optional[StatusChange]:
        """
        Compare most recent recorded run with current run to detect status changes
        
        Args:
            previous_run: Most recent run from database
            current_run: Current run from web scraping
            
        Returns:
            StatusChange object if change detected, None otherwise
        """
        # CRITICAL FIX: First check if popup text is essentially identical
        # This prevents false positives from identical data being classified differently
        prev_popup = (previous_run.raw_popup_text or "").strip()
        curr_popup = (current_run.raw_popup_text or "").strip()
        
        # If popup text is identical, no change occurred
        if prev_popup == curr_popup:
            self.logger.debug(f"Zone {current_run.zone_name}: No change - identical popup text")
            return None
        
        # Extract status indicators from popup text
        prev_status_type = self.classify_popup_status(prev_popup)
        curr_status_type = self.classify_popup_status(curr_popup)
        
        # Log the classification for debugging
        self.logger.debug(f"Zone {current_run.zone_name}: {prev_status_type} → {curr_status_type}")
        self.logger.debug(f"  Previous popup: {prev_popup}")
        self.logger.debug(f"  Current popup: {curr_popup}")
        
        # CRITICAL FIX: Only detect change if BOTH popup text AND status classification changed
        # This prevents false positives from minor text variations that don't affect status
        if prev_status_type != curr_status_type and prev_popup != curr_popup:
            
            # Calculate time since last record
            time_since_last = None
            if hasattr(previous_run, 'scraped_at') and previous_run.scraped_at:
                try:
                    if isinstance(previous_run.scraped_at, str):
                        prev_scraped = datetime.fromisoformat(previous_run.scraped_at)
                    else:
                        prev_scraped = previous_run.scraped_at
                    time_since_last = (get_houston_now() - prev_scraped).total_seconds() / 3600
                except Exception as e:
                    self.logger.debug(f"Error calculating time since last record: {e}")
            
            # Log the detected change
            self.logger.info(f"STATUS CHANGE DETECTED - {current_run.zone_name}: {prev_status_type} → {curr_status_type}")
            
            change_type = self.classify_status_change(prev_status_type, curr_status_type)
            irrigation_prevented = self.prevents_irrigation(curr_status_type)
            expected_gallons_lost = current_run.expected_gallons if irrigation_prevented else 0
            
            return StatusChange(
                zone_id=current_run.zone_id,
                zone_name=current_run.zone_name,
                current_run_date=current_run.schedule_date,
                current_scheduled_start_time=current_run.start_time,
                current_status_type=curr_status_type,
                current_popup_text=current_run.raw_popup_text or "",
                previous_run_date=previous_run.schedule_date,
                previous_scheduled_start_time=previous_run.start_time,
                previous_status_type=prev_status_type,
                previous_popup_text=previous_run.raw_popup_text or "",
                change_type=change_type,
                irrigation_prevented=irrigation_prevented,
                expected_gallons_lost=expected_gallons_lost or 0,
                change_detected_at=get_houston_now(),
                time_since_last_record_hours=time_since_last
            )
        
        # No change detected
        self.logger.debug(f"No status change for {current_run.zone_name}")
        return None
    
    def detect_changes_for_collection(self, current_runs: List[ScheduledRun], collection_date: date) -> List[StatusChange]:
        """
        Detect status changes by comparing each current run against the most recent 
        recorded run for that zone (regardless of date/time)
        
        Args:
            current_runs: List of current scheduled runs from web scraping
            collection_date: Date of the collection
            
        Returns:
            List of detected status changes
        """
        status_changes = []
        processed_zones = set()  # Track zones already processed to prevent duplicates
        
        for current_run in current_runs:
            try:
                # CRITICAL FIX: Prevent duplicate processing of same zone in one collection run
                zone_key = f"{current_run.zone_id}_{current_run.start_time}"
                if zone_key in processed_zones:
                    self.logger.debug(f"Skipping duplicate zone {current_run.zone_name} for same start time")
                    continue
                processed_zones.add(zone_key)
                
                # Get the most recent scheduled run for this zone from database (excluding current run)
                most_recent_run = self.get_most_recent_scheduled_run_for_zone(
                    current_run.zone_id, 
                    exclude_current_run=current_run
                )
                
                if most_recent_run:
                    # CRITICAL FIX: Check if we already recorded this exact change today
                    if self._is_duplicate_change_today(current_run, most_recent_run, collection_date):
                        self.logger.debug(f"Skipping duplicate change for {current_run.zone_name} - already recorded today")
                        continue
                        
                    change = self.detect_status_change(most_recent_run, current_run)
                    if change:
                        status_changes.append(change)
                else:
                    # No previous run exists - this is the first time we've seen this zone
                    self.logger.info(f"First scheduled run recorded for zone {current_run.zone_name}")
                    
            except Exception as e:
                self.logger.error(f"Error detecting status change for zone {current_run.zone_name}: {e}")
                continue
        
        return status_changes
    
    def _is_duplicate_change_today(self, current_run: ScheduledRun, previous_run: ScheduledRun, collection_date: date) -> bool:
        """
        Check if this current run has already been processed for status changes
        
        FIXED: Now checks if the same current run has been processed, regardless of which
        previous run it was compared against. This prevents multiple automated collection
        runs from creating duplicate records for the same current scheduled run.
        
        Args:
            current_run: Current scheduled run
            previous_run: Previous scheduled run for comparison (used for logging only)
            collection_date: Date of current collection
            
        Returns:
            True if this current run was already processed for status changes
        """
        try:
            db_manager = get_universal_database_manager()
            
            # FIXED: Check if we already processed this current run for status changes
            # Focus on the current run being processed, not the previous run comparison
            results = db_manager.adapter.execute_query("""
                SELECT COUNT(*) as count
                FROM scheduled_run_status_changes 
                WHERE zone_id = %s 
                    AND current_run_date = %s
                    AND current_scheduled_start_time = %s
            """, (
                current_run.zone_id,
                current_run.schedule_date.isoformat(),
                current_run.start_time.isoformat()
            ))
            
            count = results[0]['count'] if results else 0
            
            if count > 0:
                self.logger.debug(f"Current run already processed: {current_run.zone_name} {current_run.schedule_date} {current_run.start_time}")
            
            return count > 0
                
        except Exception as e:
            self.logger.error(f"Error checking for duplicate change: {e}")
            return False  # If error, allow the change to prevent missing real changes
    
    def store_status_changes(self, status_changes: List[StatusChange], collection_run_id: str = None) -> bool:
        """
        Store detected status changes in the database
        
        Args:
            status_changes: List of status changes to store
            collection_run_id: Identifier for the collection run that detected these changes
            
        Returns:
            True if all changes stored successfully, False otherwise
        """
        if not status_changes:
            return True
        
        try:
            db_manager = get_universal_database_manager()
            
            for change in status_changes:
                db_manager.adapter.execute_insert("""
                    INSERT INTO scheduled_run_status_changes (
                        zone_id, zone_name, change_detected_date, change_detected_time,
                        collection_run_id, current_run_date, current_scheduled_start_time,
                        current_status_type, current_popup_text, previous_run_date,
                        previous_scheduled_start_time, previous_status_type, previous_popup_text,
                        change_type, irrigation_prevented, expected_gallons_lost,
                        time_since_last_record_hours, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    change.zone_id,
                    change.zone_name,
                    change.change_detected_at.date().isoformat(),
                    change.change_detected_at.strftime('%Y-%m-%d %H:%M:%S'),  # PostgreSQL-friendly timestamp
                    collection_run_id,
                    change.current_run_date.isoformat(),
                    change.current_scheduled_start_time.strftime('%Y-%m-%d %H:%M:%S'),  # PostgreSQL-friendly timestamp
                    change.current_status_type,
                    change.current_popup_text,
                    change.previous_run_date.isoformat(),
                    change.previous_scheduled_start_time.strftime('%Y-%m-%d %H:%M:%S'),  # PostgreSQL-friendly timestamp
                    change.previous_status_type,
                    change.previous_popup_text,
                    change.change_type,
                    change.irrigation_prevented,
                    change.expected_gallons_lost,
                    change.time_since_last_record_hours,
                    change.change_detected_at.strftime('%Y-%m-%d %H:%M:%S')  # PostgreSQL-friendly timestamp
                ))
            
            self.logger.info(f"Stored {len(status_changes)} status changes in database")
            return True
                
        except Exception as e:
            self.logger.error(f"Error storing status changes: {e}")
            return False
    
    def get_status_changes_for_date(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Get all status changes for a specific date
        
        Args:
            target_date: Date to get changes for
            
        Returns:
            List of status changes as dictionaries
        """
        try:
            db_manager = get_universal_database_manager()
            
            results = db_manager.adapter.execute_query("""
                SELECT 
                    zone_id, zone_name, change_detected_time, current_run_date,
                    current_scheduled_start_time, current_status_type, current_popup_text,
                    previous_run_date, previous_scheduled_start_time, previous_status_type,
                    previous_popup_text, change_type, irrigation_prevented,
                    expected_gallons_lost, time_since_last_record_hours
                FROM scheduled_run_status_changes 
                WHERE change_detected_date = %s
                ORDER BY change_detected_time
            """, (target_date.isoformat(),))
            
            changes = []
            for row in results:
                changes.append({
                    'zone_id': row['zone_id'],
                    'zone_name': row['zone_name'],
                    'change_detected_time': datetime.fromisoformat(row['change_detected_time']) if row['change_detected_time'] else None,
                    'current_run_date': datetime.fromisoformat(row['current_run_date']).date() if row['current_run_date'] else None,
                    'current_scheduled_start_time': datetime.fromisoformat(row['current_scheduled_start_time']) if row['current_scheduled_start_time'] else None,
                    'current_status_type': row['current_status_type'],
                    'current_popup_text': row['current_popup_text'],
                    'previous_run_date': datetime.fromisoformat(row['previous_run_date']).date() if row['previous_run_date'] else None,
                    'previous_scheduled_start_time': datetime.fromisoformat(row['previous_scheduled_start_time']) if row['previous_scheduled_start_time'] else None,
                    'previous_status_type': row['previous_status_type'],
                    'previous_popup_text': row['previous_popup_text'],
                    'change_type': row['change_type'],
                    'irrigation_prevented': bool(row['irrigation_prevented']),
                    'expected_gallons_lost': row['expected_gallons_lost'] or 0,
                    'time_since_last_record_hours': row['time_since_last_record_hours']
                })
            
            return changes
                
        except Exception as e:
            self.logger.error(f"Error getting status changes for {target_date}: {e}")
            return []
