#!/usr/bin/env python3
"""
Irrigation Schedule vs Actual Matching Algorithm

Matches scheduled irrigation runs with actual reported runs to identify:
- Perfect matches (scheduled run has corresponding actual run)
- Missing runs (scheduled but no actual run found)
- Unexpected runs (actual run with no scheduled match)
- Timing discrepancies (matches with significant time differences)

Author: AI Assistant
Date: August 22, 2025
"""

import sqlite3
import json
import sys
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.timezone_utils import get_houston_now, to_houston_time, HOUSTON_TZ

class MatchType(Enum):
    """Types of matches between scheduled and actual runs"""
    PERFECT_MATCH = "perfect_match"           # Exact zone and time match
    TIME_VARIANCE = "time_variance"           # Same zone, slight time difference
    MISSING_RUN = "missing_run"               # Scheduled but no actual run (past time only)
    UNEXPECTED_RUN = "unexpected_run"         # Actual run with no schedule
    RAIN_CANCELLED = "rain_cancelled"         # Legitimately cancelled due to rain
    FUTURE_SCHEDULED = "future_scheduled"     # Scheduled for future (not yet due)

@dataclass
class MatchResult:
    """Result of matching a scheduled run with actual runs"""
    scheduled_run_id: Optional[int]
    actual_run_id: Optional[int]
    zone_name: str
    scheduled_time: Optional[datetime]
    actual_time: Optional[datetime]
    match_type: MatchType
    time_difference_minutes: Optional[int]
    confidence_score: float  # 0.0 to 1.0
    notes: str
    alert_priority: str  # HIGH, MEDIUM, LOW, NONE

@dataclass
class ScheduledRun:
    """Scheduled irrigation run data"""
    id: int
    zone_name: str
    scheduled_start_time: datetime
    scheduled_duration_minutes: int
    expected_gallons: Optional[float]
    is_rain_cancelled: bool
    rain_sensor_status: Optional[str]
    popup_status: Optional[str]

@dataclass
class ActualRun:
    """Actual irrigation run data"""
    id: int
    zone_name: str
    start_time: datetime
    duration_minutes: int
    actual_gallons: Optional[float]
    status: str
    failure_reason: Optional[str]
    water_efficiency: Optional[float]

class IrrigationMatcher:
    """
    Intelligent irrigation matching system that compares scheduled vs actual runs
    """
    
    def __init__(self, db_path: str = "database/irrigation_data.db", time_tolerance_minutes: int = 30):
        """
        Initialize the matcher
        
        Args:
            db_path: Path to SQLite database
            time_tolerance_minutes: Maximum time difference for a valid match
        """
        self.db_path = db_path
        self.time_tolerance_minutes = time_tolerance_minutes
        
    def load_scheduled_runs(self, target_date: date) -> List[ScheduledRun]:
        """Load scheduled runs for a specific date"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, zone_name, scheduled_start_time, scheduled_duration_minutes,
                       expected_gallons, is_rain_cancelled, rain_sensor_status, popup_status
                FROM scheduled_runs 
                WHERE schedule_date = ?
                ORDER BY scheduled_start_time
            """, (target_date,))
            
            runs = []
            for row in cursor.fetchall():
                runs.append(ScheduledRun(
                    id=row['id'],
                    zone_name=row['zone_name'],
                    scheduled_start_time=datetime.fromisoformat(row['scheduled_start_time']),
                    scheduled_duration_minutes=row['scheduled_duration_minutes'],
                    expected_gallons=row['expected_gallons'],
                    is_rain_cancelled=bool(row['is_rain_cancelled']),
                    rain_sensor_status=row['rain_sensor_status'],
                    popup_status=row['popup_status']
                ))
            
            return runs
    
    def load_actual_runs(self, target_date: date) -> List[ActualRun]:
        """Load actual runs for a specific date"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, zone_name, actual_start_time, actual_duration_minutes,
                       actual_gallons, status, failure_reason, water_efficiency
                FROM actual_runs 
                WHERE run_date = ?
                ORDER BY actual_start_time
            """, (target_date,))
            
            runs = []
            for row in cursor.fetchall():
                runs.append(ActualRun(
                    id=row['id'],
                    zone_name=row['zone_name'],
                    start_time=datetime.fromisoformat(row['actual_start_time']),
                    duration_minutes=row['actual_duration_minutes'],
                    actual_gallons=row['actual_gallons'],
                    status=row['status'],
                    failure_reason=row['failure_reason'],
                    water_efficiency=row['water_efficiency']
                ))
            
            return runs
    
    def normalize_zone_name(self, zone_name: str) -> str:
        """Normalize zone name for consistent matching"""
        # Remove common variations and normalize
        normalized = zone_name.strip().lower()
        
        # Handle common abbreviations and variations
        replacements = {
            '(mp)': '(mp)',
            '(m)': '(m)',
            '(m/d)': '(m/d)',
            'pots, baskets & planters': 'pots, baskets and planters',
            'bed/planters': 'bed and planters',
            '&': 'and'
        }
        
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
            
        return normalized
    
    def calculate_time_difference(self, scheduled: datetime, actual: datetime) -> int:
        """Calculate time difference in minutes"""
        return abs((actual - scheduled).total_seconds() / 60)
    
    def find_best_match(self, scheduled_run: ScheduledRun, actual_runs: List[ActualRun]) -> Tuple[Optional[ActualRun], float, int]:
        """
        Find the best matching actual run for a scheduled run
        
        Returns:
            Tuple of (best_match, confidence_score, time_difference_minutes)
        """
        if not actual_runs:
            return None, 0.0, 0
            
        best_match = None
        best_confidence = 0.0
        best_time_diff = float('inf')
        
        scheduled_zone_norm = self.normalize_zone_name(scheduled_run.zone_name)
        
        for actual_run in actual_runs:
            actual_zone_norm = self.normalize_zone_name(actual_run.zone_name)
            
            # Zone name matching
            if scheduled_zone_norm != actual_zone_norm:
                continue
                
            # Time difference calculation
            time_diff = self.calculate_time_difference(
                scheduled_run.scheduled_start_time, 
                actual_run.start_time
            )
            
            # Skip if outside tolerance
            if time_diff > self.time_tolerance_minutes:
                continue
                
            # Calculate confidence score
            confidence = self.calculate_confidence_score(scheduled_run, actual_run, time_diff)
            
            # Update best match if this is better
            if confidence > best_confidence or (confidence == best_confidence and time_diff < best_time_diff):
                best_match = actual_run
                best_confidence = confidence
                best_time_diff = time_diff
        
        return best_match, best_confidence, int(best_time_diff) if best_time_diff != float('inf') else 0
    
    def calculate_confidence_score(self, scheduled: ScheduledRun, actual: ActualRun, time_diff: float) -> float:
        """
        Calculate confidence score for a potential match
        
        Factors:
        - Zone name similarity (must be exact for consideration)
        - Time proximity (closer = higher confidence)
        - Duration similarity
        - Water usage vs expected
        """
        confidence = 1.0
        
        # Time penalty (0 minutes = 1.0, tolerance limit = 0.5)
        time_factor = max(0.5, 1.0 - (time_diff / self.time_tolerance_minutes) * 0.5)
        confidence *= time_factor
        
        # Duration similarity bonus
        if scheduled.scheduled_duration_minutes > 0:
            duration_ratio = min(actual.duration_minutes, scheduled.scheduled_duration_minutes) / \
                           max(actual.duration_minutes, scheduled.scheduled_duration_minutes)
            duration_factor = 0.8 + (duration_ratio * 0.2)  # 0.8 to 1.0
            confidence *= duration_factor
        
        # Water efficiency factor (if available)
        if actual.water_efficiency is not None:
            # Penalize very low or very high efficiency
            if 70 <= actual.water_efficiency <= 120:  # Normal range
                efficiency_factor = 1.0
            elif 50 <= actual.water_efficiency < 70 or 120 < actual.water_efficiency <= 150:
                efficiency_factor = 0.9
            else:
                efficiency_factor = 0.8
            confidence *= efficiency_factor
        
        return min(1.0, confidence)
    
    def determine_alert_priority(self, match_result: MatchResult, scheduled_run: Optional[ScheduledRun]) -> str:
        """Determine alert priority based on match type and zone characteristics"""
        
        if match_result.match_type == MatchType.RAIN_CANCELLED:
            return "NONE"  # No alert needed for legitimate rain cancellations
            
        if match_result.match_type == MatchType.PERFECT_MATCH:
            return "NONE"  # No alert needed for perfect matches
            
        if match_result.match_type == MatchType.TIME_VARIANCE and match_result.confidence_score >= 0.8:
            return "LOW"   # Minor timing issue
            
        # Check zone type for priority assessment
        zone_lower = match_result.zone_name.lower()
        
        if any(plant_type in zone_lower for plant_type in ['planter', 'bed', 'pot', 'basket']):
            priority = "HIGH"  # Plants in containers dry out quickly
        elif 'pool' in zone_lower:
            priority = "MEDIUM"  # Pool area plants
        elif 'turf' in zone_lower or 'lawn' in zone_lower:
            priority = "LOW"   # Turf is more resilient
        else:
            priority = "MEDIUM"  # Default for unknown zone types
            
        return priority
    
    def match_runs(self, target_date: date) -> List[MatchResult]:
        """
        Match scheduled and actual runs for a given date
        
        Returns list of MatchResult objects
        """
        scheduled_runs = self.load_scheduled_runs(target_date)
        actual_runs = self.load_actual_runs(target_date)
        
        results = []
        used_actual_runs = set()
        
        # Get current Houston time for comparison
        current_houston_time = get_houston_now()
        
        # Process each scheduled run
        for scheduled_run in scheduled_runs:
            # Handle rain-cancelled runs separately
            if scheduled_run.is_rain_cancelled:
                result = MatchResult(
                    scheduled_run_id=scheduled_run.id,
                    actual_run_id=None,
                    zone_name=scheduled_run.zone_name,
                    scheduled_time=scheduled_run.scheduled_start_time,
                    actual_time=None,
                    match_type=MatchType.RAIN_CANCELLED,
                    time_difference_minutes=None,
                    confidence_score=1.0,
                    notes=f"Legitimately cancelled: {scheduled_run.rain_sensor_status or 'Rain detected'}",
                    alert_priority="NONE"
                )
                results.append(result)
                continue
            
            # Check if scheduled run is in the future (not yet due)
            # Database times are stored as Houston local time but naive
            # We need to localize them to Houston timezone, not convert from another timezone
            if scheduled_run.scheduled_start_time.tzinfo is None:
                # Localize naive datetime as Houston time (don't convert from UTC)
                scheduled_houston_time = HOUSTON_TZ.localize(scheduled_run.scheduled_start_time)
            else:
                scheduled_houston_time = scheduled_run.scheduled_start_time
            
            scheduled_time_with_buffer = scheduled_houston_time + timedelta(minutes=10)
            if scheduled_time_with_buffer > current_houston_time:
                result = MatchResult(
                    scheduled_run_id=scheduled_run.id,
                    actual_run_id=None,
                    zone_name=scheduled_run.zone_name,
                    scheduled_time=scheduled_run.scheduled_start_time,
                    actual_time=None,
                    match_type=MatchType.FUTURE_SCHEDULED,
                    time_difference_minutes=None,
                    confidence_score=1.0,
                    notes=f"Scheduled for future - not yet due (current time: {current_houston_time.strftime('%I:%M %p')})",
                    alert_priority="NONE"
                )
                results.append(result)
                continue
            
            # Find available actual runs (not yet matched)
            available_actual = [run for run in actual_runs if run.id not in used_actual_runs]
            
            # Find best match
            best_match, confidence, time_diff = self.find_best_match(scheduled_run, available_actual)
            
            if best_match:
                # Mark actual run as used
                used_actual_runs.add(best_match.id)
                
                # Determine match type
                if confidence >= 0.9 and time_diff <= 5:
                    match_type = MatchType.PERFECT_MATCH
                    notes = f"Excellent match (confidence: {confidence:.2f})"
                elif confidence >= 0.7:
                    match_type = MatchType.TIME_VARIANCE
                    notes = f"Good match with {time_diff}min time difference (confidence: {confidence:.2f})"
                else:
                    match_type = MatchType.TIME_VARIANCE
                    notes = f"Marginal match with {time_diff}min difference (confidence: {confidence:.2f})"
                
                result = MatchResult(
                    scheduled_run_id=scheduled_run.id,
                    actual_run_id=best_match.id,
                    zone_name=scheduled_run.zone_name,
                    scheduled_time=scheduled_run.scheduled_start_time,
                    actual_time=best_match.start_time,
                    match_type=match_type,
                    time_difference_minutes=time_diff,
                    confidence_score=confidence,
                    notes=notes,
                    alert_priority="NONE"  # Will be set below
                )
                result.alert_priority = self.determine_alert_priority(result, scheduled_run)
            else:
                # No match found - missing run
                result = MatchResult(
                    scheduled_run_id=scheduled_run.id,
                    actual_run_id=None,
                    zone_name=scheduled_run.zone_name,
                    scheduled_time=scheduled_run.scheduled_start_time,
                    actual_time=None,
                    match_type=MatchType.MISSING_RUN,
                    time_difference_minutes=None,
                    confidence_score=0.0,
                    notes="No matching actual run found within time tolerance",
                    alert_priority="NONE"  # Will be set below
                )
                result.alert_priority = self.determine_alert_priority(result, scheduled_run)
            
            results.append(result)
        
        # Process unmatched actual runs (unexpected runs)
        for actual_run in actual_runs:
            if actual_run.id not in used_actual_runs:
                result = MatchResult(
                    scheduled_run_id=None,
                    actual_run_id=actual_run.id,
                    zone_name=actual_run.zone_name,
                    scheduled_time=None,
                    actual_time=actual_run.start_time,
                    match_type=MatchType.UNEXPECTED_RUN,
                    time_difference_minutes=None,
                    confidence_score=0.0,
                    notes="Actual run with no corresponding scheduled run",
                    alert_priority="MEDIUM"  # Unexpected runs warrant investigation
                )
                results.append(result)
        
        return results
    
    def generate_match_report(self, target_date: date) -> str:
        """Generate a comprehensive matching report"""
        matches = self.match_runs(target_date)
        
        # Categorize results
        perfect_matches = [m for m in matches if m.match_type == MatchType.PERFECT_MATCH]
        time_variance = [m for m in matches if m.match_type == MatchType.TIME_VARIANCE]
        missing_runs = [m for m in matches if m.match_type == MatchType.MISSING_RUN]
        unexpected_runs = [m for m in matches if m.match_type == MatchType.UNEXPECTED_RUN]
        rain_cancelled = [m for m in matches if m.match_type == MatchType.RAIN_CANCELLED]
        future_scheduled = [m for m in matches if m.match_type == MatchType.FUTURE_SCHEDULED]
        
        # Generate report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("🔍 IRRIGATION SCHEDULE vs ACTUAL MATCHING REPORT")
        report_lines.append(f"📅 Date: {target_date.strftime('%A, %B %d, %Y')}")
        report_lines.append(f"⏰ Time Tolerance: ±{self.time_tolerance_minutes} minutes")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Summary
        report_lines.append("📊 MATCH SUMMARY:")
        report_lines.append(f"   ✅ Perfect Matches: {len(perfect_matches)}")
        report_lines.append(f"   ⚠️  Time Variances: {len(time_variance)}")
        report_lines.append(f"   ❌ Missing Runs: {len(missing_runs)}")
        report_lines.append(f"   ❓ Unexpected Runs: {len(unexpected_runs)}")
        report_lines.append(f"   🌧️  Rain Cancelled: {len(rain_cancelled)}")
        report_lines.append(f"   ⏰ Future Scheduled: {len(future_scheduled)}")
        report_lines.append(f"   📋 Total Processed: {len(matches)}")
        report_lines.append("")
        
        # Alerts section
        high_priority = [m for m in matches if m.alert_priority == "HIGH"]
        medium_priority = [m for m in matches if m.alert_priority == "MEDIUM"]
        
        if high_priority or medium_priority:
            report_lines.append("🚨 ALERTS REQUIRING ATTENTION:")
            report_lines.append("-" * 60)
            
            for match in high_priority:
                report_lines.append(f"🔥 HIGH: {match.zone_name}")
                report_lines.append(f"   {match.notes}")
                if match.scheduled_time:
                    report_lines.append(f"   Scheduled: {match.scheduled_time.strftime('%I:%M %p')}")
                report_lines.append("")
            
            for match in medium_priority:
                report_lines.append(f"⚠️  MEDIUM: {match.zone_name}")
                report_lines.append(f"   {match.notes}")
                if match.scheduled_time:
                    report_lines.append(f"   Scheduled: {match.scheduled_time.strftime('%I:%M %p')}")
                report_lines.append("")
        else:
            report_lines.append("✅ NO HIGH/MEDIUM PRIORITY ALERTS")
            report_lines.append("")
        
        # Detailed results
        if matches:
            report_lines.append("📋 DETAILED MATCH RESULTS:")
            report_lines.append("-" * 80)
            
            for match in sorted(matches, key=lambda x: (x.scheduled_time or datetime.min, x.actual_time or datetime.min)):
                scheduled_str = match.scheduled_time.strftime('%I:%M %p') if match.scheduled_time else "N/A"
                actual_str = match.actual_time.strftime('%I:%M %p') if match.actual_time else "N/A"
                time_diff_str = f"{match.time_difference_minutes}min" if match.time_difference_minutes is not None else "N/A"
                
                status_emoji = {
                    MatchType.PERFECT_MATCH: "✅",
                    MatchType.TIME_VARIANCE: "⏰",
                    MatchType.MISSING_RUN: "❌",
                    MatchType.UNEXPECTED_RUN: "❓",
                    MatchType.RAIN_CANCELLED: "🌧️",
                    MatchType.FUTURE_SCHEDULED: "⏳"
                }
                
                report_lines.append(f"{status_emoji[match.match_type]} {match.zone_name}")
                report_lines.append(f"   Type: {match.match_type.value.replace('_', ' ').title()}")
                report_lines.append(f"   Scheduled: {scheduled_str} | Actual: {actual_str} | Diff: {time_diff_str}")
                report_lines.append(f"   Confidence: {match.confidence_score:.2f} | Priority: {match.alert_priority}")
                report_lines.append(f"   Notes: {match.notes}")
                report_lines.append("")
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
