#!/usr/bin/env python3
"""
Database Connectivity Test Script
Tests database connection using environment variables from .env file
"""

import os
import sys
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import logging

# Configure logging for test output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables from .env file"""
    try:
        load_dotenv()
        logger.info("Environment variables loaded from .env file")
        return True
    except Exception as e:
        logger.error(f"Failed to load .env file: {e}")
        return False

def get_db_config():
    """Extract database configuration from environment variables"""
    config = {
        'host': os.getenv('DB_HOST'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_DATABASE') or os.getenv('DB_NAME'),
        'username': os.getenv('DB_USERNAME') or os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database_url': os.getenv('DATABASE_URL')
    }
    
    logger.info("Database configuration extracted:")
    logger.info(f"  Host: {config['host']}")
    logger.info(f"  Port: {config['port']}")
    logger.info(f"  Database: {config['database']}")
    logger.info(f"  Username: {config['username']}")
    logger.info(f"  Password: {'*' * len(config['password']) if config['password'] else 'None'}")
    logger.info(f"  Database URL: {'Set' if config['database_url'] else 'Not set'}")
    
    return config

def test_connection_individual_params(config):
    """Test connection using individual database parameters"""
    logger.info("\n=== Testing connection with individual parameters ===")
    
    if not all([config['host'], config['port'], config['database'], config['username'], config['password']]):
        logger.error("Missing required database parameters")
        return False
    
    try:
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            database=config['database'],
            user=config['username'],
            password=config['password']
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info(f"✅ Connection successful! PostgreSQL version: {version}")
        
        # Test basic query
        cursor.execute("SELECT NOW() as current_time;")
        current_time = cursor.fetchone()[0]
        logger.info(f"✅ Current database time: {current_time}")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        logger.error(f"❌ Connection failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def test_connection_url(database_url):
    """Test connection using DATABASE_URL"""
    logger.info("\n=== Testing connection with DATABASE_URL ===")
    
    if not database_url:
        logger.warning("DATABASE_URL not set, skipping URL-based test")
        return False
    
    try:
        conn = psycopg2.connect(database_url)
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info(f"✅ URL connection successful! PostgreSQL version: {version}")
        
        # Test basic query
        cursor.execute("SELECT NOW() as current_time;")
        current_time = cursor.fetchone()[0]
        logger.info(f"✅ Current database time: {current_time}")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        logger.error(f"❌ URL connection failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def test_database_tables(config):
    """Test if we can access irrigation-related tables"""
    logger.info("\n=== Testing database table access ===")
    
    try:
        # Try connection with DATABASE_URL first, then individual params
        if config['database_url']:
            conn = psycopg2.connect(config['database_url'])
        else:
            conn = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                database=config['database'],
                user=config['username'],
                password=config['password']
            )
        
        cursor = conn.cursor()
        
        # List all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            logger.info("✅ Available tables:")
            for table in tables:
                logger.info(f"  - {table[0]}")
        else:
            logger.warning("⚠️  No tables found in public schema")
        
        # Test common irrigation tables if they exist
        irrigation_tables = ['schedules', 'reported_runs', 'sensor_status', 'irrigation_schedules']
        for table_name in irrigation_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                logger.info(f"✅ Table '{table_name}': {count} records")
            except psycopg2.Error:
                logger.info(f"ℹ️  Table '{table_name}': Not found or no access")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        logger.error(f"❌ Table access test failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during table test: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🔌 Database Connectivity Test Starting...")
    logger.info("=" * 50)
    
    # Load environment
    if not load_environment():
        logger.error("Failed to load environment variables")
        sys.exit(1)
    
    # Get database configuration
    config = get_db_config()
    
    # Test connections
    success_count = 0
    total_tests = 0
    
    # Test individual parameters
    total_tests += 1
    if test_connection_individual_params(config):
        success_count += 1
    
    # Test DATABASE_URL
    total_tests += 1
    if test_connection_url(config['database_url']):
        success_count += 1
    
    # Test table access
    total_tests += 1
    if test_database_tables(config):
        success_count += 1
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info(f"🏁 Test Summary: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        logger.info("🎉 All database connectivity tests PASSED!")
        sys.exit(0)
    elif success_count > 0:
        logger.warning("⚠️  Some database tests FAILED - check configuration")
        sys.exit(1)
    else:
        logger.error("❌ All database tests FAILED - check credentials and connectivity")
        sys.exit(2)

if __name__ == "__main__":
    main()

