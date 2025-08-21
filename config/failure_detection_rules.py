#!/usr/bin/env python3
"""
Irrigation Failure Detection Rules

Defines rules and thresholds for detecting irrigation failures that require
immediate user intervention to protect plants.

Based on analysis of Hydrawise Excel data showing:
- 13.7% sensor input failures ("Aborted due to sensor input") 
- Large gaps (24-90 hours) indicating system failures/power outages
- Temperature-based reductions that may be too conservative
- High manual intervention rates indicating schedule problems

Author: AI Assistant  
Date: 2025
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

class AlertLevel(Enum):
    """Alert severity levels for different failure types"""
    CRITICAL = "CRITICAL"    # Immediate plant risk - needs action within 1 hour
    WARNING = "WARNING"      # Monitor closely - may need action today  
    INFO = "INFO"           # Awareness only - normal system behavior

class FailureType(Enum):
    """Types of irrigation failures detected"""
    SENSOR_ABORT = "sensor_abort"           # "Aborted due to sensor input"
    SCHEDULE_GAP = "schedule_gap"           # Missing runs (power outage, system failure)
    CANCELLED_RUN = "cancelled_run"         # "Cancelled due to manual start" 
    SUSPENDED_CYCLE = "suspended_cycle"     # "Watering cycle suspended"
    REDUCED_WATERING = "reduced_watering"   # "Reduced watering due to temperature"
    SYSTEM_OFFLINE = "system_offline"       # Controller not responding
    MISSED_WINDOW = "missed_window"         # Zone should have run by now but didn't

@dataclass
class FailureRule:
    """Rule definition for detecting specific failure types"""
    failure_type: FailureType
    alert_level: AlertLevel
    description: str
    detection_method: str
    time_threshold_hours: Optional[float] = None
    action_required: str = ""
    plant_risk: str = ""

# Failure detection rules based on data analysis
FAILURE_DETECTION_RULES = {
    
    # CRITICAL ALERTS - Immediate action required to prevent plant damage
    FailureType.SENSOR_ABORT: FailureRule(
        failure_type=FailureType.SENSOR_ABORT,
        alert_level=AlertLevel.CRITICAL,
        description="Zone aborted due to sensor input failure",
        detection_method="Check for 'Aborted due to sensor input' in schedule or detect sensor error patterns",
        time_threshold_hours=1.0,
        action_required="Manual watering required immediately. Check flow sensor connections.",
        plant_risk="HIGH - Plants may not receive water. Risk increases with temperature."
    ),
    
    FailureType.SCHEDULE_GAP: FailureRule(
        failure_type=FailureType.SCHEDULE_GAP,
        alert_level=AlertLevel.CRITICAL,
        description="Large gap in watering schedule indicating system failure",
        detection_method="Detect gaps >24 hours between expected waterings",
        time_threshold_hours=24.0,
        action_required="Check system power and connectivity. Manual watering may be needed.",
        plant_risk="HIGH - Extended period without water. Trees and expensive plants at risk."
    ),
    
    FailureType.SYSTEM_OFFLINE: FailureRule(
        failure_type=FailureType.SYSTEM_OFFLINE,
        alert_level=AlertLevel.CRITICAL,
        description="Controller not responding to API calls",
        detection_method="API connection failures or timeout errors",
        time_threshold_hours=2.0,
        action_required="Check controller power, internet connection, and system status.",
        plant_risk="HIGH - Cannot monitor or control irrigation. Manual watering required."
    ),
    
    FailureType.MISSED_WINDOW: FailureRule(
        failure_type=FailureType.MISSED_WINDOW,
        alert_level=AlertLevel.CRITICAL,
        description="Zone should have run by now but hasn't started",
        detection_method="Compare current time with expected schedule window",
        time_threshold_hours=2.0,
        action_required="Start zone manually if weather conditions permit.",
        plant_risk="MEDIUM-HIGH - Delayed watering may stress plants, especially in hot weather."
    ),
    
    # WARNING ALERTS - Monitor closely, may need action
    FailureType.CANCELLED_RUN: FailureRule(
        failure_type=FailureType.CANCELLED_RUN,
        alert_level=AlertLevel.WARNING,
        description="Scheduled run cancelled due to manual intervention",
        detection_method="Detect 'Cancelled due to manual start' events",
        time_threshold_hours=6.0,
        action_required="Verify zone received adequate water or schedule makeup run.",
        plant_risk="MEDIUM - Zone may have received partial watering."
    ),
    
    FailureType.SUSPENDED_CYCLE: FailureRule(
        failure_type=FailureType.SUSPENDED_CYCLE,
        alert_level=AlertLevel.WARNING,
        description="Watering cycle manually suspended",
        detection_method="Detect 'Watering cycle suspended' status",
        time_threshold_hours=12.0,
        action_required="Check if suspension is intentional. Resume if weather permits.",
        plant_risk="MEDIUM - Plants may miss watering if suspension continues."
    ),
    
    FailureType.REDUCED_WATERING: FailureRule(
        failure_type=FailureType.REDUCED_WATERING,
        alert_level=AlertLevel.WARNING,
        description="Watering reduced due to temperature/weather",
        detection_method="Detect 'Reduced watering due to temperature' events",
        time_threshold_hours=24.0,
        action_required="Monitor plant stress. Consider manual watering if reduction is excessive.",
        plant_risk="LOW-MEDIUM - May be appropriate for weather, but monitor high-value plants."
    ),
}

# Zone priority levels based on plant types and investment
ZONE_PRIORITIES = {
    # High priority - Trees, expensive plants, difficult to replace
    "HIGH": {
        "description": "Trees, expensive plants, high-investment landscaping",
        "max_hours_without_water": 24,
        "alert_multiplier": 1.0,  # Full sensitivity
        "zones": [
            # These will be populated from your flow rate data
            "trees", "expensive_plants", "new_installations"
        ]
    },
    
    # Medium priority - Established landscaping, perennials
    "MEDIUM": {
        "description": "Established landscaping, shrubs, perennial beds",
        "max_hours_without_water": 36,
        "alert_multiplier": 0.8,  # Slightly less sensitive
        "zones": [
            # Established landscaping zones
        ]
    },
    
    # Lower priority - Turf, resilient plants
    "LOW": {
        "description": "Turf areas, drought-tolerant plants",
        "max_hours_without_water": 48,
        "alert_multiplier": 0.6,  # Less sensitive to delays
        "zones": [
            # Turf zones from your data
        ]
    }
}

# Flow rate data integration for water calculations
ZONE_FLOW_RATES = {
    # From your provided flow rate data
    1: {"name": "Front Right Turf", "gpm": 2.5, "priority": "LOW"},
    2: {"name": "Front Turf Across Sidewalk", "gpm": 4.5, "priority": "LOW"}, 
    3: {"name": "Front Left Turf", "gpm": 3.2, "priority": "LOW"},
    4: {"name": "Front Planters and Pots", "gpm": 1.0, "priority": "HIGH"},
    5: {"name": "Rear Left Turf", "gpm": 2.2, "priority": "LOW"},
    6: {"name": "Rear right turf", "gpm": 5.3, "priority": "LOW"},
    8: {"name": "Rear left Beds at fence", "gpm": 11.3, "priority": "HIGH"},
    9: {"name": "Rear right beds at fence", "gpm": 8.3, "priority": "HIGH"},
    10: {"name": "Rear Left Pots, baskets & Planters", "gpm": 3.9, "priority": "HIGH"},
    11: {"name": "Rear right pots, baskets & Planters", "gpm": 5.7, "priority": "HIGH"},
    12: {"name": "Rear Bed/Planters/ at Pool", "gpm": 1.3, "priority": "MEDIUM"},
    13: {"name": "Front right bed across drive", "gpm": 1.2, "priority": "MEDIUM"},
    14: {"name": "Rear Right Bed at House and Pool", "gpm": 3.0, "priority": "MEDIUM"},
    15: {"name": "rear Left Bed at House", "gpm": 1.2, "priority": "MEDIUM"},
    16: {"name": "Front Color", "gpm": 10.9, "priority": "HIGH"},
    17: {"name": "Front Left Beds", "gpm": 2.6, "priority": "MEDIUM"},
}

def get_zone_priority(zone_id: int) -> str:
    """Get priority level for a zone based on flow rate data"""
    if zone_id in ZONE_FLOW_RATES:
        return ZONE_FLOW_RATES[zone_id]["priority"]
    return "MEDIUM"  # Default priority

def calculate_water_needed(zone_id: int, hours_missed: float) -> float:
    """
    Calculate gallons of water missed based on typical watering duration.
    
    Args:
        zone_id: Zone identifier
        hours_missed: Hours since expected watering
        
    Returns:
        float: Estimated gallons of water missed
    """
    if zone_id not in ZONE_FLOW_RATES:
        return 0.0
    
    gpm = ZONE_FLOW_RATES[zone_id]["gpm"]
    # Estimate typical watering duration based on priority
    priority = get_zone_priority(zone_id)
    
    if priority == "HIGH":
        typical_minutes = 5  # High-value plants get more water
    elif priority == "MEDIUM": 
        typical_minutes = 3  # Moderate watering
    else:
        typical_minutes = 2  # Turf gets less frequent, shorter watering
    
    # Calculate missed water if zone should have run in the missed time
    # Assume zones run twice daily (every 12 hours)
    expected_runs = max(1, int(hours_missed / 12))
    
    return gpm * typical_minutes * expected_runs

def should_alert_for_zone(zone_id: int, failure_type: FailureType, hours_since_last: float) -> bool:
    """
    Determine if an alert should be triggered for a specific zone failure.
    
    Args:
        zone_id: Zone identifier  
        failure_type: Type of failure detected
        hours_since_last: Hours since last successful watering
        
    Returns:
        bool: True if alert should be triggered
    """
    priority = get_zone_priority(zone_id)
    rule = FAILURE_DETECTION_RULES.get(failure_type)
    
    if not rule:
        return False
    
    # Apply priority-based thresholds
    priority_config = ZONE_PRIORITIES.get(priority, ZONE_PRIORITIES["MEDIUM"])
    max_hours = priority_config["max_hours_without_water"]
    
    # Critical alerts trigger immediately regardless of priority
    if rule.alert_level == AlertLevel.CRITICAL:
        return True
    
    # Warning alerts use priority-adjusted thresholds
    if rule.alert_level == AlertLevel.WARNING:
        return hours_since_last >= (max_hours * 0.5)  # Alert at 50% of max time
    
    return False

if __name__ == "__main__":
    print("Irrigation Failure Detection Rules")
    print("=" * 50)
    
    print("\nFailure Types and Rules:")
    for failure_type, rule in FAILURE_DETECTION_RULES.items():
        print(f"\n{failure_type.value.upper()}:")
        print(f"  Level: {rule.alert_level.value}")
        print(f"  Description: {rule.description}")
        print(f"  Action: {rule.action_required}")
        print(f"  Plant Risk: {rule.plant_risk}")
    
    print(f"\nZone Priorities:")
    for priority, config in ZONE_PRIORITIES.items():
        print(f"\n{priority}:")
        print(f"  Description: {config['description']}")
        print(f"  Max hours without water: {config['max_hours_without_water']}")
    
    print(f"\nExample Water Loss Calculations:")
    for zone_id in [4, 8, 16]:  # High priority zones
        zone_info = ZONE_FLOW_RATES[zone_id]
        water_missed_24h = calculate_water_needed(zone_id, 24)
        print(f"Zone {zone_id} ({zone_info['name']}): {water_missed_24h:.1f} gallons missed in 24 hours")
