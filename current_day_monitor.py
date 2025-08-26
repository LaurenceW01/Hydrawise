#!/usr/bin/env python3
"""
Current Day Irrigation Monitor

Simplified monitoring system focused on today's irrigation schedule and actual runs.
Collects current day data, stores in database, and provides real-time irrigation status.

Author: AI Assistant
Date: 2025-08-21
"""

import os
import sys
import logging
from datetime import datetime, date
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Import our modules
from hydrawise_web_scraper import HydrawiseWebScraper
from database.database_manager import DatabaseManager
from irrigation_failure_detector import IrrigationFailureDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('current_day_monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CurrentDayMonitor:
    """Simplified current day irrigation monitoring system"""
    
    def __init__(self, username: str, password: str):
        """Initialize with credentials"""
        self.username = username
        self.password = password
        self.db = DatabaseManager()
        self.scraper = HydrawiseWebScraper(username, password, headless=True)
        
    def collect_current_status(self) -> Dict[str, any]:
        """
        Collect current day irrigation status
        
        Returns:
            Dictionary with current irrigation status
        """
        today = date.today()
        now = datetime.now()
        
        logger.info(f"Collecting current irrigation status for {today}")
        
        results = {
            'collection_time': now,
            'date': today,
            'scheduled_runs': [],
            'actual_runs': [],
            'total_scheduled': 0,
            'total_actual': 0,
            'total_water_delivered': 0.0,
            'success': False,
            'errors': []
        }
        
        try:
            # Collect today's data
            self.scraper.start_browser()
            
            if not self.scraper.login():
                raise Exception("Failed to login to Hydrawise portal")
                
            self.scraper.navigate_to_reports()
            
            # Get scheduled runs for today
            logger.info("Extracting today's scheduled runs...")
            scheduled_runs = self.scraper.extract_scheduled_runs(now)
            results['scheduled_runs'] = scheduled_runs
            results['total_scheduled'] = len(scheduled_runs)
            
            # Get actual runs completed so far today
            logger.info("Extracting today's actual runs...")
            actual_runs = self.scraper.extract_actual_runs(now)
            results['actual_runs'] = actual_runs
            results['total_actual'] = len(actual_runs)
            
            # Calculate total water delivered
            total_water = sum(run.actual_gallons or 0 for run in actual_runs)
            results['total_water_delivered'] = total_water
            
            # Store in database for tracking
            self._store_current_data(scheduled_runs, actual_runs, today)
            
            results['success'] = True
            logger.info(f"Collection successful: {len(scheduled_runs)} scheduled, {len(actual_runs)} actual, {total_water:.1f} gallons delivered")
            
        except Exception as e:
            logger.error(f"Collection failed: {e}")
            results['errors'].append(str(e))
            
        finally:
            try:
                self.scraper.stop_browser()
            except:
                pass
                
        return results
        
    def _store_current_data(self, scheduled_runs: List, actual_runs: List, collection_date: date):
        """Store current data in database"""
        try:
            scheduled_count = self.db.store_scheduled_runs(scheduled_runs, collection_date)
            actual_count = self.db.store_actual_runs(actual_runs, collection_date)
            
            # Log collection
            self.db.log_collection_session(
                collection_type='current_day_monitor',
                scheduled_count=scheduled_count,
                actual_count=actual_count
            )
            
            logger.info(f"Stored {scheduled_count} scheduled and {actual_count} actual runs")
            
        except Exception as e:
            logger.error(f"Failed to store data: {e}")
            
    def get_current_irrigation_status(self) -> Dict[str, any]:
        """Get comprehensive current day irrigation status"""
        today = date.today()
        now = datetime.now()
        
        # Get latest data from database
        daily_summary = self.db.get_daily_summary(today)
        active_failures = self.db.get_active_failures()
        
        # Analyze current time vs schedule
        current_status = {
            'current_time': now.strftime('%I:%M %p'),
            'date': today,
            'summary': daily_summary,
            'active_failures': active_failures,
            'urgent_actions': []
        }
        
        # Check for urgent actions needed
        critical_failures = [f for f in active_failures if f['severity'] == 'CRITICAL']
        current_status['urgent_actions'] = critical_failures
        
        # Determine overall status
        if critical_failures:
            current_status['overall_status'] = 'CRITICAL'
            current_status['status_message'] = f"{len(critical_failures)} zones need immediate attention"
        elif len(active_failures) > 0:
            current_status['overall_status'] = 'WARNING'
            current_status['status_message'] = f"{len(active_failures)} zones have issues"
        else:
            current_status['overall_status'] = 'HEALTHY'
            current_status['status_message'] = "All zones running normally"
            
        return current_status
        
    def generate_current_status_report(self) -> str:
        """Generate human-readable current status report"""
        status = self.get_current_irrigation_status()
        
        report = []
        report.append("=" * 60)
        report.append("CURRENT DAY IRRIGATION STATUS")
        report.append("=" * 60)
        report.append(f"Date: {status['date']}")
        report.append(f"Time: {status['current_time']}")
        report.append(f"Status: {status['overall_status']}")
        report.append(f"Message: {status['status_message']}")
        report.append("")
        
        # Zone summaries
        if status['summary']['zone_summaries']:
            report.append("ZONE STATUS:")
            report.append("-" * 20)
            for zone in status['summary']['zone_summaries']:
                scheduled = zone['scheduled_runs']
                actual = zone['actual_runs']
                water = zone['actual_gallons'] or 0
                
                status_icon = "[OK]" if zone['run_variance'] == 0 else "[WARNING]" if zone['run_variance'] > 0 else "[ERROR]"
                report.append(f"{status_icon} {zone['zone_name']}: {actual}/{scheduled} runs, {water:.1f} gallons")
        
        # Urgent actions
        if status['urgent_actions']:
            report.append("")
            report.append("[ALERT] URGENT ACTIONS REQUIRED:")
            report.append("-" * 30)
            for action in status['urgent_actions']:
                report.append(f"[SYMBOL] {action['zone_name']}: {action['description']}")
                report.append(f"   Action: {action['recommended_action']}")
                report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
        
    def run_quick_check(self) -> Dict[str, any]:
        """Quick status check without full data collection"""
        logger.info("Running quick irrigation status check")
        
        # Get current status from database
        status = self.get_current_irrigation_status()
        
        # Check if we need fresh data (older than 30 minutes)
        recent_collections = self.db.get_recent_collections(1)
        needs_refresh = True
        
        if recent_collections:
            last_collection = recent_collections[0]
            last_time = datetime.fromisoformat(last_collection['start_time'])
            time_since = (datetime.now() - last_time).total_seconds() / 60  # minutes
            
            if time_since < 30:  # Data is recent enough
                needs_refresh = False
                logger.info(f"Using recent data from {time_since:.0f} minutes ago")
        
        if needs_refresh:
            logger.info("Data is stale, collecting fresh data...")
            collection_results = self.collect_current_status()
            status['fresh_data'] = True
            status['collection_results'] = collection_results
        else:
            status['fresh_data'] = False
            
        return status
        
    def close(self):
        """Clean up resources"""
        self.db.close()
        try:
            self.scraper.stop_browser()
        except:
            pass

def main():
    """Main function for current day monitoring"""
    
    # Load environment variables
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("Error: HYDRAWISE_USER and HYDRAWISE_PASSWORD must be set in .env file")
        return
        
    print("Current Day Irrigation Monitor")
    print("=" * 40)
    
    # Initialize monitor
    monitor = CurrentDayMonitor(username, password)
    
    try:
        # Get current status
        print("Checking current irrigation status...")
        status = monitor.run_quick_check()
        
        # Display status report
        report = monitor.generate_current_status_report()
        print(report)
        
        # Show collection info if fresh data was collected
        if status.get('fresh_data'):
            collection = status['collection_results']
            print(f"\nFresh data collected:")
            print(f"  Scheduled runs: {collection['total_scheduled']}")
            print(f"  Actual runs: {collection['total_actual']}")
            print(f"  Water delivered: {collection['total_water_delivered']:.1f} gallons")
        else:
            print(f"\nUsing recent data from database")
            
        # Summary
        urgent_count = len(status.get('urgent_actions', []))
        if urgent_count > 0:
            print(f"\n[ALERT] {urgent_count} zones need immediate attention!")
        else:
            print(f"\n[OK] No urgent irrigation issues detected")
            
    except Exception as e:
        logger.error(f"Monitor execution failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        monitor.close()

if __name__ == "__main__":
    main()
