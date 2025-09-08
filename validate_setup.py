#!/usr/bin/env python3
"""
Hydrawise Setup Validation Script
Validates that all dependencies, configuration, and database setup are correct
"""

import sys
import os
import importlib
from pathlib import Path
import subprocess

def check_python_version():
    """Check Python version compatibility"""
    print("=== Python Version Check ===")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} (compatible)")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)")
        return False

def check_virtual_environment():
    """Check if running in virtual environment"""
    print("\n=== Virtual Environment Check ===")
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        venv_path = sys.prefix
        print(f"✓ Virtual environment active: {venv_path}")
        return True
    else:
        print("✗ No virtual environment detected")
        print("  Run: python -m venv hydrawise-venv")
        print("  Then: source hydrawise-venv/Scripts/activate")
        return False

def check_dependencies():
    """Check all required Python dependencies"""
    print("\n=== Dependencies Check ===")
    
    required_packages = {
        'selenium': 'selenium',
        'psycopg2': 'psycopg2-binary', 
        'dotenv': 'python-dotenv',
        'requests': 'requests',
        'bs4': 'beautifulsoup4',
        'webdriver_manager': 'webdriver-manager',
        'google.cloud.storage': 'google-cloud-storage',
        'pytz': 'pytz'
    }
    
    missing_packages = []
    
    for import_name, package_name in required_packages.items():
        try:
            importlib.import_module(import_name)
            print(f"✓ {package_name}")
        except ImportError:
            print(f"✗ {package_name} (missing)")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\nTo install missing packages:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_configuration():
    """Check environment configuration"""
    print("\n=== Configuration Check ===")
    
    if not Path('.env').exists():
        print("✗ .env file not found")
        print("  Copy env_local_example.txt to .env and configure")
        return False
    
    print("✓ .env file found")
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = [
            'HYDRAWISE_USER',  # Changed from HYDRAWISE_USERNAME
            'HYDRAWISE_PASSWORD', 
            'DATABASE_TYPE'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
                print(f"✗ {var} not set")
            else:
                if 'PASSWORD' in var:
                    print(f"✓ {var} = ********")
                else:
                    print(f"✓ {var} = {os.getenv(var)}")
        
        if missing_vars:
            print(f"\nMissing required environment variables: {', '.join(missing_vars)}")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Error loading configuration: {e}")
        return False

def check_database():
    """Check database connectivity"""
    print("\n=== Database Check ===")
    
    try:
        from database.universal_database_manager import get_universal_database_manager
        from dotenv import load_dotenv
        load_dotenv()
        
        db = get_universal_database_manager()
        
        # Get database type from environment
        db_type = os.getenv('DATABASE_TYPE', 'unknown')
        print(f"✓ Database type: {db_type}")
        
        # Test connection by trying a simple query
        try:
            # Test basic connectivity
            if db_type == 'postgresql':
                result = db.adapter.execute_query("SELECT 1 as test")
            else:
                result = db.adapter.execute_query("SELECT 1 as test")
            
            if result:
                print("✓ Database connection successful")
            else:
                print("✗ Database connection failed - no result")
                return False
                
            # Check if core tables exist
            try:
                result = db.adapter.execute_query("SELECT COUNT(*) as count FROM zones")
                zone_count = result[0]['count'] if result else 0
                print(f"✓ Zones table exists ({zone_count} zones)")
                
                result = db.adapter.execute_query("SELECT COUNT(*) as count FROM scheduled_runs")
                scheduled_count = result[0]['count'] if result else 0
                print(f"✓ Scheduled runs table exists ({scheduled_count} records)")
                
                return True
                
            except Exception as e:
                print(f"✗ Database schema issue: {e}")
                if db_type == 'postgresql':
                    print("  Run: python initialize_database.py")
                else:
                    print("  Tables will be created on first use")
                return False
                
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False
            
    except Exception as e:
        print(f"✗ Database check failed: {e}")
        return False

def check_chrome_setup():
    """Check Chrome and ChromeDriver setup"""
    print("\n=== Chrome/ChromeDriver Check ===")
    
    try:
        from selenium import webdriver
        from webdriver_manager.chrome import ChromeDriverManager
        
        # Check Chrome installation
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            chrome_version = driver.capabilities['browserVersion']
            driver.quit()
            print(f"✓ Chrome browser: {chrome_version}")
        except Exception as e:
            print(f"✗ Chrome browser issue: {e}")
            return False
        
        # Check ChromeDriver
        try:
            driver_path = ChromeDriverManager().install()
            print(f"✓ ChromeDriver: {driver_path}")
            return True
        except Exception as e:
            print(f"✗ ChromeDriver issue: {e}")
            return False
            
    except Exception as e:
        print(f"✗ Chrome setup check failed: {e}")
        return False

def check_directories():
    """Check required directories exist"""
    print("\n=== Directory Structure Check ===")
    
    required_dirs = [
        'database',
        'utils', 
        'config',
        'logs'
    ]
    
    all_exist = True
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"✓ {dir_name}/ directory exists")
        else:
            print(f"✗ {dir_name}/ directory missing")
            if dir_name == 'logs':
                Path(dir_name).mkdir(exist_ok=True)
                print(f"  Created {dir_name}/ directory")
            else:
                all_exist = False
    
    return all_exist

def check_key_files():
    """Check that key files exist"""
    print("\n=== Key Files Check ===")
    
    required_files = [
        'automated_collector.py',
        'requirements.txt',
        'database/postgresql_schema.sql',
        'database/universal_database_manager.py',
        'utils/universal_logging.py'
    ]
    
    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} (missing)")
            all_exist = False
    
    return all_exist

def run_basic_test():
    """Run a basic functionality test"""
    print("\n=== Basic Functionality Test ===")
    
    try:
        # Test database manager import
        from database.universal_database_manager import get_universal_database_manager
        print("✓ Database manager import")
        
        # Test logging setup
        from utils.universal_logging import setup_universal_logging
        logger = setup_universal_logging('test_validation')
        print("✓ Logging system")
        
        # Test timezone utilities
        from utils.timezone_utils import get_houston_now
        houston_time = get_houston_now()
        print(f"✓ Timezone utilities (Houston time: {houston_time})")
        
        return True
        
    except Exception as e:
        print(f"✗ Basic test failed: {e}")
        return False

def main():
    """Main validation function"""
    print("🔍 Hydrawise Setup Validation")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Virtual Environment", check_virtual_environment), 
        ("Dependencies", check_dependencies),
        ("Configuration", check_configuration),
        ("Database", check_database),
        ("Chrome Setup", check_chrome_setup),
        ("Directory Structure", check_directories),
        ("Key Files", check_key_files),
        ("Basic Functionality", run_basic_test)
    ]
    
    results = {}
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"\n✗ {check_name} check failed with error: {e}")
            results[check_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(checks)
    
    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
        if result:
            passed += 1
    
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Test with: python automated_collector.py --run-once")
        print("2. Set up NSSM service (see SETUP.md)")
        return 0
    else:
        print(f"\n⚠️  {total - passed} issues found. Please fix the failed checks.")
        print("See SETUP.md for detailed setup instructions.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
