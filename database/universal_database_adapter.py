#!/usr/bin/env python3
"""
Universal Database Adapter for Hydrawise
Provides a unified interface for both SQLite and PostgreSQL databases

This adapter allows the same code to work with both local SQLite databases
and render.com PostgreSQL databases by abstracting database-specific operations.

Author: AI Assistant
Date: 2025-01-27
"""

import os
import sys
import logging
import sqlite3
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime, date
from contextlib import contextmanager

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_config import get_database_config, is_postgresql, is_sqlite, validate_database_config

logger = logging.getLogger(__name__)

class UniversalDatabaseAdapter:
    """
    Universal database adapter that works with both SQLite and PostgreSQL
    
    Provides a consistent interface for database operations regardless of
    the underlying database system.
    """
    
    def __init__(self):
        """Initialize the database adapter"""
        self.config = get_database_config()
        self._connection = None
        self._transaction_depth = 0
        
        # Import appropriate database module
        if self.config.db_type == 'postgresql':
            try:
                import psycopg2
                import psycopg2.extras
                self.db_module = psycopg2
                self.dict_cursor_factory = psycopg2.extras.RealDictCursor
            except ImportError:
                raise ImportError(
                    "psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary"
                )
        else:
            self.db_module = sqlite3
            self.dict_cursor_factory = None
        
        logger.info(f"Initialized {self.config.db_type} database adapter")
    
    def get_connection(self):
        """Get database connection (creates if doesn't exist)"""
        if self._connection is None:
            self._connection = self._create_connection()
        return self._connection
    
    def _create_connection(self):
        """Create a new database connection"""
        if self.config.db_type == 'sqlite':
            conn = sqlite3.connect(self.config.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like row access
            return conn
        else:  # postgresql
            from database.db_config import get_connection_params
            return self.db_module.connect(**get_connection_params())
    
    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """
        Context manager for database cursors
        
        Args:
            dict_cursor: Whether to return dict-like rows (default: True)
        """
        conn = self.get_connection()
        
        if self.config.db_type == 'sqlite':
            cursor = conn.cursor()
        else:  # postgresql
            if dict_cursor and self.dict_cursor_factory:
                cursor = conn.cursor(cursor_factory=self.dict_cursor_factory)
            else:
                cursor = conn.cursor()
        
        try:
            yield cursor
        finally:
            cursor.close()
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self.get_connection()
        self._transaction_depth += 1
        
        try:
            if self._transaction_depth == 1:
                # Only begin transaction at top level
                if self.config.db_type == 'postgresql':
                    # PostgreSQL automatically starts transactions
                    pass
                else:  # sqlite
                    conn.execute("BEGIN")
            
            yield conn
            
            if self._transaction_depth == 1:
                conn.commit()
                
        except Exception as e:
            if self._transaction_depth == 1:
                conn.rollback()
            raise
        finally:
            self._transaction_depth -= 1
    
    def execute_query(self, query: str, params: Union[Tuple, Dict] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries
        
        Args:
            query: SQL query string
            params: Query parameters (tuple or dict)
            
        Returns:
            List of row dictionaries
        """
        with self.get_cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Convert rows to dictionaries
            if self.config.db_type == 'sqlite':
                return [dict(row) for row in cursor.fetchall()]
            else:  # postgresql with RealDictCursor
                return [dict(row) for row in cursor.fetchall()]
    
    def execute_insert(self, query: str, params: Union[Tuple, Dict] = None) -> Optional[int]:
        """
        Execute an INSERT query and return the inserted row ID
        
        Args:
            query: SQL INSERT statement
            params: Query parameters
            
        Returns:
            ID of inserted row (if applicable)
        """
        with self.transaction():
            with self.get_cursor(dict_cursor=False) as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                # Get inserted row ID
                if self.config.db_type == 'sqlite':
                    return cursor.lastrowid
                else:  # postgresql
                    # For PostgreSQL, we need to use RETURNING clause
                    # or fetch the ID separately if available
                    if "RETURNING" in query.upper():
                        result = cursor.fetchone()
                        return result[0] if result else None
                    else:
                        return None
    
    def execute_update(self, query: str, params: Union[Tuple, Dict] = None) -> int:
        """
        Execute an UPDATE query and return number of affected rows
        
        Args:
            query: SQL UPDATE statement
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        with self.transaction():
            with self.get_cursor(dict_cursor=False) as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                return cursor.rowcount
    
    def execute_delete(self, query: str, params: Union[Tuple, Dict] = None) -> int:
        """
        Execute a DELETE query and return number of affected rows
        
        Args:
            query: SQL DELETE statement
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        with self.transaction():
            with self.get_cursor(dict_cursor=False) as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                return cursor.rowcount
    
    def execute_script(self, script: str):
        """
        Execute a SQL script (multiple statements)
        
        Args:
            script: SQL script with multiple statements
        """
        with self.transaction():
            if self.config.db_type == 'sqlite':
                conn = self.get_connection()
                conn.executescript(script)
            else:  # postgresql
                # Split script into individual statements
                statements = [stmt.strip() for stmt in script.split(';') if stmt.strip()]
                with self.get_cursor(dict_cursor=False) as cursor:
                    for statement in statements:
                        cursor.execute(statement)
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        if self.config.db_type == 'sqlite':
            query = """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """
            params = (table_name,)
        else:  # postgresql
            query = """
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema='public' AND table_name=%s
            """
            params = (table_name,)
        
        result = self.execute_query(query, params)
        return len(result) > 0
    
    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get column information for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column information dictionaries
        """
        if self.config.db_type == 'sqlite':
            query = f"PRAGMA table_info({table_name})"
            result = self.execute_query(query)
            return [{'name': row['name'], 'type': row['type']} for row in result]
        else:  # postgresql
            query = """
                SELECT column_name as name, data_type as type
                FROM information_schema.columns 
                WHERE table_schema='public' AND table_name=%s
                ORDER BY ordinal_position
            """
            return self.execute_query(query, (table_name,))
    
    def adapt_sql_syntax(self, sql: str) -> str:
        """
        Adapt SQL syntax for the target database
        
        Args:
            sql: SQL statement that might need adaptation
            
        Returns:
            Adapted SQL statement
        """
        if self.config.db_type == 'postgresql':
            # Common SQLite to PostgreSQL adaptations
            adapted = sql
            
            # Replace SQLite-specific functions with PostgreSQL equivalents
            adapted = adapted.replace("datetime('now')", "NOW()")
            adapted = adapted.replace("date('now')", "CURRENT_DATE")
            adapted = adapted.replace("AUTOINCREMENT", "SERIAL")
            
            # Replace parameter placeholders
            # SQLite uses ? while PostgreSQL uses %s
            if '?' in adapted:
                # Simple replacement - might need more sophisticated handling
                param_count = adapted.count('?')
                for i in range(param_count):
                    adapted = adapted.replace('?', '%s', 1)
            
            return adapted
        else:
            # No adaptation needed for SQLite
            return sql
    
    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Database connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

# Convenience functions for common operations
def get_universal_adapter() -> UniversalDatabaseAdapter:
    """Get a configured universal database adapter"""
    return UniversalDatabaseAdapter()

def execute_schema_sql(schema_sql: str):
    """
    Execute schema SQL with database-specific adaptations
    
    Args:
        schema_sql: SQL schema script
    """
    with get_universal_adapter() as adapter:
        adapted_sql = adapter.adapt_sql_syntax(schema_sql)
        adapter.execute_script(adapted_sql)
        logger.info("Database schema executed successfully")

def test_database_connection() -> bool:
    """
    Test database connection and basic operations
    
    Returns:
        True if database is working properly
    """
    try:
        with get_universal_adapter() as adapter:
            # Test basic query
            if adapter.config.db_type == 'sqlite':
                result = adapter.execute_query("SELECT 1 as test")
            else:  # postgresql
                result = adapter.execute_query("SELECT 1 as test")
            
            if result and result[0]['test'] == 1:
                logger.info("Database connection test passed")
                return True
            else:
                logger.error("Database connection test failed - unexpected result")
                return False
                
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Test the adapter
    print("Testing Universal Database Adapter...")
    
    # Test configuration
    config = get_database_config()
    print(f"Database Type: {config.db_type}")
    print(f"Is Local: {config.is_local}")
    
    # Test connection
    if test_database_connection():
        print("✅ Database adapter is working correctly!")
    else:
        print("❌ Database adapter test failed!")
    
    # Test adapter operations
    try:
        with get_universal_adapter() as adapter:
            print(f"Connected to {adapter.config.db_type} database")
            
            # Test table existence check
            exists = adapter.table_exists('zones')
            print(f"Zones table exists: {exists}")
            
    except Exception as e:
        print(f"Error testing adapter: {e}")
