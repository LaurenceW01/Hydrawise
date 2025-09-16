#!/usr/bin/env python3
"""
Integration script to add daily usage analytics reports to the automated collector

This script modifies the existing automated collector to include daily usage
analytics email reports with progressive day window expansion.

Author: AI Assistant  
Date: 2025-09-15
"""

import os
import sys
import logging
from datetime import datetime, time as dt_time

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daily_usage_analytics_report import DailyUsageAnalyticsReporter, load_config_from_env
# Using basic logging instead of universal_logging
from utils.timezone_utils import get_houston_now

logger = logging.getLogger(__name__)

class DailyAnalyticsIntegration:
    """
    Integration class to add daily analytics to automated collector
    
    This class can be imported and used by the automated collector
    to add daily usage analytics reporting functionality.
    """
    
    def __init__(self):
        """Initialize the integration"""
        self.config = load_config_from_env()
        self.reporter = None
        
        if self.config.enabled:
            self.reporter = DailyUsageAnalyticsReporter(self.config)
            logger.info("Daily usage analytics integration initialized")
        else:
            logger.info("Daily usage analytics integration disabled")
    
    def is_enabled(self) -> bool:
        """Check if daily analytics is enabled"""
        return self.config.enabled and self.reporter is not None
    
    def should_send_daily_report(self) -> bool:
        """
        Check if we should send daily report based on current time
        
        Returns:
            True if current time is after configured report time
        """
        if not self.is_enabled():
            return False
        
        current_time = get_houston_now().time()
        report_time = dt_time(self.config.report_time_hour, 0)
        
        return current_time >= report_time
    
    def send_daily_analytics_report(self, force: bool = False) -> bool:
        """
        Send daily usage analytics report
        
        Args:
            force: Force send even if already sent today
            
        Returns:
            True if report was sent successfully, False otherwise
        """
        if not self.is_enabled():
            logger.debug("Daily analytics not enabled")
            return False
        
        try:
            success = self.reporter.send_daily_report(force=force)
            
            if success:
                logger.info("[ANALYTICS] Daily usage analytics report sent successfully")
            else:
                logger.warning("[ANALYTICS] Failed to send daily usage analytics report")
            
            return success
            
        except Exception as e:
            logger.error(f"[ANALYTICS] Error sending daily analytics report: {e}")
            return False
    
    def get_current_analysis_window(self) -> int:
        """Get current analysis window size"""
        if not self.is_enabled():
            return 0
        
        return self.reporter._get_current_analysis_window()
    
    def get_status(self) -> dict:
        """Get integration status"""
        if not self.is_enabled():
            return {
                "enabled": False,
                "reason": "Daily analytics disabled in configuration"
            }
        
        return {
            "enabled": True,
            "email_configured": self.reporter.email_manager is not None,
            "current_analysis_days": self.get_current_analysis_window(),
            "max_analysis_days": self.config.max_days,
            "report_time_hour": self.config.report_time_hour,
            "email_recipients": len(self.config.email_recipients)
        }

def integrate_with_automated_collector():
    """
    Function to integrate daily analytics with automated collector
    
    This function can be called from automated_collector.py to add
    daily analytics functionality.
    
    Returns:
        DailyAnalyticsIntegration instance
    """
    try:
        integration = DailyAnalyticsIntegration()
        
        if integration.is_enabled():
            logger.info("[INTEGRATION] Daily usage analytics integration active")
            status = integration.get_status()
            logger.info(f"[INTEGRATION] Analysis window: {status['current_analysis_days']}/{status['max_analysis_days']} days")
            logger.info(f"[INTEGRATION] Report time: {status['report_time_hour']}:00 Houston time")
            logger.info(f"[INTEGRATION] Email recipients: {status['email_recipients']}")
        else:
            logger.info("[INTEGRATION] Daily usage analytics integration disabled")
        
        return integration
        
    except Exception as e:
        logger.error(f"[INTEGRATION] Error initializing daily analytics integration: {e}")
        return None

def add_to_daily_collection(integration: DailyAnalyticsIntegration) -> bool:
    """
    Add daily analytics to daily collection process
    
    This function should be called during the daily collection process
    in automated_collector.py
    
    Args:
        integration: DailyAnalyticsIntegration instance
        
    Returns:
        True if analytics were processed successfully
    """
    if not integration or not integration.is_enabled():
        return True  # Not an error if disabled
    
    try:
        # Check if it's time to send daily report
        if integration.should_send_daily_report():
            logger.info("[DAILY COLLECTION] Sending daily usage analytics report...")
            success = integration.send_daily_analytics_report()
            
            if success:
                logger.info("[DAILY COLLECTION] Daily analytics report sent successfully")
            else:
                logger.warning("[DAILY COLLECTION] Daily analytics report failed to send")
            
            return success
        else:
            current_hour = get_houston_now().hour
            report_hour = integration.config.report_time_hour
            logger.info(f"[DAILY COLLECTION] Daily analytics report scheduled for {report_hour}:00, current time is {current_hour}:xx")
            return True
            
    except Exception as e:
        logger.error(f"[DAILY COLLECTION] Error processing daily analytics: {e}")
        return False

def main():
    """Test the integration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Testing daily usage analytics integration...")
    
    # Test integration
    integration = integrate_with_automated_collector()
    
    if integration:
        status = integration.get_status()
        print("\nDaily Usage Analytics Integration Status:")
        print("=" * 50)
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        if integration.is_enabled():
            print(f"\nNext report will analyze {status['current_analysis_days']} days")
            print(f"Report will be sent at {status['report_time_hour']}:00 Houston time")
            
            # Test daily collection integration
            print("\nTesting daily collection integration...")
            success = add_to_daily_collection(integration)
            print(f"Daily collection integration: {'SUCCESS' if success else 'FAILED'}")
        
        return 0
    else:
        print("Failed to initialize integration")
        return 1

if __name__ == "__main__":
    sys.exit(main())
