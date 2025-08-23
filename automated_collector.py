#!/usr/bin/env python3
"""
Automated Reported Runs Collector

Background service that automatically collects reported runs according to schedule:
- Daily collection at 6:00 AM (previous day + current day)
- Periodic collection every 30 minutes during day (current day deltas)
- Configurable schedule and intervals

Author: AI Assistant  
Date: 2025-08-23
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime, time as dt_time
from typing import Optional
from dataclasses import dataclass

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reported_runs_manager import ReportedRunsManager
from utils.timezone_utils import get_houston_now, get_display_timestamp

@dataclass
class ScheduleConfig:
    """Configuration for automated collection schedule"""
    daily_collection_time: dt_time = dt_time(6, 0)  # 6:00 AM Houston time
    periodic_interval_minutes: int = 30              # Every 30 minutes
    periodic_start_time: dt_time = dt_time(7, 0)     # Start at 7:00 AM
    periodic_end_time: dt_time = dt_time(22, 0)      # End at 10:00 PM
    enabled: bool = True

class AutomatedCollector:
    """
    Automated background collector for reported runs
    """
    
    def __init__(self, config: ScheduleConfig = None):
        """
        Initialize the automated collector
        
        Args:
            config: Schedule configuration (uses defaults if None)
        """
        self.config = config or ScheduleConfig()
        self.running = False
        self.stop_event = threading.Event()
        self.collector_thread = None
        
        # Initialize the reported runs manager
        self.manager = ReportedRunsManager(headless=True)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("AutomatedCollector initialized")
    
    def start(self):
        """Start the automated collection service"""
        if self.running:
            self.logger.warning("Automated collector is already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        # Start the collection thread
        self.collector_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collector_thread.start()
        
        self.logger.info("🚀 Automated collection service started")
        self.logger.info(f"   Daily collection: {self.config.daily_collection_time.strftime('%I:%M %p')} Houston time")
        self.logger.info(f"   Periodic collection: Every {self.config.periodic_interval_minutes} minutes")
        self.logger.info(f"   Periodic hours: {self.config.periodic_start_time.strftime('%I:%M %p')} - {self.config.periodic_end_time.strftime('%I:%M %p')}")
    
    def stop(self):
        """Stop the automated collection service"""
        if not self.running:
            return
        
        self.logger.info("🛑 Stopping automated collection service...")
        self.running = False
        self.stop_event.set()
        
        # Wait for thread to finish
        if self.collector_thread and self.collector_thread.is_alive():
            self.collector_thread.join(timeout=10)
        
        self.logger.info("✅ Automated collection service stopped")
    
    def _collection_loop(self):
        """Main collection loop (runs in background thread)"""
        last_daily_date = None
        last_periodic_time = None
        
        self.logger.info("🔄 Collection loop started")
        
        while self.running and not self.stop_event.is_set():
            try:
                now = get_houston_now()
                current_date = now.date()
                current_time = now.time()
                
                # Check for daily collection
                if self._should_run_daily_collection(current_time, current_date, last_daily_date):
                    self.logger.info(f"🌅 Running scheduled daily collection at {get_display_timestamp(now)}")
                    
                    try:
                        result = self.manager.collect_daily()
                        if result.success:
                            self.logger.info(f"✅ Daily collection completed: {result.runs_collected} collected, {result.runs_stored} stored")
                            last_daily_date = current_date
                        else:
                            self.logger.error(f"❌ Daily collection failed: {result.errors}")
                    except Exception as e:
                        self.logger.error(f"❌ Daily collection error: {e}")
                
                # Check for periodic collection
                if self._should_run_periodic_collection(current_time, now, last_periodic_time):
                    self.logger.info(f"🔄 Running scheduled periodic collection at {get_display_timestamp(now)}")
                    
                    try:
                        result = self.manager.collect_periodic(self.config.periodic_interval_minutes)
                        if result.success:
                            if result.runs_stored > 0:
                                self.logger.info(f"✅ Periodic collection completed: {result.runs_collected} collected, {result.runs_stored} stored")
                            else:
                                self.logger.debug(f"✅ Periodic collection completed: {result.runs_collected} collected, {result.runs_stored} stored (no new data)")
                            last_periodic_time = now
                        else:
                            self.logger.error(f"❌ Periodic collection failed: {result.errors}")
                    except Exception as e:
                        self.logger.error(f"❌ Periodic collection error: {e}")
                
                # Sleep for 1 minute before checking again
                self.stop_event.wait(60)
                
            except Exception as e:
                self.logger.error(f"❌ Error in collection loop: {e}")
                self.stop_event.wait(60)  # Wait a minute before retrying
    
    def _should_run_daily_collection(self, current_time: dt_time, current_date, last_daily_date) -> bool:
        """
        Check if we should run daily collection
        
        Args:
            current_time: Current time of day
            current_date: Current date
            last_daily_date: Date of last daily collection
            
        Returns:
            True if daily collection should run
        """
        if not self.config.enabled:
            return False
        
        # Check if it's time for daily collection
        daily_time = self.config.daily_collection_time
        
        # Allow a 5-minute window around the scheduled time
        time_diff = abs((current_time.hour * 60 + current_time.minute) - 
                       (daily_time.hour * 60 + daily_time.minute))
        
        if time_diff <= 5:  # Within 5 minutes of scheduled time
            # Check if we haven't already done it today
            if last_daily_date != current_date:
                return True
        
        return False
    
    def _should_run_periodic_collection(self, current_time: dt_time, current_datetime: datetime, last_periodic_time: Optional[datetime]) -> bool:
        """
        Check if we should run periodic collection
        
        Args:
            current_time: Current time of day
            current_datetime: Current datetime
            last_periodic_time: Datetime of last periodic collection
            
        Returns:
            True if periodic collection should run
        """
        if not self.config.enabled:
            return False
        
        # Check if we're within periodic collection hours
        if not (self.config.periodic_start_time <= current_time <= self.config.periodic_end_time):
            return False
        
        # Check if enough time has passed since last collection
        if last_periodic_time:
            time_since_last = current_datetime - last_periodic_time
            if time_since_last.total_seconds() < (self.config.periodic_interval_minutes * 60):
                return False
        
        return True
    
    def get_status(self) -> dict:
        """
        Get status of the automated collector
        
        Returns:
            Dictionary with status information
        """
        now = get_houston_now()
        
        status = {
            "running": self.running,
            "current_time": get_display_timestamp(now),
            "config": {
                "enabled": self.config.enabled,
                "daily_time": self.config.daily_collection_time.strftime('%I:%M %p'),
                "periodic_interval": f"{self.config.periodic_interval_minutes} minutes",
                "periodic_hours": f"{self.config.periodic_start_time.strftime('%I:%M %p')} - {self.config.periodic_end_time.strftime('%I:%M %p')}"
            }
        }
        
        # Add next scheduled times
        next_daily = self._calculate_next_daily_time(now)
        status["next_daily_collection"] = get_display_timestamp(next_daily) if next_daily else None
        
        next_periodic = self._calculate_next_periodic_time(now)
        status["next_periodic_collection"] = get_display_timestamp(next_periodic) if next_periodic else None
        
        return status
    
    def _calculate_next_daily_time(self, now: datetime) -> Optional[datetime]:
        """Calculate next daily collection time"""
        from datetime import timedelta
        
        daily_time = self.config.daily_collection_time
        
        # Try today first
        today_daily = now.replace(hour=daily_time.hour, minute=daily_time.minute, second=0, microsecond=0)
        if today_daily > now:
            return today_daily
        
        # Otherwise tomorrow
        tomorrow_daily = today_daily + timedelta(days=1)
        return tomorrow_daily
    
    def _calculate_next_periodic_time(self, now: datetime) -> Optional[datetime]:
        """Calculate next periodic collection time"""
        from datetime import timedelta
        
        # If we're outside periodic hours, return start time tomorrow or today
        current_time = now.time()
        
        if current_time < self.config.periodic_start_time:
            # Before start time today
            return now.replace(hour=self.config.periodic_start_time.hour, 
                             minute=self.config.periodic_start_time.minute, 
                             second=0, microsecond=0)
        elif current_time > self.config.periodic_end_time:
            # After end time today, return start time tomorrow
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=self.config.periodic_start_time.hour, 
                                  minute=self.config.periodic_start_time.minute, 
                                  second=0, microsecond=0)
        else:
            # During periodic hours, return next interval
            minutes_to_add = self.config.periodic_interval_minutes
            next_time = now + timedelta(minutes=minutes_to_add)
            
            # Make sure it's within periodic hours
            if next_time.time() > self.config.periodic_end_time:
                # Next collection would be tomorrow
                tomorrow = now + timedelta(days=1)
                return tomorrow.replace(hour=self.config.periodic_start_time.hour, 
                                      minute=self.config.periodic_start_time.minute, 
                                      second=0, microsecond=0)
            
            return next_time


def main():
    """Run the automated collector as a standalone service"""
    import signal
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/automated_collector.log'),
            logging.StreamHandler()
        ]
    )
    
    print("🚰 Hydrawise Automated Reported Runs Collector")
    print("=" * 50)
    
    # Create and start collector
    collector = AutomatedCollector()
    
    def signal_handler(signum, frame):
        print("\n🛑 Shutdown signal received...")
        collector.stop()
        sys.exit(0)
    
    # Handle shutdown signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start the collector
        collector.start()
        
        # Show status
        status = collector.get_status()
        print(f"🕐 Current time: {status['current_time']}")
        print(f"📅 Next daily collection: {status['next_daily_collection']}")
        print(f"🔄 Next periodic collection: {status['next_periodic_collection']}")
        print("\n✅ Automated collector is running...")
        print("   Press Ctrl+C to stop")
        
        # Keep the main thread alive
        while collector.running:
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        collector.stop()

if __name__ == "__main__":
    main()
