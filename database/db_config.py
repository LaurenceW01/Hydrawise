#!/usr/bin/env python3
"""
Database Configuration Module for Hydrawise
Handles configuration for both local SQLite and render.com PostgreSQL databases

Environment Variables:
- DATABASE_TYPE: 'sqlite' (default) or 'postgresql'
- DATABASE_URL: PostgreSQL connection string (for render.com)
- DB_PATH: Local SQLite database path (default: database/irrigation_data.db)
- DB_HOST: PostgreSQL host (alternative to DATABASE_URL)
- DB_PORT: PostgreSQL port (default: 5432)
- DB_NAME: PostgreSQL database name
- DB_USER: PostgreSQL username
- DB_PASSWORD: PostgreSQL password
- DB_SSL_MODE: PostgreSQL SSL mode (default: require)

Author: AI Assistant
Date: 2025-01-27
"""

import os
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    db_type: str  # 'sqlite' or 'postgresql'
    connection_string: str
    is_local: bool
    requires_schema_creation: bool = True
    
    # SQLite specific
    db_path: Optional[str] = None
    
    # PostgreSQL specific
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_mode: Optional[str] = None

def get_database_config() -> DatabaseConfig:
    """
    Get database configuration based on environment variables
    
    Returns:
        DatabaseConfig: Configuration object for the database
    """
    # Determine database type from environment
    db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
    
    logger.info(f"Database type from environment: '{db_type}'")
    
    if db_type == 'postgresql':
        logger.info("Configuring PostgreSQL database")
        return _get_postgresql_config()
    elif db_type in ['postgressql', 'postgres']:  # Handle common typos
        logger.warning(f"Found typo in DATABASE_TYPE: '{db_type}', treating as 'postgresql'")
        return _get_postgresql_config()
    else:
        logger.info("Configuring SQLite database")
        return _get_sqlite_config()

def _get_sqlite_config() -> DatabaseConfig:
    """Configure SQLite database (local development)"""
    # Get database path from environment or use default
    db_path = os.getenv('DB_PATH', 'database/irrigation_data.db')
    
    # Ensure absolute path for consistency
    if not os.path.isabs(db_path):
        # Make relative to project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(project_root, db_path)
    
    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    logger.info(f"Configured SQLite database: {db_path}")
    
    return DatabaseConfig(
        db_type='sqlite',
        connection_string=f"sqlite:///{db_path}",
        is_local=True,
        requires_schema_creation=True,
        db_path=db_path
    )

def _get_postgresql_config() -> DatabaseConfig:
    """Configure PostgreSQL database (render.com deployment)"""
    # Check for DATABASE_URL first (render.com standard)
    database_url = os.getenv('DATABASE_URL')
    
    logger.info(f"DATABASE_URL present: {bool(database_url)}")
    if database_url:
        logger.info("Using DATABASE_URL for PostgreSQL connection")
        # Parse the DATABASE_URL
        parsed = urlparse(database_url)
        
        config = DatabaseConfig(
            db_type='postgresql',
            connection_string=database_url,
            is_local=False,
            requires_schema_creation=True,
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/'),
            username=parsed.username,
            password=parsed.password,
            ssl_mode='require'
        )
        
        logger.info(f"Configured PostgreSQL from DATABASE_URL: {parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}")
        return config
    
    # Alternative: individual environment variables
    host = os.getenv('DB_HOST')
    port = int(os.getenv('DB_PORT', '5432'))
    database = os.getenv('DB_NAME')
    username = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    ssl_mode = os.getenv('DB_SSL_MODE', 'require')
    
    if not all([host, database, username, password]):
        logger.error("PostgreSQL configuration incomplete:")
        logger.error(f"  DB_HOST: {'SET' if host else 'MISSING'}")
        logger.error(f"  DB_NAME: {'SET' if database else 'MISSING'}")
        logger.error(f"  DB_USER: {'SET' if username else 'MISSING'}")
        logger.error(f"  DB_PASSWORD: {'SET' if password else 'MISSING'}")
        raise ValueError(
            "PostgreSQL configuration incomplete. Either set DATABASE_URL or "
            "provide DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD environment variables."
        )
    
    # Construct connection string
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}?sslmode={ssl_mode}"
    
    config = DatabaseConfig(
        db_type='postgresql',
        connection_string=connection_string,
        is_local=False,
        requires_schema_creation=True,
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        ssl_mode=ssl_mode
    )
    
    logger.info(f"Configured PostgreSQL: {host}:{port}/{database}")
    return config

def get_connection_params() -> Dict[str, Any]:
    """
    Get connection parameters for the configured database
    
    Returns:
        Dict with connection parameters suitable for database libraries
    """
    config = get_database_config()
    
    if config.db_type == 'sqlite':
        return {
            'database': config.db_path,
            'isolation_level': None  # Autocommit mode for SQLite
        }
    else:  # postgresql
        return {
            'host': config.host,
            'port': config.port,
            'database': config.database,
            'user': config.username,
            'password': config.password,
            'sslmode': config.ssl_mode
        }

def get_sqlalchemy_url() -> str:
    """
    Get SQLAlchemy-compatible database URL
    
    Returns:
        Database URL string for SQLAlchemy
    """
    config = get_database_config()
    return config.connection_string

def is_postgresql() -> bool:
    """Check if configured database is PostgreSQL"""
    return get_database_config().db_type == 'postgresql'

def is_sqlite() -> bool:
    """Check if configured database is SQLite"""
    return get_database_config().db_type == 'sqlite'

def validate_database_config() -> bool:
    """
    Validate database configuration and test connectivity
    
    Returns:
        True if configuration is valid and connection works
    """
    try:
        config = get_database_config()
        
        if config.db_type == 'sqlite':
            # Test SQLite connection
            import sqlite3
            with sqlite3.connect(config.db_path) as conn:
                conn.execute("SELECT 1").fetchone()
            logger.info("SQLite database connection validated")
            return True
            
        else:  # postgresql
            # Test PostgreSQL connection
            try:
                import psycopg2
            except ImportError as e:
                logger.error("psycopg2 not installed for PostgreSQL support")
                logger.error("This is required for render.com PostgreSQL databases")
                logger.error("Possible solutions:")
                logger.error("1. Check if psycopg2-binary is in requirements.txt")
                logger.error("2. Clear render.com build cache and redeploy")
                logger.error("3. Check build logs for installation errors")
                logger.error(f"Import error details: {e}")
                return False
                
            params = get_connection_params()
            with psycopg2.connect(**params) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            logger.info("PostgreSQL database connection validated")
            return True
            
    except Exception as e:
        logger.error(f"Database configuration validation failed: {e}")
        return False

# Environment variable documentation for render.com deployment
RENDER_ENV_DOCS = """
# Render.com Environment Variables for PostgreSQL Database

# Required for PostgreSQL (render.com will provide DATABASE_URL automatically):
DATABASE_TYPE=postgresql

# The DATABASE_URL will be automatically provided by render.com when you
# add a PostgreSQL database service. It typically looks like:
# DATABASE_URL=postgresql://username:password@hostname:port/database_name

# Optional overrides (usually not needed with render.com):
# DB_SSL_MODE=require
"""

# Local development environment variable documentation
LOCAL_ENV_DOCS = """
# Local Development Environment Variables for SQLite Database

# Use SQLite for local development:
DATABASE_TYPE=sqlite

# Optional: Custom SQLite database path
# DB_PATH=database/irrigation_data.db

# For testing PostgreSQL locally with Docker:
# DATABASE_TYPE=postgresql
# DATABASE_URL=postgresql://hydrawise:password@localhost:5432/hydrawise_db
"""

if __name__ == "__main__":
    # Test configuration
    print("Testing database configuration...")
    config = get_database_config()
    print(f"Database Type: {config.db_type}")
    print(f"Connection String: {config.connection_string}")
    print(f"Is Local: {config.is_local}")
    
    if validate_database_config():
        print("✅ Database configuration is valid!")
    else:
        print("❌ Database configuration failed!")
