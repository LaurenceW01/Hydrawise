#!/usr/bin/env python3
"""
Smart Irrigation Monitor

Intelligent current day + 24-hour monitoring system that:
- Only updates data when it's stale
- Preserves historical data
- Manages data freshness based on time and schedule changes
- Provides 24-hour forward-looking schedule view

Author: AI Assistant
Date: 2025-08-21
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Import our modules
from hydrawise_web_scraper import HydrawiseWebScraper
from database.database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('smart_irrigation_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SmartIrrigationMonitor:
    """Intelligent irrigation monitoring with smart data freshness management"""
    
    def __init__(self, username: str, password: str):
        """Initialize with credentials"""
        self.username = username
        self.password = password
        self.db = DatabaseManager()
        self.scraper = HydrawiseWebScraper(username, password, headless=True)
        
        # Freshness thresholds (in minutes)
        self.SCHEDULE_FRESHNESS_THRESHOLD = 30  # Schedule data is stale after 30 minutes
        self.ACTUAL_FRESHNESS_THRESHOLD = 15    # Actual data is stale after 15 minutes
        
    def should_refresh_schedule_data(self, target_date: date = None) -> Tuple[bool, str]:
        """
        Determine if schedule data needs refreshing
        
        Returns:
            Tuple of (should_refresh: bool, reason: str)
        """
        if target_date is None:
            target_date = date.today()
            
        try:
            # Check when we last collected schedule data for this date
            recent_collections = self.db.get_recent_collections(1)
            
            if not recent_collections:
                return True, "No previous collections found"
                
            last_collection = recent_collections[0]
            
            # Only consider collections for the target date
            if last_collection['collection_date'] != str(target_date):
                return True, f"No collections found for {target_date}"
                
            # Check if collection was successful
            if last_collection['status'] != 'SUCCESS':
                return True, f"Last collection failed: {last_collection.get('error_details', 'Unknown error')}"
                
            # Check time-based freshness
            last_time = datetime.fromisoformat(last_collection['start_time'])
            time_since_minutes = (datetime.now() - last_time).total_seconds() / 60
            
            if time_since_minutes > self.SCHEDULE_FRESHNESS_THRESHOLD:
                return True, f"Data is {time_since_minutes:.0f} minutes old (threshold: {self.SCHEDULE_FRESHNESS_THRESHOLD})"
                
            # For current day, also check if we're in a different "irrigation window"
            if target_date == date.today():
                current_hour = datetime.now().hour
                last_hour = last_time.hour
                
                # If we've crossed into a new major irrigation period, refresh
                # Major periods: early morning (4-8), mid-day (11-15), evening (17-21)
                current_period = self._get_irrigation_period(current_hour)
                last_period = self._get_irrigation_period(last_hour)
                
                if current_period != last_period:
                    return True, f"Crossed irrigation period boundary: {last_period} -> {current_period}"
                    
            return False, f"Data is fresh ({time_since_minutes:.0f} minutes old)"
            
        except Exception as e:
            logger.error(f"Error checking schedule freshness: {e}")
            return True, f"Error checking freshness: {e}"
            
    def should_refresh_actual_data(self, target_date: date = None) -> Tuple[bool, str]:
        """
        Determine if actual run data needs refreshing
        
        Returns:
            Tuple of (should_refresh: bool, reason: str)
        """
        if target_date is None:
            target_date = date.today()
            
        # For past dates, never refresh actual data (it's historical)
        if target_date < date.today():
            return False, "Historical data - no refresh needed"
            
        try:
            # For current day, check freshness of actual run data
            recent_collections = self.db.get_recent_collections(1)
            
            if not recent_collections:
                return True, "No previous collections found"
                
            last_collection = recent_collections[0]
            
            if last_collection['collection_date'] != str(target_date):
                return True, f"No collections found for {target_date}"
                
            # Check time-based freshness (actual data updates more frequently)
            last_time = datetime.fromisoformat(last_collection['start_time'])
            time_since_minutes = (datetime.now() - last_time).total_seconds() / 60
            
            if time_since_minutes > self.ACTUAL_FRESHNESS_THRESHOLD:
                return True, f"Actual data is {time_since_minutes:.0f} minutes old (threshold: {self.ACTUAL_FRESHNESS_THRESHOLD})"
                
            return False, f"Actual data is fresh ({time_since_minutes:.0f} minutes old)"
            
        except Exception as e:
            logger.error(f"Error checking actual data freshness: {e}")
            return True, f"Error checking freshness: {e}"
            
    def _get_irrigation_period(self, hour: int) -> str:
        """Get irrigation period name for an hour"""
        if 4 <= hour < 8:
            return "early_morning"
        elif 11 <= hour < 15:
            return "mid_day"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "off_hours"
            
    def collect_smart_data(self, include_tomorrow: bool = True) -> Dict[str, any]:
        """
        Smart data collection that only fetches what's needed
        
        Args:
            include_tomorrow: Whether to collect tomorrow's schedule
            
        Returns:
            Dictionary with collection results and freshness info
        """
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        logger.info(f"Starting smart data collection for {today}")
        
        results = {
            'collection_time': datetime.now(),
            'target_dates': [today],
            'data_collected': {
                'today_schedule': [],
                'today_actual': [],
                'tomorrow_schedule': []
            },
            'freshness_checks': {},
            'actions_taken': [],
            'errors': []
        }
        
        if include_tomorrow:
            results['target_dates'].append(tomorrow)
            
        try:
            # Check freshness for today's schedule
            schedule_refresh, schedule_reason = self.should_refresh_schedule_data(today)
            results['freshness_checks']['today_schedule'] = {
                'needs_refresh': schedule_refresh,
                'reason': schedule_reason
            }
            
            # Check freshness for today's actual data
            actual_refresh, actual_reason = self.should_refresh_actual_data(today)
            results['freshness_checks']['today_actual'] = {
                'needs_refresh': actual_refresh,
                'reason': actual_reason
            }
            
            # Check freshness for tomorrow's schedule (if requested)
            if include_tomorrow:
                tomorrow_refresh, tomorrow_reason = self.should_refresh_schedule_data(tomorrow)
                results['freshness_checks']['tomorrow_schedule'] = {
                    'needs_refresh': tomorrow_refresh,
                    'reason': tomorrow_reason
                }
            
            # Determine what data to collect
            collect_today_schedule = schedule_refresh
            collect_today_actual = actual_refresh
            collect_tomorrow_schedule = include_tomorrow and tomorrow_refresh
            
            # If we need to collect any schedule data, use 24-hour collection
            if collect_today_schedule or collect_tomorrow_schedule:
                logger.info("Collecting schedule data using 24-hour method...")
                results['actions_taken'].append("collected_24_hour_schedule")
                
                schedule_data = self._collect_24_hour_schedule_data()
                
                if collect_today_schedule:
                    results['data_collected']['today_schedule'] = schedule_data.get('today', [])
                    self._store_schedule_data(schedule_data.get('today', []), today)
                    
                if collect_tomorrow_schedule:
                    results['data_collected']['tomorrow_schedule'] = schedule_data.get('tomorrow', [])
                    self._store_schedule_data(schedule_data.get('tomorrow', []), tomorrow)
                    
            # Collect today's actual data separately if needed
            if collect_today_actual:
                logger.info("Collecting today's actual run data...")
                results['actions_taken'].append("collected_today_actual")
                
                actual_data = self._collect_actual_data(today)
                results['data_collected']['today_actual'] = actual_data
                self._store_actual_data(actual_data, today)
                
            # If no fresh data was needed, load from database
            if not any([collect_today_schedule, collect_today_actual, collect_tomorrow_schedule]):
                logger.info("All data is fresh, loading from database...")
                results['actions_taken'].append("used_cached_data")
                results['data_collected'] = self._load_cached_data(today, tomorrow if include_tomorrow else None)
                
        except Exception as e:
            logger.error(f"Smart data collection failed: {e}")
            results['errors'].append(str(e))
            
        return results
        
    def _collect_24_hour_schedule_data(self) -> Dict[str, List]:
        """Collect 24-hour schedule data using web scraper"""
        try:
            self.scraper.start_browser()
            if not self.scraper.login():
                raise Exception("Failed to login to Hydrawise portal")
                
            return self.scraper.collect_24_hour_schedule()
            
        finally:
            try:
                self.scraper.stop_browser()
            except:
                pass
                
    def _collect_actual_data(self, target_date: date) -> List:
        """Collect actual run data for a specific date"""
        try:
            self.scraper.start_browser()
            if not self.scraper.login():
                raise Exception("Failed to login to Hydrawise portal")
                
            self.scraper.navigate_to_reports()
            return self.scraper.extract_actual_runs(datetime.combine(target_date, datetime.min.time()))
            
        finally:
            try:
                self.scraper.stop_browser()
            except:
                pass
                
    def _store_schedule_data(self, scheduled_runs: List, target_date: date):
        """Store scheduled runs in database"""
        if scheduled_runs:
            count = self.db.store_scheduled_runs(scheduled_runs, target_date)
            logger.info(f"Stored {count} scheduled runs for {target_date}")
            
    def _store_actual_data(self, actual_runs: List, target_date: date):
        """Store actual runs in database"""
        if actual_runs:
            count = self.db.store_actual_runs(actual_runs, target_date)
            logger.info(f"Stored {count} actual runs for {target_date}")
            
    def _load_cached_data(self, today: date, tomorrow: Optional[date] = None) -> Dict[str, List]:
        """Load cached data from database"""
        cached_data = {
            'today_schedule': [],
            'today_actual': [],
            'tomorrow_schedule': []
        }
        
        # This would require database query methods to retrieve stored runs
        # For now, return empty data structure
        logger.info("Loading cached data from database (placeholder)")
        
        return cached_data
        
    def get_irrigation_status(self) -> Dict[str, any]:
        """Get comprehensive irrigation status with smart data management"""
        
        logger.info("Getting irrigation status with smart data management")
        
        # Collect fresh data as needed
        collection_results = self.collect_smart_data(include_tomorrow=True)
        
        # Get current status from database
        daily_summary = self.db.get_daily_summary()
        active_failures = self.db.get_active_failures()
        
        status = {
            'current_time': datetime.now().strftime('%I:%M %p'),
            'date': date.today(),
            'collection_info': collection_results,
            'summary': daily_summary,
            'active_failures': active_failures,
            'data_freshness': collection_results['freshness_checks'],
            'actions_taken': collection_results['actions_taken']
        }
        
        # Determine overall status
        critical_failures = [f for f in active_failures if f['severity'] == 'CRITICAL']
        if critical_failures:
            status['overall_status'] = 'CRITICAL'
            status['status_message'] = f"{len(critical_failures)} zones need immediate attention"
        elif len(active_failures) > 0:
            status['overall_status'] = 'WARNING'  
            status['status_message'] = f"{len(active_failures)} zones have issues"
        else:
            status['overall_status'] = 'HEALTHY'
            status['status_message'] = "All zones running normally"
            
        return status
        
    def generate_status_report(self) -> str:
        """Generate human-readable status report with data freshness info"""
        
        status = self.get_irrigation_status()
        
        report = []
        report.append("=" * 60)
        report.append("SMART IRRIGATION MONITORING REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {status['current_time']} on {status['date']}")
        report.append(f"Overall Status: {status['overall_status']}")
        report.append(f"Message: {status['status_message']}")
        report.append("")
        
        # Data freshness information
        report.append("DATA FRESHNESS:")
        report.append("-" * 20)
        freshness = status['data_freshness']
        
        for data_type, info in freshness.items():
            refresh_icon = "[PERIODIC]" if info['needs_refresh'] else "[OK]"
            report.append(f"{refresh_icon} {data_type.replace('_', ' ').title()}: {info['reason']}")
            
        report.append("")
        
        # Actions taken
        if status['actions_taken']:
            report.append("ACTIONS TAKEN:")
            report.append("-" * 15)
            for action in status['actions_taken']:
                action_display = action.replace('_', ' ').title()
                report.append(f"- {action_display}")
            report.append("")
        
        # Zone status (if available)
        if status['summary']['zone_summaries']:
            report.append("ZONE STATUS:")
            report.append("-" * 12)
            for zone in status['summary']['zone_summaries'][:10]:  # Show top 10
                scheduled = zone['scheduled_runs']
                actual = zone['actual_runs']
                water = zone['actual_gallons'] or 0
                
                status_icon = "[OK]" if zone['run_variance'] == 0 else "[WARNING]" if zone['run_variance'] > 0 else "[ERROR]"
                report.append(f"{status_icon} {zone['zone_name']}: {actual}/{scheduled} runs, {water:.1f} gallons")
        
        # Active failures
        if status['active_failures']:
            report.append("")
            report.append("[ALERT] ACTIVE FAILURES:")
            report.append("-" * 17)
            for failure in status['active_failures'][:5]:  # Show top 5
                report.append(f"[SYMBOL] {failure['zone_name']}: {failure['description']}")
                report.append(f"   Action: {failure['recommended_action']}")
                report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
        
    def close(self):
        """Clean up resources"""
        self.db.close()
        try:
            self.scraper.stop_browser()
        except:
            pass

def main():
    """Main function for smart irrigation monitoring"""
    
    # Load environment variables
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("Error: HYDRAWISE_USER and HYDRAWISE_PASSWORD must be set in .env file")
        return
        
    print("Smart Irrigation Monitor")
    print("=" * 30)
    
    # Initialize monitor
    monitor = SmartIrrigationMonitor(username, password)
    
    try:
        # Get irrigation status with smart data management
        print("Analyzing irrigation status with smart data management...")
        status = monitor.get_irrigation_status()
        
        # Display report
        report = monitor.generate_status_report()
        print(report)
        
        # Show collection summary
        collection_info = status['collection_info']
        print(f"\nCOLLECTION SUMMARY:")
        print(f"Actions taken: {', '.join(collection_info['actions_taken']) if collection_info['actions_taken'] else 'None (used cached data)'}")
        
        if collection_info['errors']:
            print(f"Errors: {collection_info['errors']}")
        else:
            print(f"Collection successful!")
            
    except Exception as e:
        logger.error(f"Monitor execution failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        monitor.close()

if __name__ == "__main__":
    main()
