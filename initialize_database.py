#!/usr/bin/env python3
"""
Database Initialization Script
Initializes PostgreSQL or SQLite database with proper schema
"""

import sys
import os
from pathlib import Path

def load_environment():
    """Load environment variables"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ Environment variables loaded")
        return True
    except ImportError:
        print("✗ python-dotenv not installed. Run: pip install python-dotenv")
        return False
    except Exception as e:
        print(f"✗ Error loading environment: {e}")
        return False

def check_database_config():
    """Check database configuration"""
    database_type = os.getenv('DATABASE_TYPE', 'sqlite')
    print(f"Database type: {database_type}")
    
    if database_type == 'postgresql':
        required_vars = ['DATABASE_URL']
        # Alternative: individual parameters
        alt_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        
        has_database_url = os.getenv('DATABASE_URL')
        has_individual_params = all(os.getenv(var) for var in alt_vars)
        
        if not (has_database_url or has_individual_params):
            print("✗ Missing PostgreSQL configuration")
            print("  Either set DATABASE_URL or all of: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
            return False
        
        print("✓ PostgreSQL configuration found")
        return True
        
    elif database_type == 'sqlite':
        db_path = os.getenv('DB_PATH', 'database/irrigation_data.db')
        print(f"SQLite database path: {db_path}")
        return True
    
    else:
        print(f"✗ Unknown database type: {database_type}")
        return False

def initialize_postgresql():
    """Initialize PostgreSQL database"""
    print("\n=== Initializing PostgreSQL Database ===")
    
    try:
        from database.universal_database_manager import get_universal_database_manager
        
        db = get_universal_database_manager()
        
        # Test connection
        if not db.test_connection():
            print("✗ Cannot connect to PostgreSQL database")
            return False
        
        print("✓ Connected to PostgreSQL")
        
        # Load and execute schema
        schema_file = Path('database/postgresql_schema.sql')
        if not schema_file.exists():
            print("✗ Schema file not found: database/postgresql_schema.sql")
            return False
        
        print("Loading schema from postgresql_schema.sql...")
        
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        # Split schema into individual statements
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        created_tables = 0
        for statement in statements:
            if statement.upper().startswith('CREATE TABLE'):
                try:
                    db.adapter.execute_update(statement + ';')
                    # Extract table name
                    table_name = statement.split('CREATE TABLE IF NOT EXISTS')[1].split('(')[0].strip()
                    print(f"  ✓ Created/verified table: {table_name}")
                    created_tables += 1
                except Exception as e:
                    if 'already exists' in str(e).lower():
                        table_name = statement.split('CREATE TABLE IF NOT EXISTS')[1].split('(')[0].strip()
                        print(f"  ✓ Table already exists: {table_name}")
                    else:
                        print(f"  ✗ Error creating table: {e}")
        
        print(f"\n✓ Schema initialization completed ({created_tables} tables processed)")
        
        # Verify core tables exist
        core_tables = ['zones', 'scheduled_runs', 'actual_runs']
        for table in core_tables:
            try:
                result = db.adapter.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                count = result[0]['count'] if result else 0
                print(f"  ✓ {table}: {count} records")
            except Exception as e:
                print(f"  ✗ {table}: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ PostgreSQL initialization failed: {e}")
        return False

def initialize_sqlite():
    """Initialize SQLite database"""
    print("\n=== Initializing SQLite Database ===")
    
    try:
        from database.universal_database_manager import get_universal_database_manager
        
        db = get_universal_database_manager()
        
        # Test connection (will create database if it doesn't exist)
        if not db.test_connection():
            print("✗ Cannot create/connect to SQLite database")
            return False
        
        print("✓ Connected to SQLite database")
        
        # For SQLite, the schema is typically created automatically by the application
        # Verify core tables exist
        core_tables = ['zones', 'scheduled_runs', 'actual_runs']
        tables_exist = 0
        
        for table in core_tables:
            try:
                result = db.adapter.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                count = result[0]['count'] if result else 0
                print(f"  ✓ {table}: {count} records")
                tables_exist += 1
            except Exception:
                print(f"  ⚠ {table}: table will be created on first use")
        
        if tables_exist > 0:
            print("✓ SQLite database initialized")
        else:
            print("✓ SQLite database ready (tables will be created on first use)")
        
        return True
        
    except Exception as e:
        print(f"✗ SQLite initialization failed: {e}")
        return False

def verify_setup():
    """Verify the setup is working"""
    print("\n=== Verification ===")
    
    try:
        from database.universal_database_manager import get_universal_database_manager
        
        db = get_universal_database_manager()
        connection_info = db.get_connection_info()
        
        print(f"✓ Database manager initialized")
        print(f"  Type: {connection_info.get('type', 'unknown')}")
        print(f"  Status: Connected")
        
        # Test a simple query
        try:
            if connection_info.get('type') == 'postgresql':
                result = db.adapter.execute_query("SELECT version()")
                if result:
                    print(f"  Version: {result[0].get('version', 'unknown')[:50]}...")
            else:
                result = db.adapter.execute_query("SELECT sqlite_version()")
                if result:
                    print(f"  SQLite Version: {result[0].get('sqlite_version()', 'unknown')}")
        except Exception as e:
            print(f"  ⚠ Version query failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        return False

def main():
    """Main initialization function"""
    print("🔧 Hydrawise Database Initialization")
    print("=" * 50)
    
    # Step 1: Load environment
    if not load_environment():
        return 1
    
    # Step 2: Check database configuration  
    if not check_database_config():
        return 1
    
    # Step 3: Initialize based on database type
    database_type = os.getenv('DATABASE_TYPE', 'sqlite')
    
    if database_type == 'postgresql':
        success = initialize_postgresql()
    elif database_type == 'sqlite':
        success = initialize_sqlite()
    else:
        print(f"✗ Unsupported database type: {database_type}")
        return 1
    
    if not success:
        return 1
    
    # Step 4: Verify setup
    if not verify_setup():
        return 1
    
    print("\n" + "=" * 50)
    print("🎉 Database initialization completed successfully!")
    print("\nNext steps:")
    print("1. Test with: python validate_setup.py")
    print("2. Run collector: python automated_collector.py --run-once")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
