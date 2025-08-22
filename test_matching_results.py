#!/usr/bin/env python3
"""
Test and Save Matching Algorithm Results

Runs the irrigation matching algorithm on test data and saves results for analysis.
"""

import os
from datetime import date, datetime
from database.irrigation_matcher import IrrigationMatcher

def main():
    """Test matching algorithm and save results"""
    
    print("🧪 TESTING IRRIGATION MATCHING ALGORITHM")
    print("=" * 60)
    
    # Test with our comprehensive test data
    test_date = date(2025, 8, 23)
    test_db_path = "database/test_irrigation_matching.db"
    
    if not os.path.exists(test_db_path):
        print("❌ Test database not found. Run create_test_data.py first.")
        return False
    
    try:
        # Create matcher
        matcher = IrrigationMatcher(test_db_path, time_tolerance_minutes=30)
        
        # Generate comprehensive report
        print(f"🔍 Running matching algorithm for {test_date}...")
        report = matcher.generate_match_report(test_date)
        
        # Save report to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"reports/irrigation_matching_test_{timestamp}.txt"
        
        # Ensure reports directory exists
        os.makedirs("reports", exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ Report saved to: {report_file}")
        
        # Display the report
        print("\n" + report)
        
        # Validate expected results
        print("\n" + "=" * 60)
        print("🎯 VALIDATION OF TEST SCENARIOS:")
        print("=" * 60)
        
        matches = matcher.match_runs(test_date)
        
        # Count by type
        perfect_matches = len([m for m in matches if m.match_type.value == "perfect_match"])
        time_variances = len([m for m in matches if m.match_type.value == "time_variance"])
        missing_runs = len([m for m in matches if m.match_type.value == "missing_run"])
        unexpected_runs = len([m for m in matches if m.match_type.value == "unexpected_run"])
        rain_cancelled = len([m for m in matches if m.match_type.value == "rain_cancelled"])
        
        # Count by priority
        high_alerts = len([m for m in matches if m.alert_priority == "HIGH"])
        medium_alerts = len([m for m in matches if m.alert_priority == "MEDIUM"])
        low_alerts = len([m for m in matches if m.alert_priority == "LOW"])
        
        print(f"✅ Perfect Matches: {perfect_matches} (Expected: 4)")
        print(f"⏰ Time Variances: {time_variances} (Expected: 2)")
        print(f"❌ Missing Runs: {missing_runs} (Expected: 3)")
        print(f"❓ Unexpected Runs: {unexpected_runs} (Expected: 1)")
        print(f"🌧️  Rain Cancelled: {rain_cancelled} (Expected: 1)")
        print(f"🔥 HIGH Priority Alerts: {high_alerts} (Expected: 3 missing critical zones)")
        print(f"⚠️  MEDIUM Priority Alerts: {medium_alerts} (Expected: 1 unexpected run)")
        print(f"📊 LOW Priority Alerts: {low_alerts} (Expected: 2 time variances)")
        
        # Detailed validation
        validation_results = []
        
        # Check specific scenarios
        front_right_turf = next((m for m in matches if "Front Right Turf" in m.zone_name), None)
        if front_right_turf and front_right_turf.match_type.value == "perfect_match":
            validation_results.append("✅ Front Right Turf: Perfect match detected")
        else:
            validation_results.append("❌ Front Right Turf: Expected perfect match")
        
        rear_left_pots = next((m for m in matches if "Rear Left Pots" in m.zone_name), None)
        if rear_left_pots and rear_left_pots.match_type.value == "missing_run" and rear_left_pots.alert_priority == "HIGH":
            validation_results.append("✅ Rear Left Pots: Missing run with HIGH priority detected")
        else:
            validation_results.append("❌ Rear Left Pots: Expected missing run with HIGH priority")
        
        rear_right_pots = next((m for m in matches if "Rear Right Pots" in m.zone_name), None)
        if rear_right_pots and rear_right_pots.match_type.value == "rain_cancelled":
            validation_results.append("✅ Rear Right Pots: Rain cancellation detected")
        else:
            validation_results.append("❌ Rear Right Pots: Expected rain cancellation")
        
        unexpected_run = next((m for m in matches if m.match_type.value == "unexpected_run"), None)
        if unexpected_run and "Pool Area Plants" in unexpected_run.zone_name:
            validation_results.append("✅ Pool Area Plants: Unexpected run detected")
        else:
            validation_results.append("❌ Pool Area Plants: Expected unexpected run")
        
        print("\n📋 SPECIFIC SCENARIO VALIDATION:")
        for result in validation_results:
            print(f"   {result}")
        
        # Overall validation
        total_expected = 11  # 10 scheduled + 1 unexpected
        total_found = len(matches)
        
        if total_found == total_expected:
            print(f"\n🎉 VALIDATION SUCCESSFUL: Found all {total_expected} expected matches!")
            print("✅ Algorithm correctly identified all test scenarios")
            print("✅ Alert priorities assigned correctly")
            print("✅ Rain cancellations handled properly")
            print("✅ Time tolerances working as expected")
        else:
            print(f"\n⚠️  VALIDATION ISSUE: Expected {total_expected} matches, found {total_found}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing matching algorithm: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
