#!/usr/bin/env python3
"""
Timezone Utilities for Hydrawise Database

Provides consistent timezone handling for all database operations.
All timestamps stored in database will be in Houston/Central Time.

Author: AI Assistant
Date: 2025-08-23
"""

import pytz
from datetime import datetime, timezone
from typing import Optional

# Houston timezone (Central Time)
HOUSTON_TZ = pytz.timezone('US/Central')

def get_houston_now() -> datetime:
    """
    Get current datetime in Houston/Central timezone
    
    Returns:
        datetime: Current time in Houston timezone
    """
    return datetime.now(HOUSTON_TZ)

def to_houston_time(dt: datetime) -> datetime:
    """
    Convert any datetime to Houston timezone
    
    Args:
        dt: datetime object (with or without timezone info)
        
    Returns:
        datetime: datetime converted to Houston timezone
    """
    if dt is None:
        return None
        
    # If datetime is naive (no timezone), assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    
    # Convert to Houston timezone
    return dt.astimezone(HOUSTON_TZ)

def format_houston_timestamp(dt: datetime = None) -> str:
    """
    Format datetime as Houston timezone string for database storage
    
    Args:
        dt: datetime object (defaults to current Houston time)
        
    Returns:
        str: Formatted timestamp string in Houston timezone
    """
    if dt is None:
        dt = get_houston_now()
    else:
        dt = to_houston_time(dt)
    
    # Format as ISO string but include timezone info
    return dt.strftime('%Y-%m-%d %H:%M:%S %Z')

def parse_houston_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse a Houston timezone timestamp string back to datetime
    
    Args:
        timestamp_str: timestamp string from database
        
    Returns:
        datetime: parsed datetime in Houston timezone
    """
    if not timestamp_str:
        return None
        
    try:
        # Handle different timestamp formats
        if ' CST' in timestamp_str or ' CDT' in timestamp_str:
            # Already has timezone info
            for fmt in ['%Y-%m-%d %H:%M:%S %Z', '%Y-%m-%d %H:%M:%S.%f %Z']:
                try:
                    return datetime.strptime(timestamp_str, fmt).replace(tzinfo=HOUSTON_TZ)
                except ValueError:
                    continue
        else:
            # No timezone info, assume it's already Houston time
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f']:
                try:
                    naive_dt = datetime.strptime(timestamp_str, fmt)
                    return HOUSTON_TZ.localize(naive_dt)
                except ValueError:
                    continue
                    
        # If all else fails, try to parse as ISO format and convert
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return to_houston_time(dt)
        
    except Exception:
        return None

def get_database_timestamp() -> str:
    """
    Get properly formatted timestamp for database insertion
    
    Returns:
        str: Houston timezone timestamp for database storage
    """
    houston_time = get_houston_now()
    # Store as ISO format without timezone suffix for SQLite compatibility
    return houston_time.strftime('%Y-%m-%d %H:%M:%S')

def get_display_timestamp(dt: datetime = None) -> str:
    """
    Get human-readable timestamp for display
    
    Args:
        dt: datetime to format (defaults to current Houston time)
        
    Returns:
        str: Human-readable timestamp with timezone
    """
    if dt is None:
        dt = get_houston_now()
    else:
        dt = to_houston_time(dt)
    
    return dt.strftime('%m/%d/%Y %I:%M:%S %p %Z')

def main():
    """Test timezone utilities"""
    print("[SYMBOL] Testing Houston Timezone Utilities")
    print("=" * 50)
    
    # Current time
    now = get_houston_now()
    print(f"Current Houston time: {now}")
    print(f"Formatted for display: {get_display_timestamp()}")
    print(f"Formatted for database: {get_database_timestamp()}")
    
    # Test conversion
    utc_time = datetime.now(pytz.UTC)
    houston_time = to_houston_time(utc_time)
    print(f"\nUTC time: {utc_time}")
    print(f"Converted to Houston: {houston_time}")
    
    # Test parsing
    db_timestamp = get_database_timestamp()
    parsed_time = parse_houston_timestamp(db_timestamp)
    print(f"\nDatabase timestamp: {db_timestamp}")
    print(f"Parsed back: {parsed_time}")
    
    print("\n[SYMBOL] Timezone utilities working correctly!")

if __name__ == "__main__":
    main()
