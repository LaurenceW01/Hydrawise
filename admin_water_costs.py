#!/usr/bin/env python3
"""
Houston Water Cost Analytics Admin Tool

Provides comprehensive water bill cost analysis including:
- Current billing period cost estimates
- Historical cost tracking and trends  
- Cost projections and tier analysis
- Manual watering vs irrigation cost breakdown
- Budget monitoring and alerts

Author: AI Assistant
Date: 2025-01-26
"""

import argparse
import logging
import sys
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.water_cost_calculator import WaterCostCalculator

def print_banner(title: str, icon: str = "[SYMBOL]") -> None:
    """Print a formatted banner for the analytics tool"""
    print("=" * 70)
    print(f"{icon} {title}")
    print("=" * 70)

def setup_logging(log_level: str = 'INFO') -> None:
    """Setup logging configuration"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(levelname)s:%(name)s:%(message)s'
    )

def cmd_current(args) -> None:
    """Show current billing period cost analysis"""
    print_banner("HOUSTON WATER COST ANALYSIS", "[SYMBOL]")
    print("Current Billing Period Cost Analysis\n")
    
    calculator = WaterCostCalculator()
    result = calculator.calculate_period_cost()
    
    # Display billing period info
    period = result['billing_period']
    print(f"[DATE] BILLING PERIOD: {period['start_date']} to {period['end_date']}")
    print(f"[RESULTS] Progress: {period['percent_complete']}% complete ({period['days_elapsed']}/{period['total_days']} days)")
    print()
    
    # Display usage breakdown
    usage = result['usage']
    print(f"[WATER] WATER USAGE TO DATE:")
    print(f"   [SYMBOL] Irrigation:      {usage['irrigation_gallons']:7.1f} gallons")
    print(f"   [SYMBOL] Manual watering: {usage['manual_watering_gallons']:7.1f} gallons ({usage['manual_watering_rate']} gal/day)")
    print(f"   [RESULTS] Total usage:     {usage['total_gallons']:7.1f} gallons")
    print()
    
    # Display tier information
    tier = result['tier']
    print(f"[SYMBOL] RATE TIER: Tier {tier['tier_number']} ({tier['tier_range']})")
    print(f"   [WATER] Water rate:      ${tier['water_rate_per_gallon']:.5f}/gallon")
    print(f"   [HYDRAWISE] Wastewater rate: ${tier['wastewater_rate_per_gallon']:.5f}/gallon")
    print()
    
    # Display cost breakdown
    costs = result['costs']
    print(f"[SYMBOL] COST BREAKDOWN:")
    print(f"   [SYMBOL] Basic service:    ${costs['basic_service_charge']:7.2f}")
    print(f"   [WATER] Water usage:      ${costs['water_usage_cost']:7.2f}")
    print(f"   [HYDRAWISE] Wastewater usage: ${costs['wastewater_usage_cost']:7.2f}")
    print(f"   [SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL][SYMBOL]")
    print(f"   [SYMBOL] Total estimated:  ${costs['estimated_total_cost']:7.2f}")
    print()
    
    # Display projections if available
    if 'projections' in result and result['projections']:
        proj = result['projections']
        print(f"[SYMBOL] FULL PERIOD PROJECTION:")
        print(f"   [SYMBOL] Projected irrigation: {proj['projected_irrigation_gallons']:7.1f} gallons ({proj['daily_irrigation_average']:.1f} gal/day avg)")
        print(f"   [SYMBOL] Projected manual:     {proj['projected_manual_gallons']:7.1f} gallons")
        print(f"   [RESULTS] Projected total:      {proj['projected_total_gallons']:7.1f} gallons")
        print(f"   [SYMBOL] Projected tier:       Tier {proj['projected_tier_number']}")
        print(f"   [SYMBOL] Projected cost:       ${proj['projected_total_cost']:7.2f}")
        
        # Calculate cost increase
        cost_increase = proj['projected_total_cost'] - costs['estimated_total_cost']
        print(f"   [SYMBOL] Expected increase:    ${cost_increase:7.2f}")

def cmd_history(args) -> None:
    """Show historical cost analysis"""
    print_banner("HOUSTON WATER COST HISTORY", "[RESULTS]")
    print(f"Historical Cost Analysis (Last {args.periods} Periods)\n")
    
    calculator = WaterCostCalculator()
    history = calculator.get_historical_costs(args.periods)
    
    if not history:
        print("[ERROR] No historical cost data available")
        return
    
    # Display table header
    print("-" * 100)
    print(f"{'Period':<10} {'Days':<5} {'Irrigation':<12} {'Manual':<8} {'Total':<8} {'Tier':<6} {'Total Cost':<12}")
    print("-" * 100)
    
    # Display historical data
    for period_data in history:
        period = period_data['period_label']
        billing_info = period_data['billing_period']
        usage = period_data['usage']
        tier = period_data['tier']
        costs = period_data['costs']
        
        print(f"{period:<10} "
              f"{billing_info['total_days']:<5} "
              f"{usage['irrigation_gallons']:>10.1f}g "
              f"{usage['manual_watering_gallons']:>6.1f}g "
              f"{usage['total_gallons']:>6.1f}g "
              f"{tier['tier_number']:<6} "
              f"${costs['estimated_total_cost']:>10.2f}")
    
    print("-" * 100)
    
    if len(history) >= 2:
        # Calculate trends
        latest = history[-1]
        previous = history[-2]
        
        cost_change = latest['costs']['estimated_total_cost'] - previous['costs']['estimated_total_cost']
        usage_change = latest['usage']['total_gallons'] - previous['usage']['total_gallons']
        irrigation_change = latest['usage']['irrigation_gallons'] - previous['usage']['irrigation_gallons']
        
        print(f"\n[SYMBOL] MONTH-OVER-MONTH TRENDS:")
        print(f"   [SYMBOL] Cost change:       ${cost_change:+7.2f}")
        print(f"   [WATER] Usage change:      {usage_change:+7.1f} gallons")
        print(f"   [SYMBOL] Irrigation change: {irrigation_change:+7.1f} gallons")

def cmd_tier_analysis(args) -> None:
    """Analyze cost implications of different usage tiers"""
    print_banner("HOUSTON WATER TIER ANALYSIS", "[SYMBOL]")
    print("Usage Tier Cost Analysis\n")
    
    calculator = WaterCostCalculator()
    current_result = calculator.calculate_period_cost()
    current_usage = current_result['usage']['total_gallons']
    
    # Load tier information
    tiers = calculator.rate_config['usage_charge_tiers']
    basic_service = calculator.rate_config['basic_service_charge']['total']
    
    print(f"Current usage: {current_usage:.1f} gallons (Tier {current_result['tier']['tier_number']})")
    print(f"Current estimated cost: ${current_result['costs']['estimated_total_cost']:.2f}\n")
    
    # Display tier analysis table
    print("-" * 110)
    print(f"{'Tier':<6} {'Usage Range':<20} {'Water Rate':<12} {'Wastewater Rate':<15} {'Example Cost':<15} {'vs Current':<12}")
    print("-" * 110)
    
    for tier in tiers[:15]:  # Show first 15 tiers
        # Calculate cost for middle of tier range
        if tier['usage_max'] == 999999:
            example_usage = tier['usage_min'] + 1000  # Use min + 1000 for highest tier
        else:
            example_usage = (tier['usage_min'] + tier['usage_max']) / 2
        
        example_cost = basic_service + (example_usage * tier['water_rate_per_gallon']) + (example_usage * tier['wastewater_rate_per_gallon'])
        cost_diff = example_cost - current_result['costs']['estimated_total_cost']
        
        tier_range = f"{tier['usage_min']}-{tier['usage_max']}" if tier['usage_max'] != 999999 else f"{tier['usage_min']}+"
        
        # Highlight current tier
        marker = "->" if tier['tier'] == current_result['tier']['tier_number'] else " "
        
        print(f"{marker} {tier['tier']:<4} "
              f"{tier_range:<20} "
              f"${tier['water_rate_per_gallon']:.5f}/gal "
              f"${tier['wastewater_rate_per_gallon']:.5f}/gal  "
              f"${example_cost:>12.2f}  "
              f"${cost_diff:+10.2f}")
    
    print("-" * 110)
    
    # Show tier change thresholds
    current_tier_num = current_result['tier']['tier_number']
    if current_tier_num < len(tiers):
        next_tier = tiers[current_tier_num]  # Arrays are 0-indexed, but tiers start at 1
        gallons_to_next_tier = next_tier['usage_min'] - current_usage
        
        if gallons_to_next_tier > 0:
            print(f"\n[WARNING]  TIER CHANGE ALERT:")
            print(f"   [SYMBOL] Next tier: Tier {next_tier['tier']} at {next_tier['usage_min']} gallons")
            print(f"   [SYMBOL] Distance: {gallons_to_next_tier:.1f} gallons away")
            print(f"   [SYMBOL] Rate increase: ${next_tier['water_rate_per_gallon']:.5f}/gal water, ${next_tier['wastewater_rate_per_gallon']:.5f}/gal wastewater")

def cmd_budget(args) -> None:
    """Budget monitoring and cost alerts"""
    print_banner("BUDGET MONITORING", "[SYMBOL]")
    
    if args.target_cost:
        print(f"Budget Monitoring (Target: ${args.target_cost:.2f})\n")
    else:
        print("Budget Monitoring\n")
    
    calculator = WaterCostCalculator()
    result = calculator.calculate_period_cost()
    
    current_cost = result['costs']['estimated_total_cost']
    projected_cost = result.get('projections', {}).get('projected_total_cost', current_cost)
    
    print(f"[SYMBOL] Current estimated cost: ${current_cost:.2f}")
    print(f"[SYMBOL] Projected period cost:  ${projected_cost:.2f}")
    
    if args.target_cost:
        remaining_budget = args.target_cost - current_cost
        projected_overage = projected_cost - args.target_cost
        
        print(f"[SYMBOL] Budget target:          ${args.target_cost:.2f}")
        print(f"[SYMBOL] Remaining budget:       ${remaining_budget:.2f}")
        
        if projected_overage > 0:
            print(f"[WARNING]  Projected overage:      ${projected_overage:.2f}")
            
            # Calculate usage reduction needed
            tier = result['tier']
            combined_rate = tier['water_rate_per_gallon'] + tier['wastewater_rate_per_gallon']
            gallons_to_reduce = projected_overage / combined_rate
            
            print(f"\n[SYMBOL] TO STAY ON BUDGET:")
            print(f"   Reduce usage by: {gallons_to_reduce:.0f} gallons")
            
            # Suggest reductions
            manual_savings = args.manual_reduction if args.manual_reduction else 0
            irrigation_needed = gallons_to_reduce - manual_savings
            
            if manual_savings > 0:
                days_remaining = result['billing_period']['total_days'] - result['billing_period']['days_elapsed']
                print(f"   Option 1: Reduce manual watering by {manual_savings:.0f} gallons")
                print(f"   Option 2: Reduce irrigation by {irrigation_needed:.0f} gallons")
                print(f"   Option 3: Combination of both")
        else:
            print(f"[OK] Projected to stay within budget by ${-projected_overage:.2f}")

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description='Houston Water Cost Analytics Admin Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s current                    # Show current period costs
  %(prog)s history --periods 12       # Show 12 months of history  
  %(prog)s tier-analysis              # Analyze tier implications
  %(prog)s budget --target-cost 75    # Monitor budget vs $75 target
  %(prog)s budget --target-cost 60 --manual-reduction 200  # Budget with reduction options
        """
    )
    
    # Global options
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Set logging level')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Current period analysis
    current_parser = subparsers.add_parser('current', help='Show current billing period analysis')
    current_parser.set_defaults(func=cmd_current)
    
    # Historical analysis
    history_parser = subparsers.add_parser('history', help='Show historical cost trends')
    history_parser.add_argument('--periods', type=int, default=6, 
                               help='Number of historical periods to show (default: 6)')
    history_parser.set_defaults(func=cmd_history)
    
    # Tier analysis
    tier_parser = subparsers.add_parser('tier-analysis', help='Analyze usage tier implications')
    tier_parser.set_defaults(func=cmd_tier_analysis)
    
    # Budget monitoring
    budget_parser = subparsers.add_parser('budget', help='Budget monitoring and alerts')
    budget_parser.add_argument('--target-cost', type=float, 
                              help='Target monthly cost for budget monitoring')
    budget_parser.add_argument('--manual-reduction', type=float, 
                              help='Manual watering reduction option (gallons)')
    budget_parser.set_defaults(func=cmd_budget)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Setup logging
    setup_logging(args.log_level)
    
    try:
        # Execute command
        args.func(args)
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        if args.log_level == 'DEBUG':
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
