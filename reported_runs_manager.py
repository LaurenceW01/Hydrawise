#!/usr/bin/env python3
"""
Reported Runs Collection Manager for Hydrawise

Manages three operational modes for collecting reported/actual irrigation runs:
1. Daily Collection: Previous day + current day reported runs (once per day)
2. Periodic Collection: Current day delta updates (throughout the day)
3. Admin Override: Manual collection for any date range

Author: AI Assistant
Date: 2025-08-23
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from hydrawise_web_scraper_refactored import HydrawiseWebScraper
from database.db_interface import HydrawiseDB
from utils.timezone_utils import get_houston_now, get_database_timestamp, get_display_timestamp

logger = logging.getLogger(__name__)

class CollectionMode(Enum):
    """Collection modes for reported runs"""
    DAILY = "daily"           # Previous day + current day (once per day)
    PERIODIC = "periodic"     # Current day deltas (throughout day)
    ADMIN = "admin"          # Manual override for any date

@dataclass
class CollectionResult:
    """Result of a collection operation"""
    mode: CollectionMode
    success: bool
    start_time: datetime
    end_time: datetime
    collection_date: date
    runs_collected: int
    runs_stored: int
    errors: List[str]
    details: Dict[str, any]

class ReportedRunsManager:
    """
    Manager for reported runs collection with multiple operational modes
    """
    
    def __init__(self, username: str = None, password: str = None, headless: bool = True):
        """
        Initialize the reported runs manager
        
        Args:
            username: Hydrawise username (optional, can load from env)
            password: Hydrawise password (optional, can load from env)
            headless: Whether to run browser in headless mode
        """
        # Load credentials if not provided
        if not username or not password:
            from dotenv import load_dotenv
            load_dotenv()
            username = username or os.getenv('HYDRAWISE_USER')
            password = password or os.getenv('HYDRAWISE_PASSWORD')
            
        if not username or not password:
            raise ValueError("Username and password required (from parameters or .env file)")
        
        self.username = username
        self.password = password
        self.headless = headless
        
        # Initialize database interface
        self.db = HydrawiseDB()
        
        # Track last collection times to prevent duplicate work
        self._last_daily_collection = None
        self._last_periodic_collection = None
        
        logger.info(f"ReportedRunsManager initialized (headless={headless})")
    
    # ========== PUBLIC INTERFACE METHODS ==========
    
    def collect_daily(self, force: bool = False) -> CollectionResult:
        """
        Daily collection: Previous day + current day reported runs
        
        This should run once per day to get:
        - Previous day's complete reported runs (final data)
        - Current day's reported runs (partial data, will be updated periodically)
        
        Args:
            force: Force collection even if already done today
            
        Returns:
            CollectionResult with operation details
        """
        start_time = get_houston_now()
        collection_date = start_time.date()
        
        logger.info(f"🌅 Starting daily reported runs collection for {collection_date}")
        
        # Check if we've already done daily collection today
        if not force and self._already_collected_today("daily"):
            return CollectionResult(
                mode=CollectionMode.DAILY,
                success=True,
                start_time=start_time,
                end_time=get_houston_now(),
                collection_date=collection_date,
                runs_collected=0,
                runs_stored=0,
                errors=[],
                details={"skipped": "Already collected today"}
            )
        
        result = CollectionResult(
            mode=CollectionMode.DAILY,
            success=False,
            start_time=start_time,
            end_time=None,
            collection_date=collection_date,
            runs_collected=0,
            runs_stored=0,
            errors=[],
            details={}
        )
        
        try:
            # Initialize scraper
            scraper = HydrawiseWebScraper(self.username, self.password, headless=self.headless)
            
            # Collect previous day's reported runs (final data)
            previous_date = collection_date - timedelta(days=1)
            logger.info(f"📅 Collecting previous day runs ({previous_date})")
            
            previous_runs = self._collect_runs_for_date(scraper, previous_date)
            logger.info(f"   Collected {len(previous_runs)} runs for {previous_date}")
            
            # Store previous day's data
            if previous_runs:
                stored_prev = self.db.write_actual_runs(previous_runs, previous_date)
                logger.info(f"   Stored {stored_prev} runs for {previous_date}")
                result.runs_stored += stored_prev
            
            # Collect current day's reported runs (partial data)
            logger.info(f"📅 Collecting current day runs ({collection_date})")
            
            current_runs = self._collect_runs_for_date(scraper, collection_date)
            logger.info(f"   Collected {len(current_runs)} runs for {collection_date}")
            
            # Store current day's data
            if current_runs:
                stored_curr = self.db.write_actual_runs(current_runs, collection_date)
                logger.info(f"   Stored {stored_curr} runs for {collection_date}")
                result.runs_stored += stored_curr
            
            result.runs_collected = len(previous_runs) + len(current_runs)
            result.success = True
            result.details = {
                "previous_day_runs": len(previous_runs),
                "current_day_runs": len(current_runs),
                "previous_date": str(previous_date),
                "current_date": str(collection_date)
            }
            
            # Update last collection time
            self._last_daily_collection = start_time
            
            logger.info(f"✅ Daily collection completed: {result.runs_collected} runs collected, {result.runs_stored} stored")
            
        except Exception as e:
            error_msg = f"Daily collection failed: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            
        finally:
            result.end_time = get_houston_now()
            
        return result
    
    def collect_periodic(self, min_interval_minutes: int = 30) -> CollectionResult:
        """
        Periodic collection: Current day reported runs (delta updates)
        
        This should run throughout the day to capture new reported runs.
        Only collects current day data and stores deltas.
        
        Args:
            min_interval_minutes: Minimum minutes between periodic collections
            
        Returns:
            CollectionResult with operation details
        """
        start_time = get_houston_now()
        collection_date = start_time.date()
        
        logger.info(f"🔄 Starting periodic reported runs collection for {collection_date}")
        
        # Check minimum interval
        if self._last_periodic_collection:
            time_since_last = start_time - self._last_periodic_collection
            if time_since_last.total_seconds() < (min_interval_minutes * 60):
                return CollectionResult(
                    mode=CollectionMode.PERIODIC,
                    success=True,
                    start_time=start_time,
                    end_time=get_houston_now(),
                    collection_date=collection_date,
                    runs_collected=0,
                    runs_stored=0,
                    errors=[],
                    details={"skipped": f"Too soon (min interval: {min_interval_minutes}min)"}
                )
        
        result = CollectionResult(
            mode=CollectionMode.PERIODIC,
            success=False,
            start_time=start_time,
            end_time=None,
            collection_date=collection_date,
            runs_collected=0,
            runs_stored=0,
            errors=[],
            details={}
        )
        
        try:
            # Initialize scraper
            scraper = HydrawiseWebScraper(self.username, self.password, headless=self.headless)
            
            # Collect current day's reported runs
            logger.info(f"📅 Collecting current day runs ({collection_date})")
            
            current_runs = self._collect_runs_for_date(scraper, collection_date)
            logger.info(f"   Collected {len(current_runs)} runs for {collection_date}")
            
            # Store current day's data (database will handle duplicates)
            if current_runs:
                stored_count = self.db.write_actual_runs(current_runs, collection_date)
                logger.info(f"   Stored {stored_count} new/updated runs for {collection_date}")
                result.runs_stored = stored_count
            
            result.runs_collected = len(current_runs)
            result.success = True
            result.details = {
                "current_day_runs": len(current_runs),
                "collection_date": str(collection_date),
                "interval_minutes": min_interval_minutes
            }
            
            # Update last collection time
            self._last_periodic_collection = start_time
            
            logger.info(f"✅ Periodic collection completed: {result.runs_collected} runs collected, {result.runs_stored} stored")
            
        except Exception as e:
            error_msg = f"Periodic collection failed: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            
        finally:
            result.end_time = get_houston_now()
            
        return result
    
    def collect_admin(self, target_date: date, limit_zones: int = None) -> CollectionResult:
        """
        Admin override: Manual collection for specific date
        
        This allows manual collection of any date for troubleshooting,
        backfilling, or administrative purposes.
        
        Args:
            target_date: Specific date to collect
            limit_zones: Optional limit on number of zones to process
            
        Returns:
            CollectionResult with operation details
        """
        start_time = get_houston_now()
        
        logger.info(f"👤 Starting admin reported runs collection for {target_date}")
        
        result = CollectionResult(
            mode=CollectionMode.ADMIN,
            success=False,
            start_time=start_time,
            end_time=None,
            collection_date=target_date,
            runs_collected=0,
            runs_stored=0,
            errors=[],
            details={}
        )
        
        try:
            # Initialize scraper
            scraper = HydrawiseWebScraper(self.username, self.password, headless=self.headless)
            
            # Collect runs for specified date
            logger.info(f"📅 Collecting runs for {target_date} (admin mode)")
            
            collected_runs = self._collect_runs_for_date(scraper, target_date, limit_zones)
            logger.info(f"   Collected {len(collected_runs)} runs for {target_date}")
            
            # Store the data
            if collected_runs:
                storage_result = self.db.write_actual_runs(collected_runs, target_date)
                
                # Handle both old int return and new dict return
                if isinstance(storage_result, dict):
                    stored_count = storage_result.get('new', 0) + storage_result.get('updated', 0)
                    storage_breakdown = storage_result
                else:
                    stored_count = storage_result
                    storage_breakdown = {'new': stored_count, 'updated': 0, 'unchanged': 0, 'total': len(collected_runs)}
                
                logger.info(f"   Stored {stored_count} runs for {target_date}")
                result.runs_stored = stored_count
            else:
                storage_breakdown = {'new': 0, 'updated': 0, 'unchanged': 0, 'total': 0}
            
            result.runs_collected = len(collected_runs)
            result.success = True
            result.details = {
                "target_date": str(target_date),
                "runs_collected": len(collected_runs),
                "limit_zones": limit_zones,
                "admin_mode": True,
                "storage_breakdown": storage_breakdown
            }
            
            logger.info(f"✅ Admin collection completed: {result.runs_collected} runs collected, {result.runs_stored} stored")
            
        except Exception as e:
            error_msg = f"Admin collection failed: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            
        finally:
            result.end_time = get_houston_now()
            
        return result
    
    # ========== HELPER METHODS ==========
    
    def _collect_runs_for_date(self, scraper: HydrawiseWebScraper, target_date: date, limit_zones: int = None) -> List:
        """
        Collect reported runs for a specific date using the scraper
        
        Args:
            scraper: Initialized HydrawiseWebScraper instance
            target_date: Date to collect runs for
            limit_zones: Optional limit on number of zones
            
        Returns:
            List of ActualRun objects
        """
        try:
            # Follow the working pattern from collect_reported_data.py
            logger.info("🔐 Starting browser and logging in...")
            scraper.start_browser()
            if not scraper.login():
                raise Exception("Login failed")
            
            logger.info("✅ Login successful")
            
            # Navigate to reports
            logger.info("🗂️  Navigating to reports page...")
            scraper.navigate_to_reports()
            
            # Use appropriate extraction method based on date
            if target_date < date.today():
                logger.info(f"📋 Extracting reported runs for {target_date}...")
                target_datetime = datetime.combine(target_date + timedelta(days=1), datetime.min.time())  # Reference date should be day after target
                actual_runs = scraper.extract_previous_day_reported_runs(target_datetime)
            else:
                # For current day, use extract_actual_runs 
                logger.info(f"📋 Extracting current day reported runs for {target_date}...")
                target_datetime = datetime.combine(target_date, datetime.min.time())
                actual_runs = scraper.extract_actual_runs(target_datetime)
            
            # Apply zone limit if specified
            if limit_zones and len(actual_runs) > limit_zones:
                logger.info(f"Limiting to first {limit_zones} zones (found {len(actual_runs)} total)")
                actual_runs = actual_runs[:limit_zones]
            
            return actual_runs
            
        finally:
            # Always stop browser
            try:
                scraper.stop_browser()
                logger.info("🔒 Browser closed")
            except Exception as e:
                logger.debug(f"Browser cleanup warning: {e}")
    
    def _already_collected_today(self, collection_type: str) -> bool:
        """
        Check if we've already collected data today for the specified type
        
        Args:
            collection_type: "daily" or "periodic"
            
        Returns:
            True if already collected today
        """
        today = date.today()
        
        if collection_type == "daily":
            if self._last_daily_collection:
                return self._last_daily_collection.date() == today
        elif collection_type == "periodic":
            if self._last_periodic_collection:
                return self._last_periodic_collection.date() == today
        
        return False
    
    def get_collection_status(self) -> Dict[str, any]:
        """
        Get status of collection operations
        
        Returns:
            Dictionary with collection status information
        """
        now = get_houston_now()
        today = now.date()
        
        status = {
            "current_time": get_display_timestamp(now),
            "daily_collection": {
                "last_run": get_display_timestamp(self._last_daily_collection) if self._last_daily_collection else None,
                "completed_today": self._already_collected_today("daily"),
                "next_recommended": get_display_timestamp(datetime.combine(today + timedelta(days=1), datetime.min.time().replace(hour=6)))
            },
            "periodic_collection": {
                "last_run": get_display_timestamp(self._last_periodic_collection) if self._last_periodic_collection else None,
                "completed_today": self._already_collected_today("periodic"),
                "next_recommended": None
            },
            "database_info": self.db.get_database_info()
        }
        
        # Calculate next periodic recommendation
        if self._last_periodic_collection:
            next_periodic = self._last_periodic_collection + timedelta(minutes=30)
            status["periodic_collection"]["next_recommended"] = get_display_timestamp(next_periodic)
        
        return status


def main():
    """Test the reported runs manager"""
    print("🔄 Testing Reported Runs Manager")
    print("=" * 50)
    
    try:
        # Initialize manager
        manager = ReportedRunsManager(headless=False)
        
        # Show current status
        print("📊 Current Collection Status:")
        status = manager.get_collection_status()
        print(f"   Current time: {status['current_time']}")
        print(f"   Daily collection completed today: {status['daily_collection']['completed_today']}")
        print(f"   Periodic collection completed today: {status['periodic_collection']['completed_today']}")
        
        # Test admin collection (small sample)
        yesterday = date.today() - timedelta(days=1)
        print(f"\n👤 Testing admin collection for {yesterday} (first 3 zones):")
        
        admin_result = manager.collect_admin(yesterday, limit_zones=3)
        
        print(f"   Success: {admin_result.success}")
        print(f"   Runs collected: {admin_result.runs_collected}")
        print(f"   Runs stored: {admin_result.runs_stored}")
        print(f"   Duration: {(admin_result.end_time - admin_result.start_time).total_seconds():.1f} seconds")
        
        if admin_result.errors:
            print(f"   Errors: {admin_result.errors}")
        
        print("\n✅ Reported runs manager test completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
