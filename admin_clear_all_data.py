#!/usr/bin/env python3
"""
Clear All Database Data Utility

This utility script deletes all rows from all tables in the Hydrawise irrigation database.
It preserves the database schema and structure while removing all collected data.

CAUTION: This operation is IRREVERSIBLE. All irrigation data will be permanently lost.

Usage:
    python database/clear_all_data.py [--confirm] [--backup] [--dry-run]

Options:
    --confirm    Required. Confirms you want to delete all data
    --backup     Create a backup before deletion (recommended)
    --dry-run    Show what would be deleted without actually deleting
    --db-path    Specify custom database path (default: database/irrigation_data.db)

Author: AI Assistant
Date: 2025-01-02
"""

import sqlite3
import os
import sys
import argparse
import shutil
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseCleaner:
    """Utility class to safely clear all data from the irrigation database"""
    
    def __init__(self, db_path: str = "database/irrigation_data.db"):
        """Initialize the database cleaner
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.backup_path = None
        
        # List of tables to clear (in dependency order - children first, parents last)
        self.tables_to_clear = [
            # Dependent tables first (have foreign keys)
            'excel_import_log',
            'historical_notes', 
            'collection_log',
            'system_status',
            'daily_variance',
            'failure_events',
            'actual_runs',
            'scheduled_runs',
            # Master table last
            'zones'
        ]
    
    def validate_database_exists(self) -> bool:
        """Check if the database file exists
        
        Returns:
            bool: True if database exists, False otherwise
        """
        if not os.path.exists(self.db_path):
            logger.error(f"Database file not found: {self.db_path}")
            return False
        return True
    
    def get_table_row_counts(self) -> Dict[str, int]:
        """Get current row counts for all tables
        
        Returns:
            dict: Table names mapped to row counts
        """
        row_counts = {}
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for table in self.tables_to_clear:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        row_counts[table] = count
                    except sqlite3.Error as e:
                        logger.warning(f"Could not count rows in table '{table}': {e}")
                        row_counts[table] = 0
                        
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return {}
            
        return row_counts
    
    def create_backup(self) -> bool:
        """Create a timestamped backup of the database
        
        Returns:
            bool: True if backup successful, False otherwise
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"irrigation_data_backup_{timestamp}.db"
        self.backup_path = os.path.join(os.path.dirname(self.db_path), backup_filename)
        
        try:
            shutil.copy2(self.db_path, self.backup_path)
            logger.info(f"[OK] Backup created: {self.backup_path}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to create backup: {e}")
            return False
    
    def clear_all_data(self, dry_run: bool = False) -> bool:
        """Clear all data from all tables
        
        Args:
            dry_run: If True, show what would be deleted without actually deleting
            
        Returns:
            bool: True if operation successful, False otherwise
        """
        if not self.validate_database_exists():
            return False
        
        # Get current row counts
        row_counts = self.get_table_row_counts()
        total_rows = sum(row_counts.values())
        
        if total_rows == 0:
            logger.info("[RESULTS] Database is already empty - no data to clear")
            return True
        
        logger.info("[RESULTS] Current database contents:")
        for table, count in row_counts.items():
            if count > 0:
                logger.info(f"   {table}: {count:,} rows")
        logger.info(f"   TOTAL: {total_rows:,} rows")
        
        if dry_run:
            logger.info("[ANALYSIS] DRY RUN MODE - No data will be deleted")
            logger.info("[LOG] Tables that would be cleared:")
            for table in self.tables_to_clear:
                if row_counts.get(table, 0) > 0:
                    logger.info(f"   DELETE FROM {table}; -- ({row_counts[table]:,} rows)")
            return True
        
        # Perform actual deletion
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Disable foreign key constraints temporarily
                cursor.execute("PRAGMA foreign_keys = OFF")
                
                deleted_counts = {}
                
                for table in self.tables_to_clear:
                    if row_counts.get(table, 0) > 0:
                        try:
                            logger.info(f"[DELETE]  Clearing table: {table} ({row_counts[table]:,} rows)")
                            cursor.execute(f"DELETE FROM {table}")
                            deleted_counts[table] = row_counts[table]
                        except sqlite3.Error as e:
                            logger.error(f"[ERROR] Failed to clear table '{table}': {e}")
                            return False
                
                # Re-enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys = ON")
                
                conn.commit()
                
                # Summary
                total_deleted = sum(deleted_counts.values())
                logger.info("[OK] Data deletion completed successfully!")
                logger.info(f"[RESULTS] Total rows deleted: {total_deleted:,}")
                
                # Verify tables are empty
                verification_counts = self.get_table_row_counts()
                remaining_rows = sum(verification_counts.values())
                
                if remaining_rows == 0:
                    logger.info("[OK] All tables verified empty")
                else:
                    logger.warning(f"[WARNING]  Warning: {remaining_rows} rows still remain in database")
            
            # Vacuum to reclaim space (must be done outside transaction)
            logger.info("[SYMBOL] Optimizing database (VACUUM)")
            try:
                vacuum_conn = sqlite3.connect(self.db_path)
                vacuum_conn.execute("VACUUM")
                vacuum_conn.close()
                logger.info("[OK] Database optimization completed")
            except sqlite3.Error as e:
                logger.warning(f"[WARNING]  Database optimization failed: {e}")
                
            return True
                
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Database operation failed: {e}")
            return False
    
    def reset_auto_increment_counters(self) -> bool:
        """Reset all auto-increment sequences to start from 1
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Reset the sqlite_sequence table which tracks auto-increment values
                cursor.execute("DELETE FROM sqlite_sequence")
                logger.info("[PERIODIC] Auto-increment counters reset to 1")
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Failed to reset auto-increment counters: {e}")
            return False

def main():
    """Main function with command-line interface"""
    parser = argparse.ArgumentParser(
        description="Clear all data from Hydrawise irrigation database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show what would be deleted (safe preview)
    python database/clear_all_data.py --dry-run
    
    # Create backup and clear all data
    python database/clear_all_data.py --confirm --backup
    
    # Clear data without backup (NOT RECOMMENDED)
    python database/clear_all_data.py --confirm
    
    # Use custom database path
    python database/clear_all_data.py --confirm --db-path /path/to/custom.db

[WARNING]  WARNING: This operation permanently deletes ALL irrigation data!
             Always use --backup unless you're certain you don't need the data.
        """
    )
    
    parser.add_argument(
        '--confirm', 
        action='store_true',
        help='Required confirmation flag to proceed with deletion'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create a timestamped backup before clearing data (RECOMMENDED)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true', 
        help='Show what would be deleted without actually deleting anything'
    )
    
    parser.add_argument(
        '--db-path',
        default='database/irrigation_data.db',
        help='Path to the database file (default: database/irrigation_data.db)'
    )
    
    parser.add_argument(
        '--reset-counters',
        action='store_true',
        help='Reset auto-increment ID counters to start from 1'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Require --confirm for non-dry-run operations
    if not args.dry_run and not args.confirm:
        parser.error("--confirm is required for actual deletion operations (not needed for --dry-run)")
    
    # Validate database path
    if not args.dry_run and not os.path.exists(args.db_path):
        logger.error(f"[ERROR] Database file not found: {args.db_path}")
        sys.exit(1)
    
    # Safety confirmation for non-dry runs
    if not args.dry_run:
        print("\n" + "="*60)
        print("[WARNING]  DANGER: DATABASE DELETION OPERATION")
        print("="*60)
        print(f"Database: {args.db_path}")
        print("This will PERMANENTLY DELETE all irrigation data!")
        print("This operation CANNOT be undone!")
        
        if not args.backup:
            print("\n[ALERT] WARNING: No backup will be created!")
            print("   Consider using --backup flag for safety")
        
        response = input("\nType 'DELETE ALL DATA' to confirm: ")
        if response != 'DELETE ALL DATA':
            print("[ERROR] Operation cancelled - confirmation text did not match")
            sys.exit(1)
    
    # Initialize cleaner
    cleaner = DatabaseCleaner(args.db_path)
    
    # Create backup if requested
    if args.backup and not args.dry_run:
        if not cleaner.create_backup():
            logger.error("[ERROR] Backup failed - aborting operation for safety")
            sys.exit(1)
    
    # Clear the data
    success = cleaner.clear_all_data(dry_run=args.dry_run)
    
    if success and not args.dry_run:
        # Reset auto-increment counters if requested
        if args.reset_counters:
            cleaner.reset_auto_increment_counters()
        
        print("\n" + "="*60)
        print("[OK] DATABASE CLEARED SUCCESSFULLY")
        print("="*60)
        print(f"[SYMBOL] Database: {args.db_path}")
        if cleaner.backup_path:
            print(f"[SAVED] Backup: {cleaner.backup_path}")
        print("[RESULTS] All irrigation data has been deleted")
        print("[SYMBOL][SYMBOL]  Database schema and structure preserved")
        
    elif success and args.dry_run:
        print("\n[OK] Dry run completed - no data was modified")
        
    else:
        print("\n[ERROR] Operation failed - check logs for details")
        sys.exit(1)

if __name__ == "__main__":
    main()
