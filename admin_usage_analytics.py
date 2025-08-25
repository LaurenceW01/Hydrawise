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
    """Generate cost reports for various time periods"""
    print_banner()
    print("💰 IRRIGATION COST REPORT")
    print()
    
    try:
        analytics = IrrigationAnalytics()
        
        if args.period:
            # Predefined period
            report = analytics.generate_cost_report_for_period(args.period)
        elif args.start_date:
            # Custom date range
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            end_date = start_date
            if args.end_date:
                end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
            
            report = analytics.generate_daily_cost_report(start_date, end_date)
        else:
            # Default to today
            report = analytics.generate_cost_report_for_period('today')
        
        # Format and display report
        show_daily = not args.summary_only
        formatted_report = analytics.format_cost_report(report, show_daily_detail=show_daily)
        print(formatted_report)
        
        # Save to file if requested
        if args.save:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            period_name = args.period or f"{report.period_start}_{report.period_end}"
            filename = f"reports/irrigation_cost_report_{period_name}_{timestamp}.txt"
            
            # Ensure reports directory exists
            os.makedirs("reports", exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(formatted_report)
            
            print(f"💾 Report saved to: {filename}")
        
        return 0
        
    except ValueError as e:
        print(f"❌ Invalid date format: {e}")
        print("   Use YYYY-MM-DD format")
        return 1
    except Exception as e:
        print(f"❌ Cost report generation failed: {e}")
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
