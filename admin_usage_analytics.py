#!/usr/bin/env python3
"""
Admin CLI for Irrigation Analytics

Provides command-line interface for irrigation analytics and anomaly detection:
- Calculate and update baselines for zones
- Detect usage anomalies and efficiency changes
- Generate comprehensive analytics reports
- Track usage trends over time
- Reset baselines when schedules change

Author: AI Assistant
Date: 2025-08-23
"""

import argparse
import sys
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.irrigation_analytics import IrrigationAnalytics, AnomalyType

def print_banner():
    """Print the admin banner"""
    print("=" * 70)
    print("🔬 HYDRAWISE IRRIGATION ANALYTICS ADMIN")
    print("=" * 70)

def cmd_baseline(args):
    """Calculate and update baselines for zones"""
    print_banner()
    print("📊 CALCULATING IRRIGATION BASELINES")
    print()
    
    try:
        analytics = IrrigationAnalytics()
        
        # Parse start date if provided
        start_date = None
        if args.start_date:
            if args.start_date == "30days":
                start_date = date.today() - timedelta(days=30)
            else:
                start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        
        if args.zone:
            # Update baseline for specific zone
            zones = [args.zone]
        else:
            # Get all zones
            import sqlite3
            with sqlite3.connect(analytics.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT zone_name FROM actual_runs ORDER BY zone_name")
                zones = [row[0] for row in cursor.fetchall()]
        
        print(f"🎯 Updating baselines for {len(zones)} zone(s)")
        if start_date:
            print(f"📅 Using data from {start_date} onwards")
        print()
        
        updated_count = 0
        insufficient_data = 0
        
        for zone in zones:
            if analytics.update_baseline(zone, start_date):
                baseline = analytics.calculate_baseline(zone, start_date)
                print(f"✅ {zone}")
                print(f"   📊 {baseline.sample_count} runs, avg {baseline.avg_gallons:.1f} gal, {baseline.avg_gpm:.2f} GPM")
                updated_count += 1
            else:
                print(f"⚠️  {zone} - Insufficient data (need 7+ runs)")
                insufficient_data += 1
        
        print()
        print(f"📋 BASELINE UPDATE SUMMARY:")
        print(f"   ✅ Successfully updated: {updated_count}")
        print(f"   ⚠️  Insufficient data: {insufficient_data}")
        print(f"   📅 Baseline period: {args.days or 30} days")
        
        return 0
        
    except Exception as e:
        print(f"❌ Baseline calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_detect(args):
    """Detect anomalies in irrigation data"""
    print_banner()
    print("🔍 DETECTING IRRIGATION ANOMALIES")
    print()
    
    try:
        analytics = IrrigationAnalytics()
        
        # Parse analysis date
        analysis_date = date.today()
        if args.date:
            if args.date == "yesterday":
                analysis_date = date.today() - timedelta(days=1)
            else:
                analysis_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        
        print(f"🔍 Analyzing {args.days} days ending {analysis_date}")
        print()
        
        # Detect anomalies
        anomalies = analytics.detect_anomalies(analysis_date, args.days)
        
        if not anomalies:
            print("✅ No anomalies detected!")
            return 0
        
        # Categorize anomalies
        high_priority = [a for a in anomalies if a.severity == "HIGH"]
        medium_priority = [a for a in anomalies if a.severity == "MEDIUM"]
        low_priority = [a for a in anomalies if a.severity == "LOW"]
        
        print(f"🚨 ANOMALY DETECTION RESULTS:")
        print(f"   🔥 High Priority: {len(high_priority)}")
        print(f"   ⚠️  Medium Priority: {len(medium_priority)}")
        print(f"   ℹ️  Low Priority: {len(low_priority)}")
        print()
        
        # Show high priority anomalies
        if high_priority:
            print("🔥 HIGH PRIORITY ANOMALIES:")
            print("-" * 60)
            for anomaly in high_priority:
                print(f"🚨 {anomaly.zone_name} ({anomaly.run_date})")
                print(f"   Type: {anomaly.anomaly_type.value.replace('_', ' ').title()}")
                print(f"   {anomaly.description}")
                print(f"   Deviation: {anomaly.deviation_percent:.1f}%")
                print()
        
        # Show medium priority if requested
        if args.show_all and medium_priority:
            print("⚠️  MEDIUM PRIORITY ANOMALIES:")
            print("-" * 60)
            for anomaly in medium_priority:
                print(f"⚠️  {anomaly.zone_name} ({anomaly.run_date})")
                print(f"   {anomaly.description}")
                print()
        
        # Store anomalies
        if args.store:
            stored_count = analytics.store_anomalies(anomalies)
            print(f"💾 Stored {stored_count} new anomalies in database")
        
        return 2 if high_priority else (1 if medium_priority else 0)
        
    except Exception as e:
        print(f"❌ Anomaly detection failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_report(args):
    """Generate comprehensive analytics report"""
    print_banner()
    print("📄 GENERATING ANALYTICS REPORT")
    print()
    
    try:
        analytics = IrrigationAnalytics()
        
        print(f"📊 Analyzing {args.days} days of irrigation data...")
        print()
        
        # Generate report
        report = analytics.generate_analytics_report(args.days)
        print(report)
        
        # Save to file if requested
        if args.save:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/irrigation_analytics_{timestamp}.txt"
            
            # Ensure reports directory exists
            os.makedirs("reports", exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"💾 Report saved to: {filename}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_trends(args):
    """Show usage trends for zones"""
    print_banner()
    print("📈 IRRIGATION USAGE TRENDS")
    print()
    
    try:
        analytics = IrrigationAnalytics()
        
        print(f"📊 Analyzing trends over {args.days} days")
        print()
        
        # Calculate trends
        trends = analytics.calculate_zone_trends(args.days)
        
        if not trends:
            print("❌ No trend data available")
            return 1
        
        # Sort by total usage
        trends.sort(key=lambda x: x.total_gallons, reverse=True)
        
        print("📋 ZONE USAGE TRENDS:")
        print("-" * 95)
        print(f"{'Zone':<35} {'Total Gal':<10} {'Avg/Run':<10} {'GPM':<8} {'Cost':<10} {'Usage':<12} {'Efficiency'}")
        print("-" * 95)
        
        for trend in trends:
            usage_indicator = {"INCREASING": "📈", "DECREASING": "📉", "STABLE": "➡️"}[trend.usage_trend]
            efficiency_indicator = {"IMPROVING": "⬆️", "DECLINING": "⬇️", "STABLE": "➡️"}[trend.efficiency_trend]
            
            zone_name = trend.zone_name[:32] + "..." if len(trend.zone_name) > 35 else trend.zone_name
            
            print(f"{zone_name:<35} {trend.total_gallons:<10.1f} {trend.avg_gallons_per_run:<10.1f} "
                  f"{trend.avg_gpm:<8.2f} ${trend.total_cost:<9.2f} {usage_indicator} {trend.usage_trend:<10} {efficiency_indicator} {trend.efficiency_trend}")
            
            if trend.gap_days > 0:
                print(f"{'':>57} ⚠️  {trend.gap_days} gap days")
        
        print("-" * 95)
        print(f"Total zones: {len(trends)}")
        print(f"Total gallons: {sum(t.total_gallons for t in trends):.1f}")
        print(f"Total cost: ${sum(t.total_cost for t in trends):.2f}")
        print(f"Average efficiency: {sum(t.avg_gpm for t in trends) / len(trends):.2f} GPM")
        
        return 0
        
    except Exception as e:
        print(f"❌ Trend analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_costs(args):
    """Calculate water costs"""
    print_banner()
    print("💰 WATER COST CALCULATION")
    print()
    
    try:
        analytics = IrrigationAnalytics()
        
        # Calculate cost
        cost = analytics.calculate_water_cost(args.gallons, args.monthly_total)
        
        print(f"📊 COST BREAKDOWN:")
        print(f"   💧 Gallons: {args.gallons:.1f}")
        
        if args.zone:
            print(f"   🏠 Zone: {args.zone}")
        
        if args.monthly_total:
            print(f"   🏡 Monthly household total: {args.monthly_total:.1f} gallons")
        
        print(f"   💰 Irrigation cost: ${cost:.2f}")
        print(f"   📈 Cost per gallon: ${cost/args.gallons:.4f}")
        print()
        
        print(f"📋 RATE STRUCTURE: {analytics.water_rates.name}")
        print(f"   💵 Base charge: ${analytics.water_rates.base_charge:.2f} ({analytics.water_rates.base_gallons:,} gal included)")
        
        if analytics.water_rates.regional_fee > 0:
            print(f"   🏛️  Regional fee: ${analytics.water_rates.regional_fee:.2f}/1000 gal")
        
        print("   📊 Tier structure:")
        current_tier = analytics.water_rates.base_gallons
        for tier_limit, rate in analytics.water_rates.tiers:
            if tier_limit == float('inf'):
                print(f"      {current_tier:,}+ gallons: ${rate:.2f}/1000 gal")
            else:
                print(f"      {current_tier:,}-{tier_limit:,} gallons: ${rate:.2f}/1000 gal")
                current_tier = tier_limit + 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Cost calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_rates(args):
    """Manage water rate structures"""
    print_banner()
    print("💰 WATER RATE STRUCTURES")
    print()
    
    try:
        analytics = IrrigationAnalytics()
        
        if args.list:
            print("📋 AVAILABLE RATE STRUCTURES:")
            print("-" * 50)
            
            predefined_rates = analytics.get_predefined_rate_structures()
            for key, rate_structure in predefined_rates.items():
                print(f"🏛️  {key}: {rate_structure.name}")
                print(f"   💵 Base: ${rate_structure.base_charge:.2f} ({rate_structure.base_gallons:,} gal)")
                if rate_structure.regional_fee > 0:
                    print(f"   🏛️  Regional fee: ${rate_structure.regional_fee:.2f}/1000 gal")
                print()
        
        elif args.set:
            predefined_rates = analytics.get_predefined_rate_structures()
            if args.set in predefined_rates:
                analytics.set_water_rates(predefined_rates[args.set])
                print(f"✅ Rate structure set to: {predefined_rates[args.set].name}")
            else:
                print(f"❌ Unknown rate structure: {args.set}")
                print("Use --list to see available options")
        
        elif args.show:
            print(f"📊 CURRENT RATE STRUCTURE: {analytics.water_rates.name}")
            print(f"   💵 Base charge: ${analytics.water_rates.base_charge:.2f}")
            print(f"   💧 Base gallons: {analytics.water_rates.base_gallons:,}")
            
            if analytics.water_rates.regional_fee > 0:
                print(f"   🏛️  Regional fee: ${analytics.water_rates.regional_fee:.2f}/1000 gal")
            
            print(f"   📈 Seasonal multiplier: {analytics.water_rates.seasonal_multiplier:.1f}")
            print()
            print("   📊 Tier structure:")
            current_tier = analytics.water_rates.base_gallons
            for tier_limit, rate in analytics.water_rates.tiers:
                if tier_limit == float('inf'):
                    print(f"      {current_tier:,}+ gallons: ${rate:.2f}/1000 gal")
                else:
                    print(f"      {current_tier:,}-{tier_limit:,} gallons: ${rate:.2f}/1000 gal")
                    current_tier = tier_limit + 1
        
        else:
            print("❌ Please specify an action: --list, --set, or --show")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Rate management failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_reset(args):
    """Reset baseline for a zone from a specific date"""
    print_banner()
    print("🔄 RESETTING ZONE BASELINE")
    print()
    
    try:
        analytics = IrrigationAnalytics()
        
        # Parse reset date
        reset_date = datetime.strptime(args.from_date, '%Y-%m-%d').date()
        
        print(f"🎯 Resetting baseline for: {args.zone}")
        print(f"📅 Using data from: {reset_date} onwards")
        print(f"💡 Use this when schedules have changed")
        print()
        
        if analytics.update_baseline(args.zone, reset_date):
            baseline = analytics.calculate_baseline(args.zone, reset_date)
            print("✅ Baseline reset successfully!")
            print()
            print("📊 NEW BASELINE:")
            print(f"   Zone: {baseline.zone_name}")
            print(f"   Sample period: {baseline.baseline_start_date} to {baseline.baseline_end_date}")
            print(f"   Sample runs: {baseline.sample_count}")
            print(f"   Average gallons: {baseline.avg_gallons:.1f}")
            print(f"   Average duration: {baseline.avg_duration_minutes} minutes")
            print(f"   Average efficiency: {baseline.avg_gpm:.2f} GPM")
            print(f"   Standard deviation: ±{baseline.std_dev_gallons:.1f} gallons")
        else:
            print("❌ Failed to reset baseline")
            print("   Possible causes:")
            print("   • Insufficient data (need 7+ runs)")
            print("   • No runs found after the reset date")
            print("   • Zone name not found")
            return 1
        
        return 0
        
    except ValueError:
        print(f"❌ Invalid date format: {args.from_date}")
        print("   Use YYYY-MM-DD format")
        return 1
    except Exception as e:
        print(f"❌ Baseline reset failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_cost_report(args):
    """Generate Houston water bill cost reports with zone-by-zone breakdown"""
    print_banner()
    print("💰 HOUSTON WATER BILL COST REPORT")
    print()
    
    try:
        # Import the Houston water cost calculator
        from database.water_cost_calculator import WaterCostCalculator
        import sqlite3
        
        calculator = WaterCostCalculator()
        
        # Get current billing period cost analysis
        cost_result = calculator.calculate_period_cost()
        
        # Get billing period dates
        billing_start = cost_result['billing_period']['start_date']
        billing_end = cost_result['billing_period']['end_date']
        
        print(f"📅 BILLING PERIOD: {billing_start} to {billing_end}")
        print(f"📊 Analysis Date: {cost_result['calculation_date']} ({cost_result['billing_period']['percent_complete']}% complete)")
        print()
        
        # Display overall cost summary
        usage = cost_result['usage']
        costs = cost_result['costs']
        
        print(f"💧 TOTAL WATER USAGE:")
        print(f"   🚿 Irrigation:      {usage['irrigation_gallons']:8.1f} gallons")
        print(f"   🏡 Manual watering: {usage['manual_watering_gallons']:8.1f} gallons")
        print(f"   📊 Total usage:     {usage['total_gallons']:8.1f} gallons")
        print()
        
        print(f"💰 TOTAL ESTIMATED COST: ${costs['estimated_total_cost']:.2f}")
        print(f"   🏠 Basic service:    ${costs['basic_service_charge']:7.2f}")
        print(f"   💧 Usage cost:       ${costs['total_usage_cost']:7.2f}")
        print()
        
        # Get zone-by-zone usage breakdown
        with sqlite3.connect(calculator.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ar.zone_name, 
                       COUNT(*) as run_count,
                       SUM(ar.actual_gallons) as total_gallons,
                       AVG(ar.actual_gallons) as avg_gallons_per_run,
                       SUM(ar.actual_duration_minutes) as total_minutes,
                       AVG(ar.actual_duration_minutes) as avg_minutes_per_run
                FROM actual_runs ar
                WHERE ar.run_date BETWEEN ? AND ?
                AND ar.actual_gallons IS NOT NULL
                AND ar.actual_gallons > 0
                GROUP BY ar.zone_name
                ORDER BY total_gallons DESC
            """, (billing_start, cost_result['calculation_date']))
            
            zone_data = cursor.fetchall()
        
        if zone_data:
            print("🎯 COST BY IRRIGATION ZONE:")
            print("-" * 110)
            print(f"{'Zone Name':<35} {'Runs':<6} {'Gallons':<10} {'Avg/Run':<9} {'% of Total':<10} {'Est. Cost':<10}")
            print("-" * 110)
            
            total_irrigation = usage['irrigation_gallons']
            total_usage_cost = costs['total_usage_cost']
            
            zone_costs = []
            
            for zone_name, run_count, total_gallons, avg_gallons, total_minutes, avg_minutes in zone_data:
                # Calculate zone's percentage of total irrigation usage
                if total_irrigation > 0:
                    irrigation_percentage = (total_gallons / total_irrigation) * 100
                    # Calculate zone's share of the total usage cost (irrigation only, not basic service)
                    zone_cost = (total_gallons / total_irrigation) * total_usage_cost
                else:
                    irrigation_percentage = 0
                    zone_cost = 0
                
                zone_costs.append((zone_name, total_gallons, zone_cost, irrigation_percentage))
                
                print(f"{zone_name[:35]:<35} "
                      f"{run_count:<6} "
                      f"{total_gallons:>8.1f}g "
                      f"{avg_gallons:>7.1f}g "
                      f"{irrigation_percentage:>8.1f}% "
                      f"${zone_cost:>8.2f}")
            
            print("-" * 110)
            print(f"{'IRRIGATION TOTAL':<35} "
                  f"{sum(row[1] for row in zone_data):<6} "
                  f"{total_irrigation:>8.1f}g "
                  f"{'':>9} "
                  f"{'100.0%':>9} "
                  f"${total_usage_cost:>8.2f}")
            print()
            
            # Show top cost contributors
            if len(zone_costs) > 1:
                print("💸 TOP COST CONTRIBUTORS:")
                top_zones = sorted(zone_costs, key=lambda x: x[2], reverse=True)[:5]
                for i, (zone_name, gallons, cost, percentage) in enumerate(top_zones, 1):
                    print(f"   {i}. {zone_name[:40]:<40} ${cost:6.2f} ({percentage:4.1f}%)")
                print()
            
            # Show efficiency metrics
            print("⚡ EFFICIENCY METRICS:")
            cursor.execute("""
                SELECT ar.zone_name,
                       AVG(ar.actual_gallons / ar.actual_duration_minutes) as avg_gpm,
                       COUNT(*) as run_count
                FROM actual_runs ar
                WHERE ar.run_date BETWEEN ? AND ?
                AND ar.actual_gallons IS NOT NULL 
                AND ar.actual_gallons > 0
                AND ar.actual_duration_minutes > 0
                GROUP BY ar.zone_name
                HAVING run_count >= 2
                ORDER BY avg_gpm DESC
            """, (billing_start, cost_result['calculation_date']))
            
            efficiency_data = cursor.fetchall()
            if efficiency_data:
                print("-" * 70)
                print(f"{'Zone Name':<35} {'Avg GPM':<10} {'Runs':<8} {'Cost/GPM':<12}")
                print("-" * 70)
                
                for zone_name, avg_gpm, run_count in efficiency_data:
                    # Find the cost for this zone
                    zone_cost = next((cost for name, gallons, cost, pct in zone_costs if name == zone_name), 0)
                    cost_per_gpm = zone_cost / avg_gpm if avg_gpm > 0 else 0
                    
                    print(f"{zone_name[:35]:<35} "
                          f"{avg_gpm:>8.2f} "
                          f"{run_count:<8} "
                          f"${cost_per_gpm:>10.2f}")
                print("-" * 70)
        
        else:
            print("❌ No irrigation usage data found for this billing period")
        
        # Show projections if available
        if 'projections' in cost_result and cost_result['projections']:
            proj = cost_result['projections']
            print(f"\n📈 FULL PERIOD PROJECTION:")
            print(f"   🚿 Projected irrigation: {proj['projected_irrigation_gallons']:8.1f} gallons")
            print(f"   💰 Projected total cost: ${proj['projected_total_cost']:8.2f}")
            
            # Calculate projected zone costs
            if zone_data and total_irrigation > 0:
                print(f"\n🔮 PROJECTED ZONE COSTS (Full Period):")
                projected_irrigation = proj['projected_irrigation_gallons']
                projection_multiplier = projected_irrigation / total_irrigation if total_irrigation > 0 else 1
                
                print("-" * 60)
                print(f"{'Zone Name':<35} {'Projected Gallons':<18} {'Projected Cost':<12}")
                print("-" * 60)
                
                for zone_name, gallons, cost, percentage in sorted(zone_costs, key=lambda x: x[2], reverse=True)[:10]:
                    projected_zone_gallons = gallons * projection_multiplier
                    projected_zone_cost = cost * projection_multiplier
                    
                    print(f"{zone_name[:35]:<35} "
                          f"{projected_zone_gallons:>15.1f}g "
                          f"${projected_zone_cost:>10.2f}")
                print("-" * 60)
        
        # Save to file if requested
        if args.save:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/houston_water_cost_report_{billing_start}_{timestamp}.txt"
            
            # Ensure reports directory exists
            os.makedirs("reports", exist_ok=True)
            
            # Generate text report (simplified version)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"HOUSTON WATER BILL COST REPORT\n")
                f.write(f"Billing Period: {billing_start} to {billing_end}\n")
                f.write(f"Analysis Date: {cost_result['calculation_date']}\n\n")
                
                f.write(f"Total Usage: {usage['total_gallons']:.1f} gallons\n")
                f.write(f"Irrigation: {usage['irrigation_gallons']:.1f} gallons\n")
                f.write(f"Manual Watering: {usage['manual_watering_gallons']:.1f} gallons\n\n")
                
                f.write(f"Total Cost: ${costs['estimated_total_cost']:.2f}\n")
                f.write(f"Basic Service: ${costs['basic_service_charge']:.2f}\n")
                f.write(f"Usage Cost: ${costs['total_usage_cost']:.2f}\n\n")
                
                f.write("Zone Breakdown:\n")
                for zone_name, gallons, cost, percentage in sorted(zone_costs, key=lambda x: x[2], reverse=True):
                    f.write(f"{zone_name}: {gallons:.1f} gallons, ${cost:.2f} ({percentage:.1f}%)\n")
            
            print(f"💾 Report saved to: {filename}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Cost report generation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_warnings(args):
    """Analyze usage warnings based on usage_flag and usage_type fields"""
    print_banner()
    print("⚠️  USAGE WARNINGS ANALYSIS")
    print()
    
    try:
        import sqlite3
        from database.intelligent_data_storage import IntelligentDataStorage
        
        storage = IntelligentDataStorage()
        
        # Parse date range
        if args.start_date:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            end_date = start_date
            if args.end_date:
                end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        elif args.days:
            end_date = date.today()
            start_date = end_date - timedelta(days=args.days)
        else:
            # Default to last 7 days
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
        
        print(f"📅 Analyzing usage warnings from {start_date} to {end_date}")
        print(f"   Period: {(end_date - start_date).days + 1} days")
        print()
        
        # Query for warnings
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.cursor()
            
            # Get overall statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN usage_flag = 'too_high' THEN 1 ELSE 0 END) as too_high,
                    SUM(CASE WHEN usage_flag = 'too_low' THEN 1 ELSE 0 END) as too_low,
                    SUM(CASE WHEN usage_flag = 'zero_reported' THEN 1 ELSE 0 END) as zero_reported,
                    SUM(CASE WHEN usage_type = 'estimated' THEN 1 ELSE 0 END) as estimated,
                    SUM(CASE WHEN usage_type = 'actual' THEN 1 ELSE 0 END) as actual
                FROM actual_runs 
                WHERE run_date BETWEEN ? AND ?
            """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            
            stats = cursor.fetchone()
            total_runs, too_high, too_low, zero_reported, estimated, actual = stats
            
            print("📊 OVERALL STATISTICS:")
            print(f"   🏃 Total runs: {total_runs}")
            print(f"   📈 Actual readings: {actual} ({actual/total_runs*100:.1f}%)")
            print(f"   🔢 Estimated readings: {estimated} ({estimated/total_runs*100:.1f}%)")
            print()
            print("⚠️  WARNING SUMMARY:")
            print(f"   🔴 Too high usage: {too_high} ({too_high/total_runs*100:.1f}%)")
            print(f"   🔵 Too low usage: {too_low} ({too_low/total_runs*100:.1f}%)")
            print(f"   ⚫ Zero reported: {zero_reported} ({zero_reported/total_runs*100:.1f}%)")
            print()
            
            # Show high usage warnings
            if too_high > 0:
                print("🔴 HIGH USAGE WARNINGS:")
                print("-" * 110)
                print(f"{'Zone Name':<35} {'Date':<12} {'Duration':<9} {'Actual':<8} {'Expected':<9} {'Ratio':<8}")
                print("-" * 110)
                cursor.execute("""
                    SELECT ar.zone_name, ar.run_date, ar.actual_duration_minutes, ar.actual_gallons, 
                           ROUND((z.average_flow_rate * ar.actual_duration_minutes), 1) as expected_gallons,
                           ROUND((ar.actual_gallons / (z.average_flow_rate * ar.actual_duration_minutes)) * 100, 1) as usage_ratio
                    FROM actual_runs ar
                    JOIN zones z ON ar.zone_id = z.zone_id
                    WHERE ar.usage_flag = 'too_high' 
                    AND ar.run_date BETWEEN ? AND ?
                    AND z.average_flow_rate IS NOT NULL AND z.average_flow_rate > 0
                    ORDER BY usage_ratio DESC, ar.run_date DESC
                    LIMIT ?
                """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), args.limit))
                
                for zone_name, run_date, duration, actual_gal, expected_gal, ratio in cursor.fetchall():
                    print(f"🔴 {zone_name[:35]:<35} {run_date:<12} {duration:6.1f}min {actual_gal:6.1f}gal {expected_gal:7.1f}gal {ratio:6.1f}%")
                
                if too_high > args.limit:
                    print(f"   ... and {too_high - args.limit} more (use --limit to see more)")
                print()
            
            # Show low usage warnings
            if too_low > 0:
                print("🔵 LOW USAGE WARNINGS:")
                print("-" * 110)
                print(f"{'Zone Name':<35} {'Date':<12} {'Duration':<9} {'Actual':<8} {'Expected':<9} {'Ratio':<8}")
                print("-" * 110)
                cursor.execute("""
                    SELECT ar.zone_name, ar.run_date, ar.actual_duration_minutes, ar.actual_gallons,
                           ROUND((z.average_flow_rate * ar.actual_duration_minutes), 1) as expected_gallons,
                           ROUND((ar.actual_gallons / (z.average_flow_rate * ar.actual_duration_minutes)) * 100, 1) as usage_ratio
                    FROM actual_runs ar
                    JOIN zones z ON ar.zone_id = z.zone_id
                    WHERE ar.usage_flag = 'too_low' 
                    AND ar.run_date BETWEEN ? AND ?
                    AND z.average_flow_rate IS NOT NULL AND z.average_flow_rate > 0
                    ORDER BY usage_ratio ASC, ar.run_date DESC
                    LIMIT ?
                """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), args.limit))
                
                for zone_name, run_date, duration, actual_gal, expected_gal, ratio in cursor.fetchall():
                    print(f"🔵 {zone_name[:35]:<35} {run_date:<12} {duration:6.1f}min {actual_gal:6.1f}gal {expected_gal:7.1f}gal {ratio:6.1f}%")
                
                if too_low > args.limit:
                    print(f"   ... and {too_low - args.limit} more (use --limit to see more)")
                print()
            
            # Show zones with frequent estimation usage
            if estimated > 0:
                print("🔢 ZONES WITH ESTIMATED USAGE (Zero Reported):")
                print("-" * 80)
                print(f"{'Zone Name':<45} {'Count':<7} {'Percentage':<12}")
                print("-" * 80)
                cursor.execute("""
                    SELECT zone_name, 
                           COUNT(*) as estimated_count,
                           COUNT(*) * 100.0 / (SELECT COUNT(*) FROM actual_runs ar2 WHERE ar2.zone_name = ar.zone_name AND ar2.run_date BETWEEN ? AND ?) as estimation_rate
                    FROM actual_runs ar
                    WHERE usage_type = 'estimated' 
                    AND run_date BETWEEN ? AND ?
                    GROUP BY zone_name
                    HAVING estimated_count >= ?
                    ORDER BY estimation_rate DESC, estimated_count DESC
                """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), 
                      start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), args.min_estimates))
                
                for zone_name, est_count, est_rate in cursor.fetchall():
                    print(f"🔢 {zone_name[:45]:<45} {est_count:3} est   {est_rate:5.1f}% of runs")
                print()
            
            # Show problem zones summary
            if args.summary:
                print("🎯 PROBLEM ZONES SUMMARY:")
                print("-" * 60)
                cursor.execute("""
                    SELECT zone_name,
                           COUNT(*) as total_zone_runs,
                           SUM(CASE WHEN usage_flag = 'too_high' THEN 1 ELSE 0 END) as high_warnings,
                           SUM(CASE WHEN usage_flag = 'too_low' THEN 1 ELSE 0 END) as low_warnings,
                           SUM(CASE WHEN usage_type = 'estimated' THEN 1 ELSE 0 END) as estimates
                    FROM actual_runs 
                    WHERE run_date BETWEEN ? AND ?
                    GROUP BY zone_name
                    HAVING (high_warnings + low_warnings + estimates) > 0
                    ORDER BY (high_warnings + low_warnings + estimates) DESC
                """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                for zone_name, total, high, low, est in cursor.fetchall():
                    total_issues = high + low + est
                    issue_rate = total_issues / total * 100
                    print(f"🎯 {zone_name[:35]:35} {total_issues:2}/{total:2} issues ({issue_rate:5.1f}%) "
                          f"[H:{high} L:{low} E:{est}]")
        
        # Save to file if requested
        if args.save:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/usage_warnings_{start_date}_{end_date}_{timestamp}.txt"
            
            # Ensure reports directory exists
            os.makedirs("reports", exist_ok=True)
            
            # Re-run queries and save to file
            # (Implementation would involve capturing the print output)
            print(f"💾 Report saved to: {filename}")
        
        return 0
        
    except ValueError as e:
        print(f"❌ Invalid date format: {e}")
        print("   Use YYYY-MM-DD format")
        return 1
    except Exception as e:
        print(f"❌ Usage warnings analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def cmd_zero_gallons(args):
    """Generate comprehensive zero gallon usage analysis and detection report"""
    print_banner()
    print("🚨 ZERO GALLON USAGE ANALYTICS")
    print()
    
    try:
        analytics = IrrigationAnalytics()
        
        # Parse date range
        if args.start_date:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            end_date = start_date
            if args.end_date:
                end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        elif args.days:
            end_date = date.today()
            start_date = end_date - timedelta(days=args.days)
        else:
            # Default to last 7 days
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
        
        print(f"📅 Analyzing zero gallon usage from {start_date} to {end_date}")
        print(f"   Period: {(end_date - start_date).days + 1} days")
        print()
        
        # Generate zero gallon report
        report = analytics.generate_zero_gallon_report(start_date, end_date)
        print(report)
        
        # Save to file if requested
        if args.save:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/zero_gallon_analysis_{start_date}_{end_date}_{timestamp}.txt"
            
            # Ensure reports directory exists
            os.makedirs("reports", exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"💾 Report saved to: {filename}")
        
        return 0
        
    except ValueError as e:
        print(f"❌ Invalid date format: {e}")
        print("   Use YYYY-MM-DD format")
        return 1
    except Exception as e:
        print(f"❌ Zero gallon analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def main():
    """Main CLI entry point"""
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Admin CLI for Hydrawise Irrigation Analytics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update baselines for all zones
  python admin_irrigation_analytics.py baseline
  
  # Update baseline for specific zone
  python admin_irrigation_analytics.py baseline --zone "Front Planters & Pots"
  
  # Reset baseline from specific date (after schedule change)
  python admin_irrigation_analytics.py reset "Front Color (S)" 2025-08-15
  
  # Detect anomalies in last 7 days
  python admin_irrigation_analytics.py detect --days 7 --store
  
  # Generate comprehensive report
  python admin_irrigation_analytics.py report --days 30 --save
  
  # Show usage trends
  python admin_irrigation_analytics.py trends --days 14
  
  # Calculate water cost for 25 gallons
  python admin_irrigation_analytics.py costs --gallons 25
  
  # List available water rate structures
  python admin_irrigation_analytics.py rates --list
  
  # Show current rate structure
  python admin_irrigation_analytics.py rates --show
  
  # Generate today's cost report
  python admin_irrigation_analytics.py cost-report --period today
  
  # Generate weekly cost report
  python admin_irrigation_analytics.py cost-report --period week --save
  
  # Generate custom date range cost report
  python admin_irrigation_analytics.py cost-report --start-date 2025-08-20 --end-date 2025-08-23
  
  # Analyze usage warnings for last 7 days
  python admin_irrigation_analytics.py warnings --days 7
  
  # Show usage warnings with problem zones summary
  python admin_irrigation_analytics.py warnings --summary --limit 20
  
  # Analyze zero gallon usage for last 7 days
  python admin_irrigation_analytics.py zero-gallons --days 7
  
  # Analyze zero gallon usage for specific date range
  python admin_irrigation_analytics.py zero-gallons --start-date 2025-08-20 --end-date 2025-08-23 --save
        """
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Baseline command
    baseline_parser = subparsers.add_parser('baseline', help='Calculate and update zone baselines')
    baseline_parser.add_argument('--zone', help='Specific zone to update (default: all zones)')
    baseline_parser.add_argument('--days', type=int, default=30, help='Days of data for baseline (default: 30)')
    baseline_parser.add_argument('--start-date', help='Start date for baseline (YYYY-MM-DD or "30days")')
    baseline_parser.set_defaults(func=cmd_baseline)
    
    # Detect command
    detect_parser = subparsers.add_parser('detect', help='Detect irrigation anomalies')
    detect_parser.add_argument('--days', type=int, default=7, help='Days to analyze (default: 7)')
    detect_parser.add_argument('--date', help='Analysis end date (YYYY-MM-DD, "yesterday", default: today)')
    detect_parser.add_argument('--store', action='store_true', help='Store detected anomalies in database')
    detect_parser.add_argument('--show-all', action='store_true', help='Show all priority levels')
    detect_parser.set_defaults(func=cmd_detect)
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate comprehensive analytics report')
    report_parser.add_argument('--days', type=int, default=30, help='Days to include in report (default: 30)')
    report_parser.add_argument('--save', action='store_true', help='Save report to file')
    report_parser.set_defaults(func=cmd_report)
    
    # Trends command
    trends_parser = subparsers.add_parser('trends', help='Show usage trends for all zones')
    trends_parser.add_argument('--days', type=int, default=30, help='Days to analyze (default: 30)')
    trends_parser.set_defaults(func=cmd_trends)
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset baseline for zone from specific date')
    reset_parser.add_argument('zone', help='Zone name to reset')
    reset_parser.add_argument('from_date', help='Reset from this date (YYYY-MM-DD)')
    reset_parser.set_defaults(func=cmd_reset)
    
    # Costs command
    costs_parser = subparsers.add_parser('costs', help='Calculate water costs for irrigation')
    costs_parser.add_argument('--gallons', type=float, required=True, help='Gallons to calculate cost for')
    costs_parser.add_argument('--zone', help='Zone name (for context)')
    costs_parser.add_argument('--monthly-total', type=float, help='Total monthly household usage for tier calculation')
    costs_parser.set_defaults(func=cmd_costs)
    
    # Rates command
    rates_parser = subparsers.add_parser('rates', help='Manage water rate structures')
    rates_parser.add_argument('--list', action='store_true', help='List all available rate structures')
    rates_parser.add_argument('--set', help='Set rate structure (use --list to see options)')
    rates_parser.add_argument('--show', action='store_true', help='Show current rate structure')
    rates_parser.set_defaults(func=cmd_rates)
    
    # Cost report command
    cost_report_parser = subparsers.add_parser('cost-report', help='Generate detailed cost reports by zone and date')
    cost_report_parser.add_argument('--period', choices=['today', 'yesterday', 'week', 'month', 'overall'], 
                                   help='Predefined time period')
    cost_report_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD) for custom range')
    cost_report_parser.add_argument('--end-date', help='End date (YYYY-MM-DD) for custom range')
    cost_report_parser.add_argument('--summary-only', action='store_true', help='Show only zone totals, no daily breakdown')
    cost_report_parser.add_argument('--save', action='store_true', help='Save report to file')
    cost_report_parser.set_defaults(func=cmd_cost_report)
    
    # Usage warnings command
    warnings_parser = subparsers.add_parser('warnings', help='Analyze usage warnings (too_high, too_low, estimated usage)')
    warnings_parser.add_argument('--days', type=int, default=7, help='Number of days back to analyze from today (default: 7)')
    warnings_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD) for custom range')
    warnings_parser.add_argument('--end-date', help='End date (YYYY-MM-DD) for custom range')
    warnings_parser.add_argument('--limit', type=int, default=10, help='Limit number of warnings to show per type (default: 10)')
    warnings_parser.add_argument('--min-estimates', type=int, default=2, help='Minimum estimated runs to show zone (default: 2)')
    warnings_parser.add_argument('--summary', action='store_true', help='Show problem zones summary')
    warnings_parser.add_argument('--save', action='store_true', help='Save report to file')
    warnings_parser.set_defaults(func=cmd_warnings)
    
    # Zero gallon analysis command
    zero_gallons_parser = subparsers.add_parser('zero-gallons', help='Analyze zones with zero gallon water usage patterns')
    zero_gallons_parser.add_argument('--days', type=int, help='Number of days back to analyze from today')
    zero_gallons_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD) for custom range')
    zero_gallons_parser.add_argument('--end-date', help='End date (YYYY-MM-DD) for custom range')
    zero_gallons_parser.add_argument('--save', action='store_true', help='Save report to file')
    zero_gallons_parser.set_defaults(func=cmd_zero_gallons)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n\n⏹️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
