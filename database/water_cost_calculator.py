#!/usr/bin/env python3
"""
Houston Water Cost Calculator

Calculates estimated water bills based on:
- Houston city water/wastewater tiered rate structure
- Irrigation usage from actual_runs table
- Manual watering allowance (45 gallons/day default)
- Billing period configuration (monthly, starting 1st by default)

Author: AI Assistant
Date: 2025-01-26
"""

import sqlite3
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import os
import sys

# Add project root to path for config imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

class WaterCostCalculator:
    """Calculates water costs based on Houston tiered rate structure"""
    
    def __init__(self, db_path: str = "database/irrigation_data.db", 
                 rates_config_path: str = "config/houston_water_rates.json"):
        """Initialize cost calculator with database and rate configuration"""
        self.db_path = db_path
        self.rates_config_path = rates_config_path
        self.rate_config = self._load_rate_config()
        
    def _load_rate_config(self) -> Dict[str, Any]:
        """Load Houston water rate configuration from JSON file"""
        try:
            with open(self.rates_config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded Houston water rates config from {self.rates_config_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load rate config from {self.rates_config_path}: {e}")
            raise
    
    def get_billing_period_dates(self, target_date: date = None) -> Tuple[date, date]:
        """Get billing period start and end dates for a target date
        
        Args:
            target_date: Date to find billing period for (defaults to today)
            
        Returns:
            Tuple of (billing_start_date, billing_end_date)
        """
        if target_date is None:
            target_date = date.today()
        
        billing_day = self.rate_config['billing_config']['billing_period_start_day']
        
        # Find billing period start
        if target_date.day >= billing_day:
            # Current month billing period
            billing_start = target_date.replace(day=billing_day)
        else:
            # Previous month billing period
            if target_date.month == 1:
                billing_start = target_date.replace(year=target_date.year - 1, month=12, day=billing_day)
            else:
                billing_start = target_date.replace(month=target_date.month - 1, day=billing_day)
        
        # Find billing period end (day before next period starts)
        if billing_start.month == 12:
            next_period_start = billing_start.replace(year=billing_start.year + 1, month=1)
        else:
            next_period_start = billing_start.replace(month=billing_start.month + 1)
        
        billing_end = next_period_start - timedelta(days=1)
        
        return billing_start, billing_end
    
    def get_irrigation_usage(self, billing_start: date, billing_end: date) -> float:
        """Get total irrigation usage for billing period from actual_runs table
        
        Args:
            billing_start: Start date of billing period
            billing_end: End date of billing period
            
        Returns:
            Total irrigation usage in gallons
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COALESCE(SUM(actual_gallons), 0) as total_gallons
                    FROM actual_runs 
                    WHERE run_date BETWEEN ? AND ?
                    AND actual_gallons IS NOT NULL
                """, (billing_start.strftime('%Y-%m-%d'), billing_end.strftime('%Y-%m-%d')))
                
                result = cursor.fetchone()
                irrigation_usage = result[0] if result else 0.0
                
                logger.debug(f"Irrigation usage from {billing_start} to {billing_end}: {irrigation_usage:.1f} gallons")
                return irrigation_usage
                
        except Exception as e:
            logger.error(f"Failed to get irrigation usage: {e}")
            return 0.0
    
    def get_manual_watering_usage(self, billing_start: date, target_date: date) -> float:
        """Calculate manual watering usage based on days since billing period start
        
        Args:
            billing_start: Start date of billing period
            target_date: Current date (or date to calculate for)
            
        Returns:
            Manual watering usage in gallons
        """
        gallons_per_day = self.rate_config['billing_config']['manual_watering_gallons_per_day']
        days_in_period = (target_date - billing_start).days + 1  # Include start day
        manual_usage = gallons_per_day * days_in_period
        
        logger.debug(f"Manual watering: {gallons_per_day} gal/day [SYMBOL] {days_in_period} days = {manual_usage:.1f} gallons")
        return manual_usage
    
    def find_usage_tier(self, total_usage: float) -> Dict[str, Any]:
        """Find the appropriate usage tier for total consumption
        
        Args:
            total_usage: Total water usage in gallons
            
        Returns:
            Dictionary containing tier information and rates
        """
        tiers = self.rate_config['usage_charge_tiers']
        
        for tier in tiers:
            if tier['usage_min'] <= total_usage <= tier['usage_max']:
                logger.debug(f"Usage {total_usage:.1f} gallons falls in tier {tier['tier']} ({tier['usage_min']}-{tier['usage_max']} gallons)")
                return tier
        
        # If no tier found, use the highest tier (should be the last one with high usage_max)
        highest_tier = tiers[-1]
        logger.warning(f"Usage {total_usage:.1f} gallons exceeds all tiers, using highest tier {highest_tier['tier']}")
        return highest_tier
    
    def calculate_period_cost(self, target_date: date = None) -> Dict[str, Any]:
        """Calculate estimated cost for current billing period up to target date
        
        Args:
            target_date: Date to calculate cost through (defaults to today)
            
        Returns:
            Dictionary with cost breakdown and usage details
        """
        if target_date is None:
            target_date = date.today()
        
        # Get billing period dates
        billing_start, billing_end = self.get_billing_period_dates(target_date)
        
        # Get actual usage data
        irrigation_usage = self.get_irrigation_usage(billing_start, target_date)
        manual_usage = self.get_manual_watering_usage(billing_start, target_date)
        total_usage = irrigation_usage + manual_usage
        
        # Find applicable tier and rates
        tier = self.find_usage_tier(total_usage)
        
        # Calculate costs
        basic_service = self.rate_config['basic_service_charge']
        water_cost = total_usage * tier['water_rate_per_gallon']
        wastewater_cost = total_usage * tier['wastewater_rate_per_gallon']
        usage_cost = water_cost + wastewater_cost
        total_cost = basic_service['total'] + usage_cost
        
        # Calculate days in billing period
        days_in_period = (target_date - billing_start).days + 1
        total_days_in_period = (billing_end - billing_start).days + 1
        
        result = {
            'calculation_date': target_date.strftime('%Y-%m-%d'),
            'billing_period': {
                'start_date': billing_start.strftime('%Y-%m-%d'),
                'end_date': billing_end.strftime('%Y-%m-%d'),
                'days_elapsed': days_in_period,
                'total_days': total_days_in_period,
                'percent_complete': round((days_in_period / total_days_in_period) * 100, 1)
            },
            'usage': {
                'irrigation_gallons': round(irrigation_usage, 1),
                'manual_watering_gallons': round(manual_usage, 1),
                'total_gallons': round(total_usage, 1),
                'manual_watering_rate': self.rate_config['billing_config']['manual_watering_gallons_per_day']
            },
            'tier': {
                'tier_number': tier['tier'],
                'tier_range': f"{tier['usage_min']}-{tier['usage_max']} gallons",
                'water_rate_per_gallon': tier['water_rate_per_gallon'],
                'wastewater_rate_per_gallon': tier['wastewater_rate_per_gallon']
            },
            'costs': {
                'basic_service_charge': round(basic_service['total'], 2),
                'water_usage_cost': round(water_cost, 2),
                'wastewater_usage_cost': round(wastewater_cost, 2),
                'total_usage_cost': round(usage_cost, 2),
                'estimated_total_cost': round(total_cost, 2)
            },
            'projections': self._calculate_projections(billing_start, billing_end, target_date, 
                                                     irrigation_usage, manual_usage, tier)
        }
        
        return result
    
    def _calculate_projections(self, billing_start: date, billing_end: date, target_date: date,
                             current_irrigation: float, current_manual: float, 
                             current_tier: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate projected costs for full billing period"""
        
        days_elapsed = (target_date - billing_start).days + 1
        total_days = (billing_end - billing_start).days + 1
        days_remaining = total_days - days_elapsed
        
        if days_elapsed == 0:
            return {}
        
        # Project irrigation usage based on current daily average
        daily_irrigation_avg = current_irrigation / days_elapsed
        projected_irrigation = current_irrigation + (daily_irrigation_avg * days_remaining)
        
        # Project manual watering for full period
        manual_per_day = self.rate_config['billing_config']['manual_watering_gallons_per_day']
        projected_manual = manual_per_day * total_days
        
        projected_total = projected_irrigation + projected_manual
        
        # Find tier for projected usage
        projected_tier = self.find_usage_tier(projected_total)
        
        # Calculate projected costs
        basic_service = self.rate_config['basic_service_charge']['total']
        projected_water_cost = projected_total * projected_tier['water_rate_per_gallon']
        projected_wastewater_cost = projected_total * projected_tier['wastewater_rate_per_gallon']
        projected_total_cost = basic_service + projected_water_cost + projected_wastewater_cost
        
        return {
            'projected_irrigation_gallons': round(projected_irrigation, 1),
            'projected_manual_gallons': round(projected_manual, 1),
            'projected_total_gallons': round(projected_total, 1),
            'projected_tier_number': projected_tier['tier'],
            'projected_total_cost': round(projected_total_cost, 2),
            'daily_irrigation_average': round(daily_irrigation_avg, 1)
        }
    
    def get_historical_costs(self, num_periods: int = 6) -> List[Dict[str, Any]]:
        """Get cost calculations for previous billing periods
        
        Args:
            num_periods: Number of previous periods to calculate
            
        Returns:
            List of cost calculation results for historical periods
        """
        results = []
        current_date = date.today()
        
        for i in range(num_periods):
            # Go back i months
            if current_date.month > i:
                period_date = current_date.replace(month=current_date.month - i)
            else:
                year_diff = (i - current_date.month) // 12 + 1
                month_diff = (i - current_date.month) % 12
                period_date = current_date.replace(
                    year=current_date.year - year_diff,
                    month=12 - month_diff if month_diff > 0 else 12
                )
            
            # Calculate for the end of that billing period
            billing_start, billing_end = self.get_billing_period_dates(period_date)
            period_result = self.calculate_period_cost(billing_end)
            period_result['period_label'] = f"{billing_start.strftime('%Y-%m')}"
            results.append(period_result)
        
        return results[::-1]  # Return in chronological order
    
    def store_cost_calculation(self, cost_data: Dict[str, Any]) -> None:
        """Store cost calculation in database for historical tracking"""
        # This will be implemented when we add the cost tracking tables
        pass
    
    def sync_rates_to_database(self) -> None:
        """Sync rate configuration to database for backup and historical tracking"""
        # This will be implemented when we add the cost tracking tables
        pass

if __name__ == "__main__":
    # Test the cost calculator
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    calculator = WaterCostCalculator()
    
    # Test current period calculation
    print("[SYMBOL] HOUSTON WATER COST CALCULATOR TEST")
    print("=" * 50)
    
    result = calculator.calculate_period_cost()
    
    print(f"[DATE] Billing Period: {result['billing_period']['start_date']} to {result['billing_period']['end_date']}")
    print(f"[RESULTS] Progress: {result['billing_period']['percent_complete']}% complete")
    print(f"\n[WATER] Usage:")
    print(f"   Irrigation: {result['usage']['irrigation_gallons']} gallons")
    print(f"   Manual watering: {result['usage']['manual_watering_gallons']} gallons")
    print(f"   Total: {result['usage']['total_gallons']} gallons")
    print(f"\n[SYMBOL] Costs:")
    print(f"   Basic service: ${result['costs']['basic_service_charge']}")
    print(f"   Water usage: ${result['costs']['water_usage_cost']}")
    print(f"   Wastewater usage: ${result['costs']['wastewater_usage_cost']}")
    print(f"   Total estimated: ${result['costs']['estimated_total_cost']}")
    
    if 'projections' in result and result['projections']:
        print(f"\n[SYMBOL] Full Period Projection:")
        print(f"   Projected total usage: {result['projections']['projected_total_gallons']} gallons")
        print(f"   Projected total cost: ${result['projections']['projected_total_cost']}")
