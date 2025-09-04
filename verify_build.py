#!/usr/bin/env python3
"""
Build Verification Script for Render.com
Checks if all required dependencies are installed correctly

Run this to verify the build environment before starting the main application.
"""

import sys
import os
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    logger.info(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major != 3 or version.minor < 8:
        logger.error("Python 3.8+ is required")
        return False
    
    return True

def check_required_packages():
    """Check if all required packages can be imported"""
    required_packages = [
        ('selenium', 'Web scraping'),
        ('requests', 'HTTP requests'),
        ('beautifulsoup4', 'HTML parsing'),
        ('pytz', 'Timezone handling'),
        ('python-dotenv', 'Environment variables'),
    ]
    
    optional_packages = [
        ('psycopg2', 'PostgreSQL database support'),
        ('google.cloud.storage', 'Google Cloud Storage'),
    ]
    
    all_good = True
    
    logger.info("Checking required packages...")
    for package_name, description in required_packages:
        try:
            if package_name == 'beautifulsoup4':
                import bs4
                logger.info(f"✅ {package_name} ({description}) - OK")
            elif package_name == 'python-dotenv':
                import dotenv
                logger.info(f"✅ {package_name} ({description}) - OK")
            else:
                __import__(package_name)
                logger.info(f"✅ {package_name} ({description}) - OK")
        except ImportError as e:
            logger.error(f"❌ {package_name} ({description}) - MISSING: {e}")
            all_good = False
    
    logger.info("Checking optional packages...")
    for package_name, description in optional_packages:
        try:
            if package_name == 'google.cloud.storage':
                from google.cloud import storage
                logger.info(f"✅ {package_name} ({description}) - OK")
            else:
                __import__(package_name)
                logger.info(f"✅ {package_name} ({description}) - OK")
        except ImportError as e:
            logger.warning(f"⚠️  {package_name} ({description}) - MISSING: {e}")
    
    return all_good

def check_environment_variables():
    """Check critical environment variables"""
    logger.info("Checking environment variables...")
    
    # Critical variables
    critical_vars = ['DATABASE_TYPE']
    missing_critical = []
    
    for var in critical_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var}: {value}")
        else:
            logger.error(f"❌ {var}: NOT SET")
            missing_critical.append(var)
    
    # Important variables (warn if missing)
    important_vars = ['DATABASE_URL', 'HYDRAWISE_USERNAME', 'HYDRAWISE_PASSWORD']
    for var in important_vars:
        value = os.getenv(var)
        if value:
            # Don't log sensitive values, just confirm they exist
            if 'PASSWORD' in var or 'URL' in var:
                logger.info(f"✅ {var}: SET (hidden)")
            else:
                logger.info(f"✅ {var}: {value}")
        else:
            logger.warning(f"⚠️  {var}: NOT SET")
    
    # Render.com specific variables
    render_vars = ['RENDER', 'RENDER_SERVICE_ID', 'PORT']
    for var in render_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var}: {value}")
        else:
            logger.info(f"ℹ️  {var}: Not set (normal for local development)")
    
    return len(missing_critical) == 0

def check_database_config():
    """Check database configuration"""
    logger.info("Checking database configuration...")
    
    try:
        # Import our database configuration
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from database.db_config import get_database_config, validate_database_config
        
        config = get_database_config()
        logger.info(f"✅ Database type: {config.db_type}")
        logger.info(f"✅ Is local: {config.is_local}")
        
        # Test connection
        if validate_database_config():
            logger.info("✅ Database connection: OK")
            return True
        else:
            logger.error("❌ Database connection: FAILED")
            return False
            
    except Exception as e:
        logger.error(f"❌ Database configuration error: {e}")
        return False

def main():
    """Main verification function"""
    logger.info("=== RENDER.COM BUILD VERIFICATION ===")
    
    checks = [
        ("Python Version", check_python_version),
        ("Required Packages", check_required_packages),
        ("Environment Variables", check_environment_variables),
        ("Database Configuration", check_database_config),
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        logger.info(f"\n--- {check_name} ---")
        try:
            if not check_func():
                all_passed = False
                logger.error(f"{check_name}: FAILED")
            else:
                logger.info(f"{check_name}: PASSED")
        except Exception as e:
            logger.error(f"{check_name}: ERROR - {e}")
            all_passed = False
    
    logger.info("\n=== VERIFICATION SUMMARY ===")
    if all_passed:
        logger.info("✅ All checks passed! Ready for deployment.")
        return 0
    else:
        logger.error("❌ Some checks failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
