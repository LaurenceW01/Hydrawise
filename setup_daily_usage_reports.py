#!/usr/bin/env python3
"""
Setup script for Daily Usage Analytics Reports

This script helps configure and enable daily usage analytics email reports
with progressive day window expansion (2 days -> 30 days).

Author: AI Assistant
Date: 2025-09-15
"""

import os
import sys
import logging

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from add_system_config_table import add_system_config_table
from daily_usage_analytics_report import load_config_from_env, DailyUsageAnalyticsReporter
# Using basic logging instead of universal_logging

logger = logging.getLogger(__name__)

def setup_database():
    """Setup database requirements"""
    print("Setting up database requirements...")
    
    success = add_system_config_table()
    if success:
        print("✓ system_config table ready")
        return True
    else:
        print("✗ Failed to create system_config table")
        return False

def check_configuration():
    """Check current configuration"""
    print("\nChecking current configuration...")
    
    config = load_config_from_env()
    
    print(f"  Enabled: {config.enabled}")
    print(f"  Email Recipients: {config.email_recipients}")
    print(f"  SMTP Server: {config.smtp_server}:{config.smtp_port}")
    print(f"  SMTP Username: {config.smtp_username}")
    print(f"  SMTP Password: {'***' if config.smtp_password else '(not set)'}")
    print(f"  From Address: {config.smtp_from_address}")
    print(f"  Start Days: {config.start_days}")
    print(f"  Max Days: {config.max_days}")
    print(f"  Days Increment: {config.days_increment}")
    print(f"  Report Time: {config.report_time_hour}:00 Houston time")
    
    # Check if configuration is complete
    missing = []
    if not config.email_recipients:
        missing.append("EMAIL_RECIPIENTS")
    if not config.smtp_username:
        missing.append("SMTP_USERNAME")
    if not config.smtp_password:
        missing.append("SMTP_PASSWORD")
    
    if missing:
        print(f"\n⚠️  Missing configuration: {', '.join(missing)}")
        return False, missing
    else:
        print("\n✓ Configuration complete")
        return True, []

def show_environment_variables():
    """Show required environment variables"""
    print("\nRequired Environment Variables:")
    print("=" * 50)
    print("# Enable/disable daily reports")
    print("DAILY_USAGE_REPORTS_ENABLED=true")
    print("")
    print("# Email configuration")
    print("EMAIL_RECIPIENTS=your-email@example.com,another@example.com")
    print("SMTP_SERVER=smtp.gmail.com")
    print("SMTP_PORT=587")
    print("SMTP_USERNAME=your-email@gmail.com")
    print("SMTP_PASSWORD=your-app-password")
    print("SMTP_FROM_ADDRESS=your-email@gmail.com")
    print("")
    print("# Report parameters (optional)")
    print("DAILY_REPORT_START_DAYS=2")
    print("DAILY_REPORT_MAX_DAYS=30")
    print("DAILY_REPORT_DAYS_INCREMENT=1")
    print("DAILY_REPORT_TIME_HOUR=7")
    print("")
    print("Add these to your .env file or set as environment variables.")

def test_email_sending():
    """Test email sending functionality"""
    print("\nTesting email functionality...")
    
    try:
        config = load_config_from_env()
        if not config.enabled:
            print("✗ Daily reports are disabled")
            return False
        
        reporter = DailyUsageAnalyticsReporter(config)
        
        if not reporter.email_manager:
            print("✗ Email manager not initialized (check email configuration)")
            return False
        
        print("✓ Email manager initialized successfully")
        
        # Generate a test report (dry run)
        analysis_days = reporter._get_current_analysis_window()
        report_content = reporter.generate_report_content(analysis_days)
        
        if report_content and not report_content.startswith("Error"):
            print(f"✓ Report generation successful ({analysis_days} day analysis)")
            print(f"  Report length: {len(report_content)} characters")
            return True
        else:
            print("✗ Report generation failed")
            return False
            
    except Exception as e:
        print(f"✗ Error testing email functionality: {e}")
        return False

def show_integration_instructions():
    """Show instructions for integrating with automated collector"""
    print("\nIntegration with Automated Collector:")
    print("=" * 50)
    print("To integrate daily usage analytics with your automated collector,")
    print("add the following code to your automated_collector.py:")
    print("")
    print("# At the top of the file, add import:")
    print("from integrate_daily_usage_analytics import integrate_with_automated_collector, add_to_daily_collection")
    print("")
    print("# In your AutomatedCollector.__init__ method, add:")
    print("self.analytics_integration = integrate_with_automated_collector()")
    print("")
    print("# In your daily collection method, add after data collection:")
    print("if self.analytics_integration:")
    print("    add_to_daily_collection(self.analytics_integration)")
    print("")
    print("This will automatically send daily usage analytics reports")
    print("at the configured time during your daily collection process.")

def main():
    """Main setup function"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("Daily Usage Analytics Reports Setup")
    print("=" * 50)
    
    # Step 1: Setup database
    if not setup_database():
        print("\n❌ Database setup failed. Please check the logs and try again.")
        return 1
    
    # Step 2: Check configuration
    config_complete, missing = check_configuration()
    
    if not config_complete:
        print(f"\n⚠️  Configuration incomplete. Missing: {', '.join(missing)}")
        show_environment_variables()
        print("\nPlease configure the missing variables and run setup again.")
        return 1
    
    # Step 3: Test email functionality
    if not test_email_sending():
        print("\n⚠️  Email testing failed. Please check your email configuration.")
        return 1
    
    # Step 4: Show integration instructions
    show_integration_instructions()
    
    print("\n✅ Setup completed successfully!")
    print("\nYour daily usage analytics reports are ready to use.")
    print("Reports will start with a 2-day analysis window and gradually")
    print("expand to 30 days over time.")
    print("")
    print("To test manually, run:")
    print("  python daily_usage_analytics_report.py --dry-run")
    print("")
    print("To send a report immediately, run:")
    print("  python daily_usage_analytics_report.py --force")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
