#!/usr/bin/env python3
"""
Automated Hydrawise Data Collector

Background service that automatically collects both schedules and reported runs:
- Daily collection at startup if after scheduled time
- Schedule collection every hour during active hours
- Reported runs collection every hour during active hours
- Configurable schedule and intervals

Author: AI Assistant  
Date: 2025-08-26
"""

import os
import sys
import time
import logging
import threading
import sqlite3
from datetime import datetime, date, time as dt_time, timedelta
from typing import Optional
from dataclasses import dataclass

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reported_runs_manager import ReportedRunsManager
from utils.timezone_utils import get_houston_now, get_display_timestamp, get_database_timestamp
from utils.logging_utils import setup_instance_logging, setup_main_logging
import subprocess

@dataclass
class ScheduleConfig:
    """Configuration for automated collection schedule"""
    daily_collection_time: dt_time = dt_time(6, 0)  # 6:00 AM Houston time
    hourly_interval_minutes: int = 60                # Every hour
    active_start_time: dt_time = dt_time(6, 0)       # Start at 6:00 AM
    active_end_time: dt_time = dt_time(20, 0)        # End at 8:00 PM
    enabled: bool = True
    collect_schedules: bool = True                   # Enable schedule collection
    collect_reported_runs: bool = True               # Enable reported runs collection
    collect_yesterday_on_startup: bool = True        # Collect yesterday's data on startup
    smart_startup_check: bool = True                 # Check if yesterday's data already exists
    headless_mode: bool = True                       # Run browsers in headless mode by default

class AutomatedCollector:
    """
    Automated background collector for schedules and reported runs
    """
    
    def __init__(self, config: ScheduleConfig = None):
        """
        Initialize the automated collector
        
        Args:
            config: Schedule configuration (uses defaults if None)
        """
        self.config = config or ScheduleConfig()
        self.running = False
        self.paused = False
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.collector_thread = None
        
        # Initialize the reported runs manager with proper headless setting
        self.manager = ReportedRunsManager(headless=self.config.headless_mode)
        
        # Setup logging with file handler
        self.logger, self.log_filename = setup_instance_logging(__name__, "automated_collector")
        
        # Track collection state
        self.last_daily_date = None
        self.last_interval_time = None
        self.startup_completed = False
        
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
        
        self.logger.info("[START] Automated collection service started")
        self.logger.info(f"   Daily collection: {self.config.daily_collection_time.strftime('%I:%M %p')} Houston time")
        self.logger.info(f"   Interval collection: Every {self.config.hourly_interval_minutes} minutes")
        self.logger.info(f"   Active hours: {self.config.active_start_time.strftime('%I:%M %p')} - {self.config.active_end_time.strftime('%I:%M %p')}")
        self.logger.info(f"   Schedule collection: {'Enabled' if self.config.collect_schedules else 'Disabled'}")
        self.logger.info(f"   Reported runs collection: {'Enabled' if self.config.collect_reported_runs else 'Disabled'}")
        
        # Run startup collection if after scheduled time
        self._run_startup_collection()
    

    def _run_startup_collection(self):
        """Run initial collection at startup if after scheduled time"""
        now = get_houston_now()
        current_time = now.time()
        
        # Check if we're after the daily collection time and before end time
        if (current_time >= self.config.daily_collection_time and 
            current_time <= self.config.active_end_time):
            
            self.logger.info(f"[STARTUP] Running startup collection at {get_display_timestamp(now)}")
            self.logger.info("   Collecting previous day and current day data to update database")
            
            # Start a separate thread for startup collection to avoid blocking
            startup_thread = threading.Thread(target=self._execute_startup_collection, daemon=True)
            startup_thread.start()
    
    def pause(self):
        """Pause the automated collection service"""
        if not self.running:
            self.logger.warning("Cannot pause: collector is not running")
            return
        
        if self.paused:
            self.logger.warning("Collector is already paused")
            return
        
        self.paused = True
        self.pause_event.set()
        self.logger.info("[PAUSE] Automated collection service paused")
    
    def resume(self):
        """Resume the automated collection service"""
        if not self.running:
            self.logger.warning("Cannot resume: collector is not running")
            return
        
        if not self.paused:
            self.logger.warning("Collector is not paused")
            return
        
        self.paused = False
        self.pause_event.clear()
        self.logger.info("[RESUME] Automated collection service resumed")
    
    def stop(self):
        """Stop the automated collection service"""
        if not self.running:
            return
        
        self.logger.info("[STOP] Stopping automated collection service...")
        self.running = False
        self.paused = False
        self.stop_event.set()
        self.pause_event.clear()
        
        # Wait for thread to finish
        if self.collector_thread and self.collector_thread.is_alive():
            self.collector_thread.join(timeout=10)
        
        self.logger.info("[STOP] Automated collection service stopped")
    
    def _execute_startup_collection(self):
        """Execute the startup collection in a separate thread"""
        try:
            now = get_houston_now()
            
            # Check if we should collect yesterday's data
            if self.config.collect_yesterday_on_startup:
                should_collect_yesterday = True
                
                if self.config.smart_startup_check:
                    should_collect_yesterday = self._should_collect_yesterday_data(now)
                
                if should_collect_yesterday:
                    # Collect previous day's data first (respecting configuration)
                    yesterday = (now - timedelta(days=1)).date()
                    self.logger.info("[STARTUP] Collecting previous day's data...")
                    
                    schedules_success = True
                    runs_success = True
                    
                    if self.config.collect_schedules:
                        self.logger.info("   Running schedule collection for yesterday...")
                        schedules_success = self._run_admin_command("admin_schedule_collection.py", "collect", "yesterday")
                    
                    if self.config.collect_reported_runs:
                        self.logger.info("   Running reported runs collection for yesterday...")
                        runs_success = self._run_admin_command("admin_reported_runs.py", "yesterday")
                    
                    # Mark yesterday as complete if collections succeeded
                    if schedules_success and runs_success:
                        self._mark_collection_complete(
                            yesterday, 
                            schedules_complete=self.config.collect_schedules, 
                            runs_complete=self.config.collect_reported_runs
                        )
                else:
                    self.logger.info("[STARTUP] Yesterday's data already exists, skipping collection")
            else:
                self.logger.info("[STARTUP] Yesterday's data collection disabled in configuration")
            
            # Collect current day's data (respecting configuration)
            today = now.date()
            self.logger.info("[STARTUP] Collecting current day's data...")
            
            today_schedules_success = True
            today_runs_success = True
            
            if self.config.collect_schedules:
                self.logger.info("   Running schedule collection for today...")
                today_schedules_success = self._run_admin_command("admin_schedule_collection.py", "collect", "today")
            
            if self.config.collect_reported_runs:
                self.logger.info("   Running reported runs collection for today...")
                today_runs_success = self._run_admin_command("admin_reported_runs.py", "today")
            
            # NOTE: Do NOT mark today as complete - today's data is ongoing and should not be marked complete
            # Only yesterday's data should be marked complete since it represents a finalized day
            
            self.startup_completed = True
            self.last_daily_date = now.date()
            self.last_interval_time = now  # Set last interval time to prevent immediate interval run
            self.logger.info("[STARTUP] Startup collection completed successfully")
            
        except Exception as e:
            self.logger.error(f"[ERROR] Startup collection failed: {e}")
    
    def _run_admin_command(self, script, *args):
        """Run an admin command and log the results"""
        import gc
        import time
        
        try:
            # Set up environment for better memory management
            enhanced_env = {
                **os.environ,
                'PYTHONMALLOC': 'malloc',  # Use system malloc for better memory management
                'PYTHONHASHSEED': '0',     # Consistent hashing for better memory patterns
                'PYTHONOPTIMIZE': '1'      # Enable basic optimizations
            }
            
            # Build command with visible flag if needed
            cmd = ["python", script]
            if not self.config.headless_mode:
                cmd.append("--visible")
            cmd.extend(list(args))
            self.logger.info(f"[RUN] Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300,  # 5 minute timeout
                env=enhanced_env
            )
            
            if result.returncode == 0:
                self.logger.info(f"[SUCCESS] Command completed successfully: {script} {' '.join(args)}")
                if result.stdout.strip():
                    # Log key output lines
                    lines = result.stdout.strip().split('\n')
                    for line in lines[-10:]:  # Last 10 lines
                        if any(keyword in line.lower() for keyword in ['collected', 'stored', 'success', 'completed', 'error']):
                            self.logger.info(f"   Output: {line.strip()}")
                
                # Force cleanup after subprocess completion
                self.logger.debug("[CLEANUP] Running garbage collection and system cleanup")
                gc.collect()  # Force Python garbage collection
                time.sleep(3)  # Allow system to reclaim resources
                self.logger.debug("[CLEANUP] Cleanup completed")
                return True
            else:
                self.logger.error(f"[ERROR] Command failed: {script} {' '.join(args)} (exit code: {result.returncode})")
                if result.stderr.strip():
                    self.logger.error(f"   Error: {result.stderr.strip()}")
                
                # Cleanup after error too
                gc.collect()
                time.sleep(2)
                return False
                    
        except subprocess.TimeoutExpired:
            self.logger.error(f"[TIMEOUT] Command timed out: {script} {' '.join(args)}")
            # Cleanup after timeout too
            gc.collect()
            time.sleep(2)
            return False
        except Exception as e:
            self.logger.error(f"[ERROR] Error running command {script}: {e}")
            # Cleanup after error too
            gc.collect()
            time.sleep(2)
            return False
    
    def _should_collect_yesterday_data(self, now: datetime) -> bool:
        """Check if we should collect yesterday's data based on completion tracking"""
        try:
            yesterday = now.date() - timedelta(days=1)
            db_path = 'database/irrigation_data.db'
            
            # Check if database exists
            if not os.path.exists(db_path):
                self.logger.info("   Database doesn't exist, will collect yesterday's data")
                return True
            
            # Check completion status for yesterday
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Check if yesterday's collection is marked as complete
                cursor.execute("""
                    SELECT schedules_complete, runs_complete 
                    FROM collection_status 
                    WHERE date = ?
                """, (yesterday.isoformat(),))
                
                result = cursor.fetchone()
                
                if result:
                    schedules_complete, runs_complete = result
                    
                    # Check what types of collection are enabled
                    schedules_needed = self.config.collect_schedules
                    runs_needed = self.config.collect_reported_runs
                    
                    # Determine if collection is needed based on what's enabled
                    if schedules_needed and not schedules_complete:
                        self.logger.info(f"   Yesterday's schedule collection not complete, will collect")
                        return True
                    elif runs_needed and not runs_complete:
                        self.logger.info(f"   Yesterday's runs collection not complete, will collect")
                        return True
                    elif (not schedules_needed or schedules_complete) and (not runs_needed or runs_complete):
                        self.logger.info(f"   Yesterday's collection already completed (schedules: {schedules_complete}, runs: {runs_complete})")
                        return False
                    else:
                        # This shouldn't happen, but be safe
                        return True
                else:
                    self.logger.info(f"   No completion record for yesterday, will collect")
                    return True
                    
        except Exception as e:
            self.logger.warning(f"   Error checking yesterday's completion status: {e}, will collect anyway")
            return True
    
    def _mark_collection_complete(self, collection_date: date, schedules_complete: bool = False, runs_complete: bool = False):
        """Mark a collection as complete in the database"""
        try:
            db_path = 'database/irrigation_data.db'
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Insert or update the completion status with Houston time
                cursor.execute("""
                    INSERT OR REPLACE INTO collection_status 
                    (date, schedules_complete, runs_complete, last_updated)
                    VALUES (?, ?, ?, ?)
                """, (collection_date.isoformat(), schedules_complete, runs_complete, get_database_timestamp()))
                
                conn.commit()
                self.logger.info(f"   Marked {collection_date} collection complete (schedules: {schedules_complete}, runs: {runs_complete})")
                
        except Exception as e:
            self.logger.error(f"   Error marking collection complete for {collection_date}: {e}")
    
    def _collection_loop(self):
        """Main collection loop (runs in background thread)"""        
        self.logger.info("[LOOP] Collection loop started")
        
        while self.running and not self.stop_event.is_set():
            try:
                # Check if paused
                if self.paused:
                    self.logger.debug("[PAUSE] Collection paused, waiting...")
                    self.pause_event.wait(60)  # Check every minute while paused
                    continue
                
                now = get_houston_now()
                current_date = now.date()
                current_time = now.time()
                
                # Check for daily collection (only if startup wasn't completed today)
                if self._should_run_daily_collection(current_time, current_date, self.last_daily_date):
                    self.logger.info(f"[DAILY] Running scheduled daily collection at {get_display_timestamp(now)}")
                    
                    try:
                        # Run full daily collection (respecting configuration)
                        yesterday = current_date - timedelta(days=1)
                        
                        # Yesterday collection
                        yesterday_schedules_success = True
                        yesterday_runs_success = True
                        
                        if self.config.collect_schedules:
                            self.logger.info("   Running daily schedule collection for yesterday...")
                            yesterday_schedules_success = self._run_admin_command("admin_schedule_collection.py", "collect", "yesterday")
                        
                        if self.config.collect_reported_runs:
                            self.logger.info("   Running daily reported runs collection for yesterday...")
                            yesterday_runs_success = self._run_admin_command("admin_reported_runs.py", "yesterday")
                        
                        # Mark yesterday as complete if collections succeeded
                        if yesterday_schedules_success and yesterday_runs_success:
                            self._mark_collection_complete(
                                yesterday, 
                                schedules_complete=self.config.collect_schedules, 
                                runs_complete=self.config.collect_reported_runs
                            )
                        
                        # Today collection
                        today_schedules_success = True
                        today_runs_success = True
                        
                        if self.config.collect_schedules:
                            self.logger.info("   Running daily schedule collection for today...")
                            today_schedules_success = self._run_admin_command("admin_schedule_collection.py", "collect", "today")
                        
                        if self.config.collect_reported_runs:
                            self.logger.info("   Running daily reported runs collection for today...")
                            today_runs_success = self._run_admin_command("admin_reported_runs.py", "today")
                        
                        # NOTE: Do NOT mark today as complete - today's data is ongoing and should not be marked complete
                        # Only yesterday's data should be marked complete since it represents a finalized day
                        
                        self.last_daily_date = current_date
                        self.logger.info("[DAILY] Daily collection completed")
                    except Exception as e:
                        self.logger.error(f"[ERROR] Daily collection error: {e}")
                
                # Check for interval collection (but skip if startup is in progress)
                if self.startup_completed and self._should_run_interval_collection(current_time, now, self.last_interval_time):
                    self.logger.info(f"[INTERVAL] Running scheduled interval collection at {get_display_timestamp(now)}")
                    
                    try:
                        # Collect current day updates
                        interval_schedules_success = True
                        interval_runs_success = True
                        
                        if self.config.collect_schedules:
                            interval_schedules_success = self._run_admin_command("admin_schedule_collection.py", "collect", "today")
                        
                        if self.config.collect_reported_runs:
                            interval_runs_success = self._run_admin_command("admin_reported_runs.py", "update")
                        
                        # NOTE: Do NOT mark today as complete during interval collection - today's data is ongoing
                        # Interval collection updates current data but should not mark the day as complete
                        
                        self.last_interval_time = now
                        self.logger.info("[INTERVAL] Interval collection completed")
                    except Exception as e:
                        self.logger.error(f"[ERROR] Interval collection error: {e}")
                elif not self.startup_completed:
                    self.logger.debug("[INTERVAL] Skipping interval collection - startup in progress")
                elif self.last_interval_time:
                    # Log how much time remaining until next interval run
                    time_since_last = now - self.last_interval_time
                    minutes_since_last = time_since_last.total_seconds() / 60
                    minutes_remaining = self.config.hourly_interval_minutes - minutes_since_last
                    if minutes_remaining > 0:
                        self.logger.debug(f"[INTERVAL] Next interval collection in {minutes_remaining:.1f} minutes")
                
                # Sleep for 5 minutes before checking again
                self.stop_event.wait(300)
                
            except Exception as e:
                self.logger.error(f"[ERROR] Error in collection loop: {e}")
                self.stop_event.wait(300)  # Wait 5 minutes before retrying
    
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
    
    def _should_run_interval_collection(self, current_time: dt_time, current_datetime: datetime, last_interval_time: Optional[datetime]) -> bool:
        """
        Check if we should run interval collection
        
        Args:
            current_time: Current time of day
            current_datetime: Current datetime
            last_interval_time: Datetime of last interval collection
            
        Returns:
            True if interval collection should run
        """
        if not self.config.enabled:
            return False
        
        # Check if we're within active collection hours (6 AM to 8 PM)
        if not (self.config.active_start_time <= current_time <= self.config.active_end_time):
            return False
        
        # Check if enough time has passed since last collection
        if last_interval_time:
            time_since_last = current_datetime - last_interval_time
            minutes_since_last = time_since_last.total_seconds() / 60
            
            if minutes_since_last < self.config.hourly_interval_minutes:
                # Not enough time has passed
                return False
        else:
            # No previous interval run recorded - should not run until interval passes
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
            "paused": self.paused,
            "current_time": get_display_timestamp(now),
            "startup_completed": self.startup_completed,
            "config": {
                "enabled": self.config.enabled,
                "daily_time": self.config.daily_collection_time.strftime('%I:%M %p'),
                "interval": f"{self.config.hourly_interval_minutes} minutes",
                "active_hours": f"{self.config.active_start_time.strftime('%I:%M %p')} - {self.config.active_end_time.strftime('%I:%M %p')}",
                "schedules_enabled": self.config.collect_schedules,
                "reported_runs_enabled": self.config.collect_reported_runs,
                "collect_yesterday_on_startup": self.config.collect_yesterday_on_startup,
                "smart_startup_check": self.config.smart_startup_check,
                "browser_mode": "Headless" if self.config.headless_mode else "Visible"
            }
        }
        
        # Add next scheduled times
        next_daily = self._calculate_next_daily_time(now)
        status["next_daily_collection"] = get_display_timestamp(next_daily) if next_daily else None
        
        next_interval = self._calculate_next_interval_time(now)
        status["next_interval_collection"] = get_display_timestamp(next_interval) if next_interval else None
        
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
    
    def _calculate_next_interval_time(self, now: datetime) -> Optional[datetime]:
        """Calculate next interval collection time"""
        current_time = now.time()
        
        if current_time < self.config.active_start_time:
            # Before start time today
            return now.replace(hour=self.config.active_start_time.hour, 
                             minute=self.config.active_start_time.minute, 
                             second=0, microsecond=0)
        elif current_time > self.config.active_end_time:
            # After end time today, return start time tomorrow
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=self.config.active_start_time.hour, 
                                  minute=self.config.active_start_time.minute, 
                                  second=0, microsecond=0)
        else:
            # During active hours, calculate based on last interval collection time
            if self.last_interval_time:
                # Calculate next time based on when last collection happened
                next_time = self.last_interval_time + timedelta(minutes=self.config.hourly_interval_minutes)
                
                # Make sure it's within active hours
                if next_time.time() > self.config.active_end_time:
                    # Next collection would be tomorrow
                    tomorrow = now + timedelta(days=1)
                    return tomorrow.replace(hour=self.config.active_start_time.hour, 
                                          minute=self.config.active_start_time.minute, 
                                          second=0, microsecond=0)
                
                return next_time
            else:
                # No previous interval run, return next interval based on start time
                # Find next interval boundary from start time
                start_today = now.replace(hour=self.config.active_start_time.hour,
                                        minute=self.config.active_start_time.minute,
                                        second=0, microsecond=0)
                
                # Calculate how many intervals have passed since start time
                time_since_start = now - start_today
                intervals_passed = int(time_since_start.total_seconds() / (self.config.hourly_interval_minutes * 60))
                
                # Next interval time
                next_time = start_today + timedelta(minutes=(intervals_passed + 1) * self.config.hourly_interval_minutes)
                
                # Make sure it's within active hours
                if next_time.time() > self.config.active_end_time:
                    # Next collection would be tomorrow
                    tomorrow = now + timedelta(days=1)
                    return tomorrow.replace(hour=self.config.active_start_time.hour, 
                                          minute=self.config.active_start_time.minute, 
                                          second=0, microsecond=0)
                
                return next_time


def main():
    """Run the automated collector as a standalone service"""
    import signal
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Hydrawise Automated Data Collector')
    parser.add_argument('--interval', type=int, default=60, 
                       help='Collection interval in minutes (default: 60)')
    parser.add_argument('--start-time', type=str, default='06:00', 
                       help='Active start time in HH:MM format (default: 06:00)')
    parser.add_argument('--end-time', type=str, default='20:00', 
                       help='Active end time in HH:MM format (default: 20:00)')
    parser.add_argument('--no-yesterday', action='store_true',
                       help='Skip collecting yesterday\'s data on startup')
    parser.add_argument('--no-smart-check', action='store_true',
                       help='Disable smart checking for existing data')
    parser.add_argument('--no-schedules', action='store_true',
                       help='Disable schedule collection')
    parser.add_argument('--no-reported-runs', action='store_true',
                       help='Disable reported runs collection')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Logging level (default: INFO)')
    parser.add_argument('--visible', action='store_true',
                       help='Run browsers in visible mode (default: headless/invisible)')
    parser.add_argument('--run-once', action='store_true',
                       help='Run collection once and exit without iterations (for scheduled tasks)')
    
    args = parser.parse_args()
    
    # Parse time arguments
    try:
        start_hour, start_min = map(int, args.start_time.split(':'))
        end_hour, end_min = map(int, args.end_time.split(':'))
        start_time = dt_time(start_hour, start_min)
        end_time = dt_time(end_hour, end_min)
    except ValueError:
        print("[ERROR] Error: Invalid time format. Use HH:MM (e.g., 06:00)")
        return 1
    
    # Create configuration
    config = ScheduleConfig(
        hourly_interval_minutes=args.interval,
        active_start_time=start_time,
        active_end_time=end_time,
        collect_schedules=not args.no_schedules,
        collect_reported_runs=not args.no_reported_runs,
        collect_yesterday_on_startup=not args.no_yesterday,
        smart_startup_check=not args.no_smart_check,
        headless_mode=not args.visible  # Default headless, --visible makes it visible
    )
    
    # Setup logging
    setup_main_logging(log_level=args.log_level)
    
    print("Hydrawise Automated Data Collector")
    print("=" * 50)
    print(f"Configuration:")
    print(f"   Interval: Every {args.interval} minutes")
    print(f"   Active hours: {args.start_time} - {args.end_time}")
    print(f"   Schedules: {'Enabled' if config.collect_schedules else 'Disabled'}")
    print(f"   Reported runs: {'Enabled' if config.collect_reported_runs else 'Disabled'}")
    print(f"   Yesterday collection: {'Enabled' if config.collect_yesterday_on_startup else 'Disabled'}")
    print(f"   Smart checking: {'Enabled' if config.smart_startup_check else 'Disabled'}")
    print(f"   Browser mode: {'Headless' if config.headless_mode else 'Visible'}")
    print(f"   Log level: {args.log_level}")
    print(f"   Run once: {'Yes' if args.run_once else 'No'}")
    print("")
    
    # Handle run-once mode
    if args.run_once:
        print("[RUN-ONCE] Running collection once and exiting...")
        
        # Create collector for one-time execution
        collector = AutomatedCollector(config)
        
        try:
            # Run startup collection which handles both yesterday and today
            collector._execute_startup_collection()
            print("[SUCCESS] Single collection run completed successfully")
            return 0
        except Exception as e:
            print(f"[ERROR] Single collection run failed: {e}")
            return 1
    
    # Create and start collector for continuous operation
    collector = AutomatedCollector(config)
    
    def signal_handler(signum, frame):
        print("\n[SHUTDOWN] Signal received...")
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
        print(f"Current time: {status['current_time']}")
        print(f"Startup completed: {status['startup_completed']}")
        print(f"Paused: {status['paused']}")
        print(f"Next daily collection: {status['next_daily_collection']}")
        print(f"Next interval collection: {status['next_interval_collection']}")
        print("\nAutomated collector is running...")
        print("   Commands available:")
        print("   - Press 'p' + Enter to pause/resume")
        print("   - Press 's' + Enter to show status")
        print("   - Press 'q' + Enter to quit")
        print("   - Press Ctrl+C to stop")
        
        # Keep the main thread alive with interactive commands (Windows compatible)
        try:
            import threading
            import queue
            
            input_queue = queue.Queue()
            
            def input_thread():
                """Background thread to handle user input"""
                while collector.running:
                    try:
                        line = input().strip().lower()
                        input_queue.put(line)
                    except (EOFError, KeyboardInterrupt):
                        # User pressed Ctrl+D or Ctrl+C
                        input_queue.put('quit')
                        break
                    except Exception:
                        # Handle any other input errors
                        break
            
            # Start input thread
            input_handler = threading.Thread(target=input_thread, daemon=True)
            input_handler.start()
            
            while collector.running:
                try:
                    # Check for user input with timeout
                    try:
                        line = input_queue.get(timeout=1)
                        
                        if line == 'p':
                            if collector.paused:
                                collector.resume()
                                print("[RESUME] Collection resumed")
                            else:
                                collector.pause()
                                print("[PAUSE] Collection paused")
                        elif line == 's':
                            # Show status
                            status = collector.get_status()
                            print(f"\n[STATUS] Current status:")
                            print(f"   Running: {status['running']}")
                            print(f"   Paused: {status['paused']}")
                            print(f"   Current time: {status['current_time']}")
                            print(f"   Startup completed: {status['startup_completed']}")
                            print(f"   Next daily: {status['next_daily_collection']}")
                            print(f"   Next interval: {status['next_interval_collection']}")
                            print("")
                        elif line in ['q', 'quit', 'exit']:
                            print("[QUIT] Stopping collector...")
                            collector.stop()
                            break
                        else:
                            print("[HELP] Commands: 'p' (pause/resume), 's' (status), 'q' (quit)")
                    
                    except queue.Empty:
                        # No input received, continue monitoring
                        continue
                        
                except KeyboardInterrupt:
                    # Handle Ctrl+C
                    print("\n[SHUTDOWN] Interrupted by user")
                    collector.stop()
                    break
                    
        except KeyboardInterrupt:
            pass
            
    except KeyboardInterrupt:
        print("\n[STOP] Stopped by user")
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        collector.stop()

if __name__ == "__main__":
    main()
