#!/usr/bin/env python3
"""
Create Test Data for Irrigation Matching Algorithm

Generates realistic test scenarios including:
- Perfect matches
- Time variance matches
- Missing runs (scheduled but no actual)
- Unexpected runs (actual but no scheduled)
- Rain cancelled runs
- Various plant types for priority testing

Author: AI Assistant
Date: August 22, 2025
"""

import sys
import os
import sqlite3
import json
from datetime import datetime, date, timedelta
from typing import List, Dict

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligent_data_storage import IntelligentDataStorage
from hydrawise_web_scraper_refactored import ScheduledRun, ActualRun

def create_test_zones():
    """Create test zones with different plant types for priority testing"""
    zones = [
        (1, "Front Right Turf (MP)", "Front Right Turf (MP)", "LOW", "turf"),
        (2, "Front Left Turf (MP)", "Front Left Turf (MP)", "LOW", "turf"), 
        (3, "Rear Left Pots, Baskets & Planters (M)", "Rear Left Pots, Baskets & Planters (M)", "HIGH", "planters"),
        (4, "Rear Right Pots, Baskets & Planters (M)", "Rear Right Pots, Baskets & Planters (M)", "HIGH", "planters"),
        (5, "Rear Bed/Planters at Pool (M)", "Rear Bed/Planters at Pool (M)", "HIGH", "beds"),
        (6, "Rear Right Bed at House and Pool (M/D)", "Rear Right Bed at House and Pool (M/D)", "HIGH", "beds"),
        (7, "Left Side Turf (MP)", "Left Side Turf (MP)", "LOW", "turf"),
        (8, "Pool Area Plants (M)", "Pool Area Plants (M)", "MEDIUM", "plants"),
        (9, "Front Entrance Beds (M)", "Front Entrance Beds (M)", "HIGH", "beds"),
        (10, "Vegetable Garden (M/D)", "Vegetable Garden (M/D)", "HIGH", "vegetables")
    ]
    
    return zones

def create_test_scheduled_runs(test_date: date) -> List[ScheduledRun]:
    """Create 10 scheduled runs with various scenarios"""
    
    base_datetime = datetime.combine(test_date, datetime.min.time())
    
    scheduled_runs = []
    
    # 1. Perfect match scenario - Front Right Turf
    run1 = ScheduledRun(
        zone_id="1",
        zone_name="Front Right Turf (MP)",
        start_time=base_datetime.replace(hour=6, minute=0),   # 6:00 AM
        duration_minutes=15,
        expected_gallons=25.5,
        notes="Normal lawn watering"
    )
    run1.raw_popup_text = "Time: Mon, 6:00am\nDuration: 15 minutes\nExpected water: 25.5 gallons"
    run1.popup_lines = [
        {"type": "time", "text": "Time: Mon, 6:00am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 15 minutes", "parsed_value": 15},
        {"type": "water", "text": "Expected water: 25.5 gallons", "parsed_value": 25.5}
    ]
    run1.parsed_summary = "Normal scheduled run"
    scheduled_runs.append(run1)
    
    # 2. Time variance match scenario - Front Left Turf  
    run2 = ScheduledRun(
        zone_id="2",
        zone_name="Front Left Turf (MP)",
        start_time=base_datetime.replace(hour=6, minute=15),  # 6:15 AM
        duration_minutes=15,
        expected_gallons=23.8,
        notes="Normal lawn watering"
    )
    run2.raw_popup_text = "Time: Mon, 6:15am\nDuration: 15 minutes\nExpected water: 23.8 gallons"
    run2.popup_lines = [
        {"type": "time", "text": "Time: Mon, 6:15am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 15 minutes", "parsed_value": 15},
        {"type": "water", "text": "Expected water: 23.8 gallons", "parsed_value": 23.8}
    ]
    run2.parsed_summary = "Normal scheduled run"
    scheduled_runs.append(run2)
    
    # 3. Missing run scenario - Rear Left Pots (HIGH priority)
    run3 = ScheduledRun(
        zone_id="3",
        zone_name="Rear Left Pots, Baskets & Planters (M)",
        start_time=base_datetime.replace(hour=7, minute=0),   # 7:00 AM
        duration_minutes=8,
        expected_gallons=12.3,
        notes="High priority planters"
    )
    run3.raw_popup_text = "Time: Mon, 7:00am\nDuration: 8 minutes\nExpected water: 12.3 gallons"
    run3.popup_lines = [
        {"type": "time", "text": "Time: Mon, 7:00am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 8 minutes", "parsed_value": 8},
        {"type": "water", "text": "Expected water: 12.3 gallons", "parsed_value": 12.3}
    ]
    run3.parsed_summary = "Critical planter watering"
    scheduled_runs.append(run3)
    
    # 4. Rain cancelled scenario - Rear Right Pots
    run4 = ScheduledRun(
        zone_id="4",
        zone_name="Rear Right Pots, Baskets & Planters (M)",
        start_time=base_datetime.replace(hour=7, minute=15),  # 7:15 AM
        duration_minutes=0,  # Set to 0 for rain cancellation
        expected_gallons=None,
        notes="Rain cancelled"
    )
    run4.raw_popup_text = "Aborted due to high daily rainfall\nTime: Mon, 7:15am\nDuration: Not scheduled to run"
    run4.popup_lines = [
        {"type": "status", "text": "Aborted due to high daily rainfall", "parsed_value": "aborted_rainfall"},
        {"type": "time", "text": "Time: Mon, 7:15am", "parsed_value": "Mon"},
        {"type": "status", "text": "Duration: Not scheduled to run", "parsed_value": "not_scheduled_rain"}
    ]
    run4.parsed_summary = "Rain cancelled - legitimate"
    scheduled_runs.append(run4)
    
    # 5. Perfect match - Pool Area Beds
    run5 = ScheduledRun(
        zone_id="5",
        zone_name="Rear Bed/Planters at Pool (M)",
        start_time=base_datetime.replace(hour=7, minute=30),  # 7:30 AM
        duration_minutes=10,
        expected_gallons=18.7,
        notes="Pool area landscaping"
    )
    run5.raw_popup_text = "Time: Mon, 7:30am\nDuration: 10 minutes\nExpected water: 18.7 gallons"
    run5.popup_lines = [
        {"type": "time", "text": "Time: Mon, 7:30am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 10 minutes", "parsed_value": 10},
        {"type": "water", "text": "Expected water: 18.7 gallons", "parsed_value": 18.7}
    ]
    run5.parsed_summary = "Pool area watering"
    scheduled_runs.append(run5)
    
    # 6. Missing run scenario - High priority bed
    run6 = ScheduledRun(
        zone_id="6",
        zone_name="Rear Right Bed at House and Pool (M/D)",
        start_time=base_datetime.replace(hour=8, minute=0),   # 8:00 AM
        duration_minutes=12,
        expected_gallons=22.1,
        notes="Critical bed watering"
    )
    run6.raw_popup_text = "Time: Mon, 8:00am\nDuration: 12 minutes\nExpected water: 22.1 gallons"
    run6.popup_lines = [
        {"type": "time", "text": "Time: Mon, 8:00am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 12 minutes", "parsed_value": 12},
        {"type": "water", "text": "Expected water: 22.1 gallons", "parsed_value": 22.1}
    ]
    run6.parsed_summary = "Critical bed irrigation"
    scheduled_runs.append(run6)
    
    # 7. Time variance - Left Side Turf
    run7 = ScheduledRun(
        zone_id="7",
        zone_name="Left Side Turf (MP)",
        start_time=base_datetime.replace(hour=8, minute=30),  # 8:30 AM
        duration_minutes=18,
        expected_gallons=31.2,
        notes="Side lawn area"
    )
    run7.raw_popup_text = "Time: Mon, 8:30am\nDuration: 18 minutes\nExpected water: 31.2 gallons"
    run7.popup_lines = [
        {"type": "time", "text": "Time: Mon, 8:30am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 18 minutes", "parsed_value": 18},
        {"type": "water", "text": "Expected water: 31.2 gallons", "parsed_value": 31.2}
    ]
    run7.parsed_summary = "Side lawn watering"
    scheduled_runs.append(run7)
    
    # 8. Perfect match - Pool Area Plants
    run8 = ScheduledRun(
        zone_id="8",
        zone_name="Pool Area Plants (M)",
        start_time=base_datetime.replace(hour=9, minute=0),   # 9:00 AM
        duration_minutes=6,
        expected_gallons=8.5,
        notes="Pool landscaping"
    )
    run8.raw_popup_text = "Time: Mon, 9:00am\nDuration: 6 minutes\nExpected water: 8.5 gallons"
    run8.popup_lines = [
        {"type": "time", "text": "Time: Mon, 9:00am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 6 minutes", "parsed_value": 6},
        {"type": "water", "text": "Expected water: 8.5 gallons", "parsed_value": 8.5}
    ]
    run8.parsed_summary = "Pool area plants"
    scheduled_runs.append(run8)
    
    # 9. Missing run - Front Entrance Beds (HIGH priority)
    run9 = ScheduledRun(
        zone_id="9",
        zone_name="Front Entrance Beds (M)",
        start_time=base_datetime.replace(hour=9, minute=30),  # 9:30 AM
        duration_minutes=7,
        expected_gallons=11.8,
        notes="High visibility entrance"
    )
    run9.raw_popup_text = "Time: Mon, 9:30am\nDuration: 7 minutes\nExpected water: 11.8 gallons"
    run9.popup_lines = [
        {"type": "time", "text": "Time: Mon, 9:30am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 7 minutes", "parsed_value": 7},
        {"type": "water", "text": "Expected water: 11.8 gallons", "parsed_value": 11.8}
    ]
    run9.parsed_summary = "Entrance bed watering"
    scheduled_runs.append(run9)
    
    # 10. Perfect match - Vegetable Garden
    run10 = ScheduledRun(
        zone_id="10",
        zone_name="Vegetable Garden (M/D)",
        start_time=base_datetime.replace(hour=10, minute=0),  # 10:00 AM
        duration_minutes=14,
        expected_gallons=28.9,
        notes="Food production area"
    )
    run10.raw_popup_text = "Time: Mon, 10:00am\nDuration: 14 minutes\nExpected water: 28.9 gallons"
    run10.popup_lines = [
        {"type": "time", "text": "Time: Mon, 10:00am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 14 minutes", "parsed_value": 14},
        {"type": "water", "text": "Expected water: 28.9 gallons", "parsed_value": 28.9}
    ]
    run10.parsed_summary = "Vegetable garden irrigation"
    scheduled_runs.append(run10)
    
    return scheduled_runs

def create_test_actual_runs(test_date: date) -> List[ActualRun]:
    """Create actual runs that match various scenarios"""
    
    base_datetime = datetime.combine(test_date, datetime.min.time())
    
    actual_runs = []
    
    # 1. Perfect match for Front Right Turf (exactly on time)
    run1 = ActualRun(
        zone_id="1",
        zone_name="Front Right Turf (MP)",
        start_time=base_datetime.replace(hour=6, minute=0),   # Exact match
        duration_minutes=15,
        actual_gallons=24.8,  # Slightly under expected
        status="Normal watering cycle",
        failure_reason=None,
        notes="Current: 750mA, Normal completion"
    )
    run1.raw_popup_text = "Start: Mon, 6:00am\nDuration: 15 minutes\nWater delivered: 24.8 gallons\nStatus: Normal watering cycle"
    run1.popup_lines = [
        {"type": "time", "text": "Start: Mon, 6:00am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 15 minutes", "parsed_value": 15},
        {"type": "water", "text": "Water delivered: 24.8 gallons", "parsed_value": 24.8},
        {"type": "status", "text": "Status: Normal watering cycle", "parsed_value": "normal"}
    ]
    run1.parsed_summary = "Successful irrigation run"
    actual_runs.append(run1)
    
    # 2. Time variance for Front Left Turf (10 minutes late)
    run2 = ActualRun(
        zone_id="2", 
        zone_name="Front Left Turf (MP)",
        start_time=base_datetime.replace(hour=6, minute=25),  # 10 minutes late
        duration_minutes=15,
        actual_gallons=23.1,  # Close to expected
        status="Normal watering cycle",
        failure_reason=None,
        notes="Current: 720mA, Delayed start"
    )
    run2.raw_popup_text = "Start: Mon, 6:25am\nDuration: 15 minutes\nWater delivered: 23.1 gallons\nStatus: Normal watering cycle"
    run2.popup_lines = [
        {"type": "time", "text": "Start: Mon, 6:25am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 15 minutes", "parsed_value": 15},
        {"type": "water", "text": "Water delivered: 23.1 gallons", "parsed_value": 23.1},
        {"type": "status", "text": "Status: Normal watering cycle", "parsed_value": "normal"}
    ]
    run2.parsed_summary = "Normal run with timing variance"
    actual_runs.append(run2)
    
    # 3. NO ACTUAL RUN for Rear Left Pots (missing run scenario - will trigger HIGH alert)
    
    # 4. NO ACTUAL RUN for Rear Right Pots (rain cancelled - legitimate)
    
    # 5. Perfect match for Pool Area Beds
    run5 = ActualRun(
        zone_id="5",
        zone_name="Rear Bed/Planters at Pool (M)",
        start_time=base_datetime.replace(hour=7, minute=32),  # 2 minutes late
        duration_minutes=10,
        actual_gallons=19.1,  # Slightly over expected
        status="Normal watering cycle",
        failure_reason=None,
        notes="Current: 850mA, Excellent delivery"
    )
    run5.raw_popup_text = "Start: Mon, 7:32am\nDuration: 10 minutes\nWater delivered: 19.1 gallons\nStatus: Normal watering cycle"
    run5.popup_lines = [
        {"type": "time", "text": "Start: Mon, 7:32am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 10 minutes", "parsed_value": 10},
        {"type": "water", "text": "Water delivered: 19.1 gallons", "parsed_value": 19.1},
        {"type": "status", "text": "Status: Normal watering cycle", "parsed_value": "normal"}
    ]
    run5.parsed_summary = "Efficient watering cycle"
    actual_runs.append(run5)
    
    # 6. NO ACTUAL RUN for Rear Right Bed (missing run scenario - will trigger HIGH alert)
    
    # 7. Time variance for Left Side Turf (20 minutes early!)
    run7 = ActualRun(
        zone_id="7",
        zone_name="Left Side Turf (MP)",
        start_time=base_datetime.replace(hour=8, minute=10),  # 20 minutes early
        duration_minutes=18,
        actual_gallons=29.8,  # Under expected
        status="Normal watering cycle",
        failure_reason=None,
        notes="Current: 680mA, Early start"
    )
    run7.raw_popup_text = "Start: Mon, 8:10am\nDuration: 18 minutes\nWater delivered: 29.8 gallons\nStatus: Normal watering cycle"
    run7.popup_lines = [
        {"type": "time", "text": "Start: Mon, 8:10am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 18 minutes", "parsed_value": 18},
        {"type": "water", "text": "Water delivered: 29.8 gallons", "parsed_value": 29.8},
        {"type": "status", "text": "Status: Normal watering cycle", "parsed_value": "normal"}
    ]
    run7.parsed_summary = "Early start irrigation"
    actual_runs.append(run7)
    
    # 8. Perfect match for Pool Area Plants
    run8 = ActualRun(
        zone_id="8",
        zone_name="Pool Area Plants (M)",
        start_time=base_datetime.replace(hour=9, minute=1),   # 1 minute late
        duration_minutes=6,
        actual_gallons=8.7,  # Close to expected
        status="Normal watering cycle",
        failure_reason=None,
        notes="Current: 900mA, Perfect conditions"
    )
    run8.raw_popup_text = "Start: Mon, 9:01am\nDuration: 6 minutes\nWater delivered: 8.7 gallons\nStatus: Normal watering cycle"
    run8.popup_lines = [
        {"type": "time", "text": "Start: Mon, 9:01am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 6 minutes", "parsed_value": 6},
        {"type": "water", "text": "Water delivered: 8.7 gallons", "parsed_value": 8.7},
        {"type": "status", "text": "Status: Normal watering cycle", "parsed_value": "normal"}
    ]
    run8.parsed_summary = "Optimal plant watering"
    actual_runs.append(run8)
    
    # 9. NO ACTUAL RUN for Front Entrance Beds (missing run scenario - will trigger HIGH alert)
    
    # 10. Perfect match for Vegetable Garden
    run10 = ActualRun(
        zone_id="10",
        zone_name="Vegetable Garden (M/D)",
        start_time=base_datetime.replace(hour=10, minute=3),  # 3 minutes late
        duration_minutes=14,
        actual_gallons=30.2,  # Slightly over expected - good for vegetables
        status="Normal watering cycle",
        failure_reason=None,
        notes="Current: 820mA, Excellent growth conditions"
    )
    run10.raw_popup_text = "Start: Mon, 10:03am\nDuration: 14 minutes\nWater delivered: 30.2 gallons\nStatus: Normal watering cycle"
    run10.popup_lines = [
        {"type": "time", "text": "Start: Mon, 10:03am", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 14 minutes", "parsed_value": 14},
        {"type": "water", "text": "Water delivered: 30.2 gallons", "parsed_value": 30.2},
        {"type": "status", "text": "Status: Normal watering cycle", "parsed_value": "normal"}
    ]
    run10.parsed_summary = "Vegetable garden success"
    actual_runs.append(run10)
    
    # 11. UNEXPECTED RUN - Manual override (no scheduled match)
    unexpected_run = ActualRun(
        zone_id="8",  # Same zone as run8 but different time
        zone_name="Pool Area Plants (M)",
        start_time=base_datetime.replace(hour=14, minute=30),  # 2:30 PM - no schedule
        duration_minutes=4,
        actual_gallons=5.2,
        status="Manual override",
        failure_reason=None,
        notes="Current: 850mA, Manual intervention"
    )
    unexpected_run.raw_popup_text = "Start: Mon, 2:30pm\nDuration: 4 minutes\nWater delivered: 5.2 gallons\nStatus: Manual override"
    unexpected_run.popup_lines = [
        {"type": "time", "text": "Start: Mon, 2:30pm", "parsed_value": "Mon"},
        {"type": "duration", "text": "Duration: 4 minutes", "parsed_value": 4},
        {"type": "water", "text": "Water delivered: 5.2 gallons", "parsed_value": 5.2},
        {"type": "status", "text": "Status: Manual override", "parsed_value": "manual"}
    ]
    unexpected_run.parsed_summary = "Unscheduled manual run"
    actual_runs.append(unexpected_run)
    
    return actual_runs

def setup_test_database(test_date: date) -> str:
    """Setup test database with comprehensive test data"""
    
    # Use a test database
    test_db_path = "database/test_irrigation_matching.db"
    
    # Remove existing test database
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    # Initialize database with enhanced storage
    storage = IntelligentDataStorage(test_db_path)
    
    print(f"📊 Setting up test database: {test_db_path}")
    print(f"📅 Test date: {test_date}")
    
    # Add test zones
    zones = create_test_zones()
    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.cursor()
        for zone_data in zones:
            cursor.execute("""
                INSERT OR REPLACE INTO zones 
                (zone_id, zone_name, zone_display_name, priority_level, plant_type)
                VALUES (?, ?, ?, ?, ?)
            """, zone_data)
        conn.commit()
    
    print(f"✅ Added {len(zones)} test zones")
    
    # Create and store test scheduled runs
    scheduled_runs = create_test_scheduled_runs(test_date)
    
    # Mark rain cancelled run
    for run in scheduled_runs:
        if "Rear Right Pots" in run.zone_name:
            # This will be processed as rain cancelled during storage
            pass
    
    stored_scheduled = storage.store_scheduled_runs_enhanced(scheduled_runs, test_date)
    print(f"✅ Added {stored_scheduled} scheduled runs")
    
    # Create and store test actual runs  
    actual_runs = create_test_actual_runs(test_date)
    stored_actual = storage.store_actual_runs_enhanced(actual_runs, test_date)
    print(f"✅ Added {stored_actual} actual runs")
    
    print(f"\n📋 TEST SCENARIOS CREATED:")
    print(f"   ✅ Perfect Matches: 4 zones (Front Right Turf, Pool Beds, Pool Plants, Vegetable Garden)")
    print(f"   ⏰ Time Variances: 2 zones (Front Left Turf +10min, Left Side Turf -20min)")
    print(f"   ❌ Missing Runs: 3 zones (Rear Left Pots, Rear Right Bed, Front Entrance Beds)")
    print(f"   🌧️  Rain Cancelled: 1 zone (Rear Right Pots - legitimate)")
    print(f"   ❓ Unexpected Runs: 1 zone (Pool Plants manual override)")
    print(f"   🚨 HIGH Priority Alerts: 3 zones (missing planters/beds)")
    print(f"   ⚠️  MEDIUM Priority Alerts: 1 zone (unexpected run)")
    
    return test_db_path

def main():
    """Create test data for irrigation matching algorithm"""
    
    print("🧪 CREATING TEST DATA FOR IRRIGATION MATCHING")
    print("=" * 60)
    
    # Use tomorrow as test date for clean testing
    test_date = date.today() + timedelta(days=1)
    
    try:
        test_db_path = setup_test_database(test_date)
        
        print(f"\n🎯 Test database ready: {test_db_path}")
        print(f"📅 Test date: {test_date}")
        print(f"\n💡 Next steps:")
        print(f"   1. Run matching algorithm: python -c \"from database.irrigation_matcher import IrrigationMatcher; m=IrrigationMatcher('{test_db_path}'); print(m.generate_match_report('{test_date}'))\"")
        print(f"   2. Review match results and alert priorities")
        print(f"   3. Validate algorithm accuracy")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
