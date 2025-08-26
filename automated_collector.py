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
from datetime import datetime, time as dt_time, timedelta
from typing import Optional
from dataclasses import dataclass

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reported_runs_manager import ReportedRunsManager
from utils.timezone_utils import get_houston_now, get_display_timestamp
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
        
        # Initialize the reported runs manager
        self.manager = ReportedRunsManager(headless=True)
        
        # Setup logging with file handler
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # Track collection state
        self.last_daily_date = None
        self.last_hourly_time = None
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
        self.logger.info(f"   Hourly collection: Every {self.config.hourly_interval_minutes} minutes")
        self.logger.info(f"   Active hours: {self.config.active_start_time.strftime('%I:%M %p')} - {self.config.active_end_time.strftime('%I:%M %p')}")
        self.logger.info(f"   Schedule collection: {'Enabled' if self.config.collect_schedules else 'Disabled'}")
        self.logger.info(f"   Reported runs collection: {'Enabled' if self.config.collect_reported_runs else 'Disabled'}")
        
        # Run startup collection if after scheduled time
        self._run_startup_collection()
    
    def _setup_logging(self):
        """Setup logging with file handler using consistent naming convention"""
        from datetime import datetime
        import os
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Generate log filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f'logs/automated_collector_{timestamp}.log'
        
        # Create file handler with UTF-8 encoding
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        self.logger.info(f"LOG: Logging to: {log_filename}")
    
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
                    # Collect previous day's data first
                    self.logger.info("[STARTUP] Collecting previous day's schedules and reported runs...")
                    self._run_admin_command("admin_schedule_collection.py", "collect", "yesterday")
                    self._run_admin_command("admin_reported_runs.py", "yesterday")
                else:
                    self.logger.info("[STARTUP] Yesterday's data already exists, skipping collection")
            else:
                self.logger.info("[STARTUP] Yesterday's data collection disabled in configuration")
            
            # Collect current day's data
            self.logger.info("[STARTUP] Collecting current day's schedules and reported runs...")
            self._run_admin_command("admin_schedule_collection.py", "collect", "today")
            self._run_admin_command("admin_reported_runs.py", "today")
            
            self.startup_completed = True
            self.last_daily_date = now.date()
            self.logger.info("[STARTUP] Startup collection completed successfully")
            
        except Exception as e:
            self.logger.error(f"[ERROR] Startup collection failed: {e}")
    
    def _run_admin_command(self, script, *args):
        """Run an admin command and log the results"""
        try:
            cmd = ["python", script] + list(args)
            self.logger.info(f"[RUN] Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                self.logger.info(f"[SUCCESS] Command completed successfully: {script} {' '.join(args)}")
                if result.stdout.strip():
                    # Log key output lines
                    lines = result.stdout.strip().split('\n')
                    for line in lines[-10:]:  # Last 10 lines
                        if any(keyword in line.lower() for keyword in ['collected', 'stored', 'success', 'completed', 'error']):
                            self.logger.info(f"   Output: {line.strip()}")
            else:
                self.logger.error(f"[ERROR] Command failed: {script} {' '.join(args)} (exit code: {result.returncode})")
                if result.stderr.strip():
                    self.logger.error(f"   Error: {result.stderr.strip()}")
                    
        except subprocess.TimeoutExpired:
            self.logger.error(f"[TIMEOUT] Command timed out: {script} {' '.join(args)}")
        except Exception as e:
            self.logger.error(f"[ERROR] Error running command {script}: {e}")
    
    def _should_collect_yesterday_data(self, now: datetime) -> bool:
        """Check if we should collect yesterday's data based on database contents"""
        try:
            yesterday = now.date() - timedelta(days=1)
            db_path = 'database/irrigation_data.db'
            
            # Check if database exists
            if not os.path.exists(db_path):
                self.logger.info("   Database doesn't exist, will collect yesterday's data")
                return True
            
            # Check if yesterday's data was updated today
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Check actual_runs table for yesterday's data updated today
                cursor.execute("""
                    SELECT COUNT(*) FROM actual_runs 
                    WHERE DATE(actual_start_time) = ? 
                    AND DATE(created_at) = DATE('now', 'localtime')
                """, (yesterday.isoformat(),))
                
                runs_updated_today = cursor.fetchone()[0]
                
                # Check scheduled_runs table for yesterday's data updated today
                cursor.execute("""
                    SELECT COUNT(*) FROM scheduled_runs 
                    WHERE DATE(schedule_date) = ? 
                    AND DATE(created_at) = DATE('now', 'localtime')
                """, (yesterday.isoformat(),))
                
                schedules_updated_today = cursor.fetchone()[0]
                
                if runs_updated_today > 0 or schedules_updated_today > 0:
                    self.logger.info(f"   Yesterday's data already updated today (runs: {runs_updated_today}, schedules: {schedules_updated_today})")
                    return False
                else:
                    self.logger.info(f"   No yesterday's data found updated today, will collect")
                    return True
                    
        except Exception as e:
            self.logger.warning(f"   Error checking yesterday's data: {e}, will collect anyway")
            return True
    
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
                        # Run full daily collection
                        self._run_admin_command("admin_schedule_collection.py", "collect", "yesterday")
                        self._run_admin_command("admin_reported_runs.py", "yesterday")
                        self._run_admin_command("admin_schedule_collection.py", "collect", "today")
                        self._run_admin_command("admin_reported_runs.py", "today")
                        
                        self.last_daily_date = current_date
                        self.logger.info("[DAILY] Daily collection completed")
                    except Exception as e:
                        self.logger.error(f"[ERROR] Daily collection error: {e}")
                
                # Check for hourly collection
                if self._should_run_hourly_collection(current_time, now, self.last_hourly_time):
                    self.logger.info(f"[HOURLY] Running scheduled hourly collection at {get_display_timestamp(now)}")
                    
                    try:
                        # Collect current day updates
                        if self.config.collect_schedules:
                            self._run_admin_command("admin_schedule_collection.py", "collect", "today")
                        
                        if self.config.collect_reported_runs:
                            self._run_admin_command("admin_reported_runs.py", "update")
                        
                        self.last_hourly_time = now
                        self.logger.info("[HOURLY] Hourly collection completed")
                    except Exception as e:
                        self.logger.error(f"[ERROR] Hourly collection error: {e}")
                
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
    
    def _should_run_hourly_collection(self, current_time: dt_time, current_datetime: datetime, last_hourly_time: Optional[datetime]) -> bool:
        """
        Check if we should run hourly collection
        
        Args:
            current_time: Current time of day
            current_datetime: Current datetime
            last_hourly_time: Datetime of last hourly collection
            
        Returns:
            True if hourly collection should run
        """
        if not self.config.enabled:
            return False
        
        # Check if we're within active collection hours (6 AM to 8 PM)
        if not (self.config.active_start_time <= current_time <= self.config.active_end_time):
            return False
        
        # Check if enough time has passed since last collection
        if last_hourly_time:
            time_since_last = current_datetime - last_hourly_time
            if time_since_last.total_seconds() < (self.config.hourly_interval_minutes * 60):
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
                "hourly_interval": f"{self.config.hourly_interval_minutes} minutes",
                "active_hours": f"{self.config.active_start_time.strftime('%I:%M %p')} - {self.config.active_end_time.strftime('%I:%M %p')}",
                "schedules_enabled": self.config.collect_schedules,
                "reported_runs_enabled": self.config.collect_reported_runs,
                "collect_yesterday_on_startup": self.config.collect_yesterday_on_startup,
                "smart_startup_check": self.config.smart_startup_check
            }
        }
        
        # Add next scheduled times
        next_daily = self._calculate_next_daily_time(now)
        status["next_daily_collection"] = get_display_timestamp(next_daily) if next_daily else None
        
        next_hourly = self._calculate_next_hourly_time(now)
        status["next_hourly_collection"] = get_display_timestamp(next_hourly) if next_hourly else None
        
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
    
    def _calculate_next_hourly_time(self, now: datetime) -> Optional[datetime]:
        """Calculate next hourly collection time"""
        # If we're outside active hours, return start time tomorrow or today
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
            # During active hours, return next interval
            minutes_to_add = self.config.hourly_interval_minutes
            next_time = now + timedelta(minutes=minutes_to_add)
            
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
        smart_startup_check=not args.no_smart_check
    )
    
    # Setup logging with UTF-8 encoding
    os.makedirs('logs', exist_ok=True)
    
    # Create handlers
    file_handler = logging.FileHandler('logs/automated_collector.log', encoding='utf-8')
    console_handler = logging.StreamHandler()
    
    # Set levels
    file_handler.setLevel(getattr(logging, args.log_level))
    console_handler.setLevel(getattr(logging, args.log_level))
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        handlers=[file_handler, console_handler]
    )
    
    print("Hydrawise Automated Data Collector")
    print("=" * 50)
    print(f"Configuration:")
    print(f"   Interval: Every {args.interval} minutes")
    print(f"   Active hours: {args.start_time} - {args.end_time}")
    print(f"   Schedules: {'Enabled' if config.collect_schedules else 'Disabled'}")
    print(f"   Reported runs: {'Enabled' if config.collect_reported_runs else 'Disabled'}")
    print(f"   Yesterday collection: {'Enabled' if config.collect_yesterday_on_startup else 'Disabled'}")
    print(f"   Smart checking: {'Enabled' if config.smart_startup_check else 'Disabled'}")
    print(f"   Log level: {args.log_level}")
    print("")
    
    # Create and start collector
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
        print(f"Next hourly collection: {status['next_hourly_collection']}")
        print("\nAutomated collector is running...")
        print("   Commands available:")
        print("   - Press 'p' + Enter to pause/resume")
        print("   - Press 's' + Enter to show status")
        print("   - Press 'q' + Enter to quit")
        print("   - Press Ctrl+C to stop")
        
        # Keep the main thread alive with interactive commands
        try:
            while collector.running:
                try:
                    # Check for user input (non-blocking)
                    import select
                    import sys
                    
                    if sys.stdin in select.select([sys.stdin], [], [], 1)[0]:
                        line = input().strip().lower()
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
                            print(f"\nStatus Update:")
                            print(f"   Running: {status['running']}")
                            print(f"   Paused: {status['paused']}")
                            print(f"   Current time: {status['current_time']}")
                            print(f"   Next daily: {status['next_daily_collection']}")
                            print(f"   Next hourly: {status['next_hourly_collection']}")
                            print("")
                        elif line in ['q', 'quit', 'exit']:
                            print("[STOP] Stopping collector...")
                            collector.stop()
                            break
                    else:
                        time.sleep(1)
                except (EOFError, KeyboardInterrupt):
                    break
                except:
                    # Fallback for systems without select
                    time.sleep(10)
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
