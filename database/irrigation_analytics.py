#!/usr/bin/env python3
"""
Irrigation Analytics System

Tracks and analyzes irrigation patterns over time to detect:
- Water usage trends and averages per zone
- Runtime changes and anomalies  
- Gaps in irrigation (zero gallons usage)
- Sudden consumption spikes or drops
- Schedule changes requiring baseline recalculation
- System efficiency changes

Author: AI Assistant
Date: 2025-08-23
"""

import sqlite3
import json
import sys
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.timezone_utils import get_houston_now, get_display_timestamp

class AnomalyType(Enum):
    """Types of irrigation anomalies"""
    HIGH_USAGE = "high_usage"           # Usage significantly above baseline
    LOW_USAGE = "low_usage"             # Usage significantly below baseline  
    ZERO_USAGE = "zero_usage"           # Expected run but no water used
    RUNTIME_INCREASE = "runtime_increase"  # Runtime longer than expected
    RUNTIME_DECREASE = "runtime_decrease"  # Runtime shorter than expected
    SCHEDULE_CHANGE = "schedule_change"    # Pattern indicates schedule modification
    EFFICIENCY_DROP = "efficiency_drop"    # Gallons per minute decreased
    EFFICIENCY_SPIKE = "efficiency_spike"  # Gallons per minute increased

@dataclass
class UsageBaseline:
    """Baseline water usage pattern for a zone"""
    zone_name: str
    avg_gallons: float
    avg_duration_minutes: int
    avg_gpm: float                    # Gallons per minute
    std_dev_gallons: float
    std_dev_duration: float
    sample_count: int
    baseline_start_date: date
    baseline_end_date: date
    last_updated: datetime
    
@dataclass
class UsageAnomaly:
    """Detected irrigation anomaly"""
    id: Optional[int]
    zone_name: str
    run_date: date
    anomaly_type: AnomalyType
    severity: str                     # HIGH, MEDIUM, LOW
    actual_value: float
    expected_value: float
    deviation_percent: float
    description: str
    detected_at: datetime
    acknowledged: bool = False

@dataclass
class ZoneUsageTrend:
    """Zone usage trend over time"""
    zone_name: str
    period_days: int
    total_runs: int
    total_gallons: float
    avg_gallons_per_run: float
    avg_duration_per_run: float
    avg_gpm: float
    usage_trend: str                  # INCREASING, DECREASING, STABLE
    efficiency_trend: str             # IMPROVING, DECLINING, STABLE
    gap_days: int                     # Days with zero usage
    last_run_date: Optional[date]
    total_cost: float = 0.0          # Total water cost for period
    avg_cost_per_run: float = 0.0    # Average cost per run

@dataclass
class DailyCostSummary:
    """Daily cost summary for a specific date"""
    run_date: date
    zone_name: str
    total_runs: int
    total_gallons: float
    total_cost: float
    avg_cost_per_run: float

@dataclass
class CostReport:
    """Comprehensive cost report"""
    title: str
    period_start: date
    period_end: date
    daily_summaries: List[DailyCostSummary]
    zone_totals: Dict[str, Dict[str, float]]  # zone_name -> {'gallons': x, 'cost': y, 'runs': z}
    grand_total_gallons: float
    grand_total_cost: float
    grand_total_runs: int
    average_daily_cost: float
    rate_structure_name: str

@dataclass
class WaterRateStructure:
    """Water rate structure for cost calculations"""
    name: str                        # Rate structure name (e.g., "Harris County MUD 208")
    base_charge: float              # Monthly base charge
    base_gallons: int               # Gallons included in base charge
    tiers: List[Tuple[int, float]]  # (gallons_threshold, rate_per_1000_gallons)
    regional_fee: float = 0.0       # Additional regional authority fee per 1000 gallons
    seasonal_multiplier: float = 1.0 # Summer vs winter rate multiplier

class IrrigationAnalytics:
    """
    Comprehensive irrigation analytics and anomaly detection system
    """
    
    def __init__(self, db_path: str = "database/irrigation_data.db"):
        """Initialize analytics system"""
        self.db_path = db_path
        self.ensure_analytics_tables()
        
        # Anomaly detection thresholds
        self.usage_threshold = 2.0      # Standard deviations for usage anomalies
        self.duration_threshold = 1.5   # Standard deviations for duration anomalies
        self.efficiency_threshold = 0.3 # 30% change in GPM for efficiency alerts
        self.min_baseline_samples = 1   # Minimum runs to establish baseline
        
        # Default water rate structure (City of Houston 2025 rates)
        self.water_rates = WaterRateStructure(
            name="City of Houston (2025 Rates)",
            base_charge=8.43,            # Water meter charge $7.95 * 1.06 (6% increase)
            base_gallons=0,              # No gallons included in base charge
            tiers=[
                (3000, 1.79),            # 1-3K gal: $1.69 * 1.06 (with credit)
                (6000, 8.45),            # 4-6K gal: $7.97 * 1.06
                (12000, 11.79),          # 7-12K gal: $11.12 * 1.06
                (20000, 15.50),          # 13-20K gal: $14.62 * 1.06
                (float('inf'), 20.22)    # Over 20K gal: $19.08 * 1.06
            ],
            regional_fee=0.0,            # No regional fee
            seasonal_multiplier=1.0      # 2025 rates
        )
        
    def ensure_analytics_tables(self):
        """Create analytics tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Baseline usage patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_baselines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_name TEXT NOT NULL,
                    avg_gallons REAL NOT NULL,
                    avg_duration_minutes INTEGER NOT NULL,
                    avg_gpm REAL NOT NULL,
                    std_dev_gallons REAL NOT NULL,
                    std_dev_duration REAL NOT NULL,
                    sample_count INTEGER NOT NULL,
                    baseline_start_date DATE NOT NULL,
                    baseline_end_date DATE NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(zone_name)
                )
            """)
            
            # Detected anomalies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_name TEXT NOT NULL,
                    run_date DATE NOT NULL,
                    anomaly_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    actual_value REAL NOT NULL,
                    expected_value REAL NOT NULL,
                    deviation_percent REAL NOT NULL,
                    description TEXT NOT NULL,
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    acknowledged BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Usage trends summary table (for faster reporting)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_trends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_name TEXT NOT NULL,
                    analysis_date DATE NOT NULL,
                    period_days INTEGER NOT NULL,
                    total_runs INTEGER NOT NULL,
                    total_gallons REAL NOT NULL,
                    avg_gallons_per_run REAL NOT NULL,
                    avg_duration_per_run REAL NOT NULL,
                    avg_gpm REAL NOT NULL,
                    usage_trend TEXT NOT NULL,
                    efficiency_trend TEXT NOT NULL,
                    gap_days INTEGER NOT NULL,
                    last_run_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(zone_name, analysis_date, period_days)
                )
            """)
            
            conn.commit()
    
    def calculate_baseline(self, zone_name: str, start_date: date = None, end_date: date = None) -> Optional[UsageBaseline]:
        """
        Calculate baseline usage pattern for a zone
        
        Args:
            zone_name: Zone to analyze
            start_date: Start of baseline period (defaults to 30 days ago)
            end_date: End of baseline period (defaults to today)
            
        Returns:
            UsageBaseline object or None if insufficient data
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all successful runs for this zone in the period
            cursor.execute("""
                SELECT actual_gallons, actual_duration_minutes, run_date
                FROM actual_runs 
                WHERE zone_name = ? 
                AND run_date BETWEEN ? AND ?
                AND actual_gallons IS NOT NULL 
                AND actual_gallons > 0
                AND actual_duration_minutes > 0
                ORDER BY run_date
            """, (zone_name, start_date, end_date))
            
            runs = cursor.fetchall()
            
        if len(runs) < self.min_baseline_samples:
            return None
            
        # Calculate statistics
        gallons_values = [float(run[0]) for run in runs]
        duration_values = [int(run[1]) for run in runs]
        gpm_values = [g/d for g, d in zip(gallons_values, duration_values) if d > 0]
        
        baseline = UsageBaseline(
            zone_name=zone_name,
            avg_gallons=statistics.mean(gallons_values),
            avg_duration_minutes=int(statistics.mean(duration_values)),
            avg_gpm=statistics.mean(gpm_values),
            std_dev_gallons=statistics.stdev(gallons_values) if len(gallons_values) > 1 else 0,
            std_dev_duration=statistics.stdev(duration_values) if len(duration_values) > 1 else 0,
            sample_count=len(runs),
            baseline_start_date=start_date,
            baseline_end_date=end_date,
            last_updated=get_houston_now()
        )
        
        return baseline
    
    def update_baseline(self, zone_name: str, start_date: date = None) -> bool:
        """
        Update or create baseline for a zone and store in database
        
        Args:
            zone_name: Zone to update
            start_date: Start date for new baseline calculation
            
        Returns:
            True if baseline was updated successfully
        """
        baseline = self.calculate_baseline(zone_name, start_date)
        if not baseline:
            return False
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert or replace baseline
            cursor.execute("""
                INSERT OR REPLACE INTO usage_baselines
                (zone_name, avg_gallons, avg_duration_minutes, avg_gpm,
                 std_dev_gallons, std_dev_duration, sample_count,
                 baseline_start_date, baseline_end_date, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                baseline.zone_name, baseline.avg_gallons, baseline.avg_duration_minutes,
                baseline.avg_gpm, baseline.std_dev_gallons, baseline.std_dev_duration,
                baseline.sample_count, baseline.baseline_start_date, 
                baseline.baseline_end_date, baseline.last_updated.strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            conn.commit()
            
        return True
    
    def detect_anomalies(self, analysis_date: date = None, days_back: int = 7) -> List[UsageAnomaly]:
        """
        Detect anomalies in recent irrigation data
        
        Args:
            analysis_date: Date to analyze (defaults to today)
            days_back: How many days back to analyze
            
        Returns:
            List of detected anomalies
        """
        if analysis_date is None:
            analysis_date = date.today()
            
        start_date = analysis_date - timedelta(days=days_back)
        anomalies = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all zones with baselines
            cursor.execute("SELECT zone_name FROM usage_baselines")
            zones = [row[0] for row in cursor.fetchall()]
            
            for zone_name in zones:
                # Get baseline for this zone
                cursor.execute("""
                    SELECT avg_gallons, avg_duration_minutes, avg_gpm,
                           std_dev_gallons, std_dev_duration
                    FROM usage_baselines WHERE zone_name = ?
                """, (zone_name,))
                
                baseline_row = cursor.fetchone()
                if not baseline_row:
                    continue
                    
                avg_gallons, avg_duration, avg_gpm, std_dev_gallons, std_dev_duration = baseline_row
                
                # Get recent runs for this zone
                cursor.execute("""
                    SELECT run_date, actual_gallons, actual_duration_minutes
                    FROM actual_runs 
                    WHERE zone_name = ? 
                    AND run_date BETWEEN ? AND ?
                    ORDER BY run_date DESC
                """, (zone_name, start_date, analysis_date))
                
                recent_runs = cursor.fetchall()
                
                for run_date, gallons, duration in recent_runs:
                    run_date = datetime.strptime(run_date, '%Y-%m-%d').date()
                    
                    # Check for anomalies
                    anomalies.extend(self._check_run_anomalies(
                        zone_name, run_date, gallons, duration,
                        avg_gallons, avg_duration, avg_gpm,
                        std_dev_gallons, std_dev_duration
                    ))
        
        return anomalies
    
    def _check_run_anomalies(self, zone_name: str, run_date: date, 
                           actual_gallons: float, actual_duration: int,
                           avg_gallons: float, avg_duration: int, avg_gpm: float,
                           std_dev_gallons: float, std_dev_duration: float) -> List[UsageAnomaly]:
        """Check a single run for anomalies"""
        anomalies = []
        detected_at = get_houston_now()
        
        # Zero usage anomaly
        if actual_gallons == 0 and actual_duration > 0:
            anomalies.append(UsageAnomaly(
                id=None, zone_name=zone_name, run_date=run_date,
                anomaly_type=AnomalyType.ZERO_USAGE, severity="HIGH",
                actual_value=0.0, expected_value=avg_gallons,
                deviation_percent=100.0,
                description=f"Zone ran for {actual_duration} minutes but used 0 gallons",
                detected_at=detected_at
            ))
            return anomalies  # Skip other checks for zero usage
        
        if actual_gallons <= 0 or actual_duration <= 0:
            return anomalies  # Skip analysis for invalid data
            
        # Calculate actual GPM
        actual_gpm = actual_gallons / actual_duration
        
        # Usage anomalies
        if std_dev_gallons > 0:
            gallons_z_score = abs(actual_gallons - avg_gallons) / std_dev_gallons
            if gallons_z_score > self.usage_threshold:
                anomaly_type = AnomalyType.HIGH_USAGE if actual_gallons > avg_gallons else AnomalyType.LOW_USAGE
                severity = "HIGH" if gallons_z_score > 3 else "MEDIUM"
                deviation = ((actual_gallons - avg_gallons) / avg_gallons) * 100
                
                anomalies.append(UsageAnomaly(
                    id=None, zone_name=zone_name, run_date=run_date,
                    anomaly_type=anomaly_type, severity=severity,
                    actual_value=actual_gallons, expected_value=avg_gallons,
                    deviation_percent=abs(deviation),
                    description=f"Water usage {deviation:+.1f}% from baseline ({actual_gallons:.1f} vs {avg_gallons:.1f} gal)",
                    detected_at=detected_at
                ))
        
        # Duration anomalies
        if std_dev_duration > 0:
            duration_z_score = abs(actual_duration - avg_duration) / std_dev_duration
            if duration_z_score > self.duration_threshold:
                anomaly_type = AnomalyType.RUNTIME_INCREASE if actual_duration > avg_duration else AnomalyType.RUNTIME_DECREASE
                severity = "MEDIUM" if duration_z_score > 2 else "LOW"
                deviation = ((actual_duration - avg_duration) / avg_duration) * 100
                
                anomalies.append(UsageAnomaly(
                    id=None, zone_name=zone_name, run_date=run_date,
                    anomaly_type=anomaly_type, severity=severity,
                    actual_value=actual_duration, expected_value=avg_duration,
                    deviation_percent=abs(deviation),
                    description=f"Runtime {deviation:+.1f}% from baseline ({actual_duration} vs {avg_duration} min)",
                    detected_at=detected_at
                ))
        
        # Efficiency anomalies
        efficiency_change = (actual_gpm - avg_gpm) / avg_gpm
        if abs(efficiency_change) > self.efficiency_threshold:
            anomaly_type = AnomalyType.EFFICIENCY_SPIKE if efficiency_change > 0 else AnomalyType.EFFICIENCY_DROP
            severity = "HIGH" if abs(efficiency_change) > 0.5 else "MEDIUM"
            
            anomalies.append(UsageAnomaly(
                id=None, zone_name=zone_name, run_date=run_date,
                anomaly_type=anomaly_type, severity=severity,
                actual_value=actual_gpm, expected_value=avg_gpm,
                deviation_percent=abs(efficiency_change) * 100,
                description=f"Efficiency {efficiency_change:+.1%} from baseline ({actual_gpm:.2f} vs {avg_gpm:.2f} GPM)",
                detected_at=detected_at
            ))
        
        return anomalies
    
    def store_anomalies(self, anomalies: List[UsageAnomaly]) -> int:
        """Store detected anomalies in database"""
        if not anomalies:
            return 0
            
        stored_count = 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for anomaly in anomalies:
                # Check if this anomaly already exists
                cursor.execute("""
                    SELECT id FROM usage_anomalies 
                    WHERE zone_name = ? AND run_date = ? AND anomaly_type = ?
                """, (anomaly.zone_name, anomaly.run_date, anomaly.anomaly_type.value))
                
                if not cursor.fetchone():  # Only store if not already detected
                    cursor.execute("""
                        INSERT INTO usage_anomalies
                        (zone_name, run_date, anomaly_type, severity, actual_value,
                         expected_value, deviation_percent, description, detected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        anomaly.zone_name, anomaly.run_date, anomaly.anomaly_type.value,
                        anomaly.severity, anomaly.actual_value, anomaly.expected_value,
                        anomaly.deviation_percent, anomaly.description,
                        anomaly.detected_at.strftime('%Y-%m-%d %H:%M:%S')
                    ))
                    stored_count += 1
            
            conn.commit()
            
        return stored_count
    
    def calculate_zone_trends(self, period_days: int = 30, analysis_date: date = None) -> List[ZoneUsageTrend]:
        """
        Calculate usage trends for all zones over a period
        
        Args:
            period_days: Number of days to analyze
            analysis_date: End date for analysis (defaults to today)
            
        Returns:
            List of zone trend analyses
        """
        if analysis_date is None:
            analysis_date = date.today()
            
        start_date = analysis_date - timedelta(days=period_days)
        trends = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all zones that have run in the period
            cursor.execute("""
                SELECT DISTINCT zone_name FROM actual_runs 
                WHERE run_date BETWEEN ? AND ?
            """, (start_date, analysis_date))
            
            zones = [row[0] for row in cursor.fetchall()]
            
            for zone_name in zones:
                trend = self._calculate_single_zone_trend(zone_name, start_date, analysis_date, period_days)
                if trend:
                    trends.append(trend)
        
        return trends
    
    def _calculate_single_zone_trend(self, zone_name: str, start_date: date, 
                                   end_date: date, period_days: int) -> Optional[ZoneUsageTrend]:
        """Calculate trend for a single zone"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all runs in period
            cursor.execute("""
                SELECT run_date, actual_gallons, actual_duration_minutes
                FROM actual_runs 
                WHERE zone_name = ? AND run_date BETWEEN ? AND ?
                AND actual_gallons IS NOT NULL AND actual_duration_minutes IS NOT NULL
                ORDER BY run_date
            """, (zone_name, start_date, end_date))
            
            runs = cursor.fetchall()
            
        if not runs:
            return None
            
        # Calculate basic statistics
        total_runs = len(runs)
        gallons_values = [float(run[1]) for run in runs if run[1] > 0]
        duration_values = [int(run[2]) for run in runs if run[2] > 0]
        
        if not gallons_values:
            return None
            
        total_gallons = sum(gallons_values)
        avg_gallons = total_gallons / len(gallons_values)
        avg_duration = sum(duration_values) / len(duration_values) if duration_values else 0
        avg_gpm = avg_gallons / avg_duration if avg_duration > 0 else 0
        
        # Calculate gap days (days with zero usage when irrigation was expected)
        gap_days = self._calculate_gap_days(zone_name, start_date, end_date)
        
        # Determine trends
        usage_trend = self._determine_usage_trend(runs)
        efficiency_trend = self._determine_efficiency_trend(runs)
        
        # Last run date
        last_run_date = max([datetime.strptime(run[0], '%Y-%m-%d').date() for run in runs])
        
        # Calculate water costs
        total_cost = 0.0
        for run in runs:
            gallons = float(run[1])
            if gallons > 0:
                total_cost += self.calculate_water_cost(gallons)
        
        avg_cost_per_run = total_cost / total_runs if total_runs > 0 else 0.0
        
        return ZoneUsageTrend(
            zone_name=zone_name,
            period_days=period_days,
            total_runs=total_runs,
            total_gallons=total_gallons,
            avg_gallons_per_run=avg_gallons,
            avg_duration_per_run=avg_duration,
            avg_gpm=avg_gpm,
            usage_trend=usage_trend,
            efficiency_trend=efficiency_trend,
            gap_days=gap_days,
            last_run_date=last_run_date,
            total_cost=total_cost,
            avg_cost_per_run=avg_cost_per_run
        )
    
    def _calculate_gap_days(self, zone_name: str, start_date: date, end_date: date) -> int:
        """Calculate days with expected irrigation but zero usage"""
        # This is a simplified version - could be enhanced to check against scheduled runs
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM actual_runs 
                WHERE zone_name = ? AND run_date BETWEEN ? AND ?
                AND actual_gallons = 0 AND actual_duration_minutes > 0
            """, (zone_name, start_date, end_date))
            
            return cursor.fetchone()[0]
    
    def _determine_usage_trend(self, runs: List[Tuple]) -> str:
        """Determine if usage is increasing, decreasing, or stable"""
        if len(runs) < 5:
            return "STABLE"
            
        # Split into first and second half
        mid_point = len(runs) // 2
        first_half = runs[:mid_point]
        second_half = runs[mid_point:]
        
        first_avg = sum(float(run[1]) for run in first_half) / len(first_half)
        second_avg = sum(float(run[1]) for run in second_half) / len(second_half)
        
        change_percent = (second_avg - first_avg) / first_avg if first_avg > 0 else 0
        
        if change_percent > 0.1:  # 10% increase
            return "INCREASING"
        elif change_percent < -0.1:  # 10% decrease
            return "DECREASING"
        else:
            return "STABLE"
    
    def _determine_efficiency_trend(self, runs: List[Tuple]) -> str:
        """Determine if efficiency (GPM) is improving, declining, or stable"""
        if len(runs) < 5:
            return "STABLE"
            
        # Calculate GPM for each run
        gpm_values = []
        for run in runs:
            gallons, duration = float(run[1]), int(run[2])
            if gallons > 0 and duration > 0:
                gpm_values.append(gallons / duration)
        
        if len(gpm_values) < 5:
            return "STABLE"
            
        # Split into first and second half
        mid_point = len(gpm_values) // 2
        first_avg = sum(gpm_values[:mid_point]) / mid_point
        second_avg = sum(gpm_values[mid_point:]) / (len(gpm_values) - mid_point)
        
        change_percent = (second_avg - first_avg) / first_avg if first_avg > 0 else 0
        
        if change_percent > 0.1:  # 10% improvement
            return "IMPROVING"
        elif change_percent < -0.1:  # 10% decline
            return "DECLINING"
        else:
            return "STABLE"
    
    def calculate_water_cost(self, gallons: float, monthly_total_gallons: float = None) -> float:
        """
        Calculate water cost for given gallons using tiered rate structure
        
        Args:
            gallons: Gallons to calculate cost for
            monthly_total_gallons: Total household usage for the month (for proper tier calculation)
            
        Returns:
            Cost in dollars (irrigation portion only, not including base charge)
        """
        if gallons <= 0:
            return 0.0
            
        # If no monthly total provided, assume irrigation is incremental usage above base
        if monthly_total_gallons is None:
            monthly_total_gallons = self.water_rates.base_gallons + gallons
            
        # Calculate cost using tiered structure
        total_cost = 0.0
        remaining_gallons = gallons
        current_usage = monthly_total_gallons - gallons  # Usage before this irrigation
        
        for tier_limit, rate_per_1000 in self.water_rates.tiers:
            if remaining_gallons <= 0:
                break
                
            # Determine how many gallons fall in this tier
            tier_start = max(current_usage, self.water_rates.base_gallons)
            tier_end = min(current_usage + remaining_gallons, tier_limit)
            
            if tier_end > tier_start:
                tier_gallons = tier_end - tier_start
                tier_cost = (tier_gallons / 1000.0) * rate_per_1000
                total_cost += tier_cost
                remaining_gallons -= tier_gallons
                current_usage = tier_end
        
        # Add regional fee if applicable
        if self.water_rates.regional_fee > 0:
            total_cost += (gallons / 1000.0) * self.water_rates.regional_fee
            
        # Apply seasonal multiplier
        total_cost *= self.water_rates.seasonal_multiplier
        
        return total_cost
    
    def set_water_rates(self, rate_structure: WaterRateStructure):
        """Set custom water rate structure"""
        self.water_rates = rate_structure
    
    def get_predefined_rate_structures(self) -> Dict[str, WaterRateStructure]:
        """Get common Houston area water rate structures"""
        return {
            "hcmud208_winter": WaterRateStructure(
                name="Harris County MUD 208 (Winter)",
                base_charge=14.00,
                base_gallons=10000,
                tiers=[(20000, 1.75), (30000, 2.00), (float('inf'), 3.50)],
                regional_fee=0.0,
                seasonal_multiplier=1.0
            ),
            "hcmud208_summer": WaterRateStructure(
                name="Harris County MUD 208 (Summer)",
                base_charge=14.00,
                base_gallons=10000,
                tiers=[(20000, 2.00), (30000, 2.25), (float('inf'), 4.00)],
                regional_fee=0.0,
                seasonal_multiplier=1.1  # Approximate summer increase
            ),
            "hcmud6": WaterRateStructure(
                name="Harris County MUD 6",
                base_charge=12.00,
                base_gallons=5000,
                tiers=[(10000, 1.50), (float('inf'), 2.00)],
                regional_fee=4.79,  # WHCRWA fee
                seasonal_multiplier=1.0
            ),
            "hcmud1": WaterRateStructure(
                name="Harris County MUD 1",
                base_charge=16.00,
                base_gallons=5000,
                tiers=[
                    (10000, 1.25), (15000, 1.50), (20000, 2.00), (float('inf'), 2.50)
                ],
                regional_fee=5.06,  # WHCRWA fee
                seasonal_multiplier=1.0
            ),
            "houston_city": WaterRateStructure(
                name="City of Houston (2025 Rates)",
                base_charge=8.43,  # Water meter charge $7.95 * 1.06 (6% increase)
                base_gallons=0,    # No gallons included in base charge
                tiers=[
                    (3000, 1.79),   # 1-3K gal: $1.69 * 1.06 (with credit)
                    (6000, 8.45),   # 4-6K gal: $7.97 * 1.06
                    (12000, 11.79), # 7-12K gal: $11.12 * 1.06
                    (20000, 15.50), # 13-20K gal: $14.62 * 1.06
                    (float('inf'), 20.22)  # Over 20K gal: $19.08 * 1.06
                ],
                regional_fee=0.0,
                seasonal_multiplier=1.0
            )
        }
    
    def generate_analytics_report(self, days_back: int = 30, include_costs: bool = True) -> str:
        """Generate comprehensive analytics report"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Get trends and anomalies
        trends = self.calculate_zone_trends(days_back)
        anomalies = self.detect_anomalies(days_back=days_back)
        
        # Generate report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("💧 IRRIGATION ANALYTICS REPORT")
        report_lines.append(f"📅 Analysis Period: {start_date} to {end_date} ({days_back} days)")
        report_lines.append(f"📊 Generated: {get_display_timestamp()}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Summary
        high_anomalies = [a for a in anomalies if a.severity == "HIGH"]
        medium_anomalies = [a for a in anomalies if a.severity == "MEDIUM"]
        
        report_lines.append("📋 EXECUTIVE SUMMARY:")
        report_lines.append(f"   🏠 Zones analyzed: {len(trends)}")
        report_lines.append(f"   🚨 High priority alerts: {len(high_anomalies)}")
        report_lines.append(f"   ⚠️  Medium priority alerts: {len(medium_anomalies)}")
        report_lines.append(f"   💧 Total gallons used: {sum(t.total_gallons for t in trends):.1f}")
        
        if include_costs and trends:
            total_cost = sum(t.total_cost for t in trends)
            report_lines.append(f"   💰 Total irrigation cost: ${total_cost:.2f}")
            report_lines.append(f"   📊 Rate structure: {self.water_rates.name}")
        
        report_lines.append("")
        
        # High priority anomalies
        if high_anomalies:
            report_lines.append("🚨 HIGH PRIORITY ANOMALIES:")
            report_lines.append("-" * 60)
            for anomaly in high_anomalies:
                report_lines.append(f"🔥 {anomaly.zone_name} ({anomaly.run_date})")
                report_lines.append(f"   {anomaly.description}")
                report_lines.append("")
        
        # Zone trends
        if trends:
            report_lines.append("📈 ZONE USAGE TRENDS:")
            report_lines.append("-" * 80)
            for trend in sorted(trends, key=lambda x: x.total_gallons, reverse=True):
                usage_emoji = {"INCREASING": "📈", "DECREASING": "📉", "STABLE": "➡️"}
                efficiency_emoji = {"IMPROVING": "⬆️", "DECLINING": "⬇️", "STABLE": "➡️"}
                
                report_lines.append(f"🏠 {trend.zone_name}")
                report_lines.append(f"   💧 Total: {trend.total_gallons:.1f} gal ({trend.total_runs} runs)")
                report_lines.append(f"   📊 Avg: {trend.avg_gallons_per_run:.1f} gal/run, {trend.avg_duration_per_run:.1f} min/run")
                report_lines.append(f"   ⚡ Efficiency: {trend.avg_gpm:.2f} GPM")
                
                if include_costs:
                    report_lines.append(f"   💰 Cost: ${trend.total_cost:.2f} total, ${trend.avg_cost_per_run:.2f}/run")
                
                report_lines.append(f"   📈 Trends: Usage {usage_emoji[trend.usage_trend]} {trend.usage_trend}, Efficiency {efficiency_emoji[trend.efficiency_trend]} {trend.efficiency_trend}")
                
                if trend.gap_days > 0:
                    report_lines.append(f"   ⚠️  {trend.gap_days} gap days (zero usage)")
                    
                report_lines.append("")
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def generate_daily_cost_report(self, start_date: date, end_date: date = None) -> CostReport:
        """
        Generate detailed daily cost report by zone for a date range
        
        Args:
            start_date: Start date for report
            end_date: End date for report (defaults to start_date for single day)
            
        Returns:
            CostReport with detailed breakdown
        """
        if end_date is None:
            end_date = start_date
            
        # Determine report title based on date range
        if start_date == end_date:
            title = f"Daily Cost Report - {start_date}"
        else:
            title = f"Cost Report - {start_date} to {end_date}"
            
        daily_summaries = []
        zone_totals = {}
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all runs in the date range
            cursor.execute("""
                SELECT run_date, zone_name, actual_gallons, actual_duration_minutes
                FROM actual_runs 
                WHERE run_date BETWEEN ? AND ?
                AND actual_gallons IS NOT NULL 
                AND actual_gallons > 0
                ORDER BY run_date, zone_name
            """, (start_date, end_date))
            
            runs = cursor.fetchall()
        
        # Group runs by date and zone
        date_zone_runs = {}
        for run in runs:
            run_date_str, zone_name, gallons, duration = run
            run_date = datetime.strptime(run_date_str, '%Y-%m-%d').date()
            
            key = (run_date, zone_name)
            if key not in date_zone_runs:
                date_zone_runs[key] = []
            date_zone_runs[key].append((gallons, duration))
        
        # Calculate daily summaries
        for (run_date, zone_name), zone_runs in date_zone_runs.items():
            total_runs = len(zone_runs)
            total_gallons = sum(float(run[0]) for run in zone_runs)
            total_cost = sum(self.calculate_water_cost(float(run[0])) for run in zone_runs)
            avg_cost_per_run = total_cost / total_runs if total_runs > 0 else 0.0
            
            daily_summaries.append(DailyCostSummary(
                run_date=run_date,
                zone_name=zone_name,
                total_runs=total_runs,
                total_gallons=total_gallons,
                total_cost=total_cost,
                avg_cost_per_run=avg_cost_per_run
            ))
            
            # Update zone totals
            if zone_name not in zone_totals:
                zone_totals[zone_name] = {'gallons': 0.0, 'cost': 0.0, 'runs': 0}
            
            zone_totals[zone_name]['gallons'] += total_gallons
            zone_totals[zone_name]['cost'] += total_cost
            zone_totals[zone_name]['runs'] += total_runs
        
        # Calculate grand totals
        grand_total_gallons = sum(summary.total_gallons for summary in daily_summaries)
        grand_total_cost = sum(summary.total_cost for summary in daily_summaries)
        grand_total_runs = sum(summary.total_runs for summary in daily_summaries)
        
        # Calculate average daily cost
        date_range = (end_date - start_date).days + 1
        average_daily_cost = grand_total_cost / date_range if date_range > 0 else 0.0
        
        return CostReport(
            title=title,
            period_start=start_date,
            period_end=end_date,
            daily_summaries=daily_summaries,
            zone_totals=zone_totals,
            grand_total_gallons=grand_total_gallons,
            grand_total_cost=grand_total_cost,
            grand_total_runs=grand_total_runs,
            average_daily_cost=average_daily_cost,
            rate_structure_name=self.water_rates.name
        )
    
    def generate_cost_report_for_period(self, period: str, reference_date: date = None) -> CostReport:
        """
        Generate cost report for predefined periods
        
        Args:
            period: 'today', 'yesterday', 'week', 'month', 'overall'
            reference_date: Reference date (defaults to today)
            
        Returns:
            CostReport for the specified period
        """
        if reference_date is None:
            reference_date = date.today()
            
        if period == 'today':
            return self.generate_daily_cost_report(reference_date)
        elif period == 'yesterday':
            yesterday = reference_date - timedelta(days=1)
            return self.generate_daily_cost_report(yesterday)
        elif period == 'week':
            # Last 7 days
            start_date = reference_date - timedelta(days=6)
            return self.generate_daily_cost_report(start_date, reference_date)
        elif period == 'month':
            # Current month
            start_date = reference_date.replace(day=1)
            return self.generate_daily_cost_report(start_date, reference_date)
        elif period == 'overall':
            # All available data
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MIN(run_date), MAX(run_date) FROM actual_runs WHERE actual_gallons > 0")
                result = cursor.fetchone()
                
                if result[0] and result[1]:
                    start_date = datetime.strptime(result[0], '%Y-%m-%d').date()
                    end_date = datetime.strptime(result[1], '%Y-%m-%d').date()
                    return self.generate_daily_cost_report(start_date, end_date)
                else:
                    # No data available
                    return self.generate_daily_cost_report(reference_date, reference_date)
        else:
            raise ValueError(f"Unknown period: {period}")
    
    def format_cost_report(self, report: CostReport, show_daily_detail: bool = True) -> str:
        """
        Format cost report for display
        
        Args:
            report: CostReport to format
            show_daily_detail: Whether to show daily breakdown
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"💰 {report.title.upper()}")
        lines.append("=" * 80)
        lines.append(f"📅 Period: {report.period_start} to {report.period_end}")
        lines.append(f"📊 Rate Structure: {report.rate_structure_name}")
        lines.append("")
        
        # Summary
        lines.append("📋 SUMMARY:")
        lines.append(f"   💧 Total gallons: {report.grand_total_gallons:.1f}")
        lines.append(f"   💰 Total cost: ${report.grand_total_cost:.2f}")
        lines.append(f"   🔄 Total runs: {report.grand_total_runs}")
        lines.append(f"   📈 Average daily cost: ${report.average_daily_cost:.2f}")
        lines.append("")
        
        # Zone totals
        if report.zone_totals:
            lines.append("🏠 COST BY ZONE:")
            lines.append("-" * 80)
            lines.append(f"{'Zone':<35} {'Runs':<8} {'Gallons':<12} {'Total Cost':<12} {'Avg/Run'}")
            lines.append("-" * 80)
            
            # Sort zones by cost (highest first)
            sorted_zones = sorted(report.zone_totals.items(), 
                                key=lambda x: x[1]['cost'], reverse=True)
            
            for zone_name, totals in sorted_zones:
                runs = int(totals['runs'])
                gallons = totals['gallons']
                cost = totals['cost']
                avg_cost = cost / runs if runs > 0 else 0.0
                
                zone_display = zone_name[:32] + "..." if len(zone_name) > 35 else zone_name
                lines.append(f"{zone_display:<35} {runs:<8} {gallons:<12.1f} ${cost:<11.2f} ${avg_cost:.2f}")
            
            lines.append("-" * 80)
            lines.append("")
        
        # Daily detail if requested and multiple days
        if show_daily_detail and len(set(s.run_date for s in report.daily_summaries)) > 1:
            lines.append("📅 DAILY BREAKDOWN:")
            lines.append("-" * 80)
            
            # Group by date
            daily_groups = {}
            for summary in report.daily_summaries:
                if summary.run_date not in daily_groups:
                    daily_groups[summary.run_date] = []
                daily_groups[summary.run_date].append(summary)
            
            for run_date in sorted(daily_groups.keys()):
                date_summaries = daily_groups[run_date]
                daily_total_cost = sum(s.total_cost for s in date_summaries)
                daily_total_gallons = sum(s.total_gallons for s in date_summaries)
                daily_total_runs = sum(s.total_runs for s in date_summaries)
                
                lines.append(f"📅 {run_date} - {daily_total_runs} runs, {daily_total_gallons:.1f} gal, ${daily_total_cost:.2f}")
                
                # Sort zones by cost for this day
                date_summaries.sort(key=lambda x: x.total_cost, reverse=True)
                for summary in date_summaries:
                    zone_display = summary.zone_name[:30] + "..." if len(summary.zone_name) > 30 else summary.zone_name
                    lines.append(f"   🏠 {zone_display:<33} {summary.total_runs} runs, {summary.total_gallons:.1f} gal, ${summary.total_cost:.2f}")
                
                lines.append("")
        
        lines.append("=" * 80)
        return "\n".join(lines)

def main():
    """Test the analytics system"""
    print("🔬 TESTING IRRIGATION ANALYTICS SYSTEM")
    print("=" * 60)
    
    analytics = IrrigationAnalytics()
    
    # Update baselines for all zones
    print("📊 Calculating baselines...")
    
    # Get all unique zones
    with sqlite3.connect(analytics.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT zone_name FROM actual_runs")
        zones = [row[0] for row in cursor.fetchall()]
    
    for zone in zones:
        if analytics.update_baseline(zone):
            print(f"   ✅ Updated baseline for {zone}")
        else:
            print(f"   ⚠️  Insufficient data for {zone}")
    
    # Detect anomalies
    print("\n🔍 Detecting anomalies...")
    anomalies = analytics.detect_anomalies()
    stored_count = analytics.store_anomalies(anomalies)
    print(f"   🚨 Found {len(anomalies)} anomalies, stored {stored_count} new ones")
    
    # Generate report
    print("\n📄 Generating analytics report...")
    report = analytics.generate_analytics_report()
    print(report)

if __name__ == "__main__":
    main()
