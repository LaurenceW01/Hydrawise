#!/usr/bin/env python3
"""
Reset Daily Usage Analytics Report Start Date

This script resets the daily usage analytics system to start from September 13, 2025,
with proper progressive buildup to 30 days.

Logic:
- Start date: 2025-09-13
- Current date: 2025-09-15 
- Days since start: 3 days (9/13 to 9/15)
- Progressive buildup: Start with 2 days, add 1 day each report, cap at 30 days

Author: AI Assistant
Date: 2025-09-15
"""

import os
import sys
import logging
from datetime import datetime, date

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database_manager import get_universal_database_manager
from utils.timezone_utils import get_houston_now

logger = logging.getLogger(__name__)

def reset_daily_report_start_date():
    """Reset the daily report system to start from 9/13/2025"""
    try:
        db_manager = get_universal_database_manager()
        
        # Define the start date for reporting
        start_date = date(2025, 9, 13)
        current_date = get_houston_now().date()
        
        # Calculate days since start date
        days_since_start = (current_date - start_date).days + 1  # +1 to include start date
        
        # Progressive buildup logic:
        # - Start with 2 days minimum
        # - Add 1 day for each day since start (after the first day)
        # - Cap at 30 days maximum
        
        if days_since_start <= 1:
            # First day - start with 2 days
            current_analysis_days = 2
        else:
            # Progressive buildup: 2 + (days_since_start - 1), capped at 30
            current_analysis_days = min(2 + (days_since_start - 1), 30)
        
        logger.info(f"Start date: {start_date}")
        logger.info(f"Current date: {current_date}")
        logger.info(f"Days since start: {days_since_start}")
        logger.info(f"Setting analysis window to: {current_analysis_days} days")
        
        # Update the system config to set the current analysis window
        db_manager.adapter.execute_update("""
            INSERT INTO system_config (config_key, config_value, updated_at)
            VALUES ('daily_report_analysis_days', %s, %s)
            ON CONFLICT (config_key) 
            DO UPDATE SET 
                config_value = EXCLUDED.config_value,
                updated_at = EXCLUDED.updated_at
        """, (str(current_analysis_days), get_houston_now()))
        
        # Also set the start date for reference
        db_manager.adapter.execute_update("""
            INSERT INTO system_config (config_key, config_value, updated_at)
            VALUES ('daily_report_start_date', %s, %s)
            ON CONFLICT (config_key) 
            DO UPDATE SET 
                config_value = EXCLUDED.config_value,
                updated_at = EXCLUDED.updated_at
        """, (start_date.isoformat(), get_houston_now()))
        
        # Clear any previous "already sent today" markers to allow fresh start
        db_manager.adapter.execute_update("""
            DELETE FROM system_config 
            WHERE config_key = 'last_daily_usage_report_date'
        """)
        
        logger.info("Daily report system reset successfully")
        logger.info(f"Next report will analyze {current_analysis_days} days from {start_date}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error resetting daily report start date: {e}")
        return False

def main():
    """Main function"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Resetting daily usage analytics report start date...")
    
    success = reset_daily_report_start_date()
    
    if success:
        logger.info("Reset completed successfully")
        print("\n✅ Daily report system reset to start from September 13, 2025")
        print("📊 Progressive buildup configured properly")
        print("📧 Ready to send reports with correct date range")
        return 0
    else:
        logger.error("Reset failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())



