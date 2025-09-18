#!/usr/bin/env python3
"""
Daily Usage Analytics Report System

Automated daily email report for irrigation usage analytics with progressive
day window expansion (starts at 2 days, grows to 30 days rolling window).

Integrates with existing email notification system and can be run standalone
or integrated into the automated collector.

Author: AI Assistant
Date: 2025-09-15
"""

import os
import sys
import logging
import json
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
import io
from contextlib import redirect_stdout

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.usage_analytics import UsageAnalytics
from database.universal_database_manager import get_universal_database_manager
from utils.timezone_utils import get_houston_now, get_display_timestamp
# Using basic logging instead of universal_logging
from utils.email_notifications import EmailNotificationManager, EmailConfig

logger = logging.getLogger(__name__)

@dataclass
class DailyReportConfig:
    """Configuration for daily usage analytics reports"""
    enabled: bool = True
    email_recipients: list = None
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    
    # Report parameters
    start_days: int = 2                    # Start with 2-day window
    max_days: int = 30                     # Maximum 30-day rolling window
    days_increment: int = 1                # Add 1 day each report until max
    report_time_hour: int = 7              # Send at 7:00 AM Houston time [[memory:7198787]]
    
    # Storage for tracking progress
    current_days: Optional[int] = None     # Current analysis window size
    
    def __post_init__(self):
        """Initialize default values"""
        if self.email_recipients is None:
            self.email_recipients = []
        if not self.smtp_from_address and self.smtp_username:
            self.smtp_from_address = self.smtp_username

class DailyUsageAnalyticsReporter:
    """
    Daily usage analytics report generator and emailer
    
    Features:
    - Progressive day window expansion (2 -> 30 days)
    - Integration with existing email system
    - Detailed usage flag analysis
    - Zone health monitoring
    - Automatic scheduling support
    """
    
    def __init__(self, config: DailyReportConfig):
        """
        Initialize the daily reporter
        
        Args:
            config: Configuration for daily reports
        """
        self.config = config
        self.logger = logger
        self.analytics = UsageAnalytics()
        self.db_manager = get_universal_database_manager()
        
        # Initialize email manager if email is configured
        self.email_manager = None
        if self._is_email_configured():
            self.email_manager = self._create_email_manager()
    
    def _is_email_configured(self) -> bool:
        """Check if email configuration is complete"""
        return (
            self.config.enabled and
            self.config.email_recipients and
            self.config.smtp_username and
            self.config.smtp_password
        )
    
    def _create_email_manager(self) -> EmailNotificationManager:
        """Create email manager from config"""
        email_config = EmailConfig(
            enabled=True,
            recipients=self.config.email_recipients,
            smtp_server=self.config.smtp_server,
            smtp_port=self.config.smtp_port,
            username=self.config.smtp_username,
            password=self.config.smtp_password,
            from_address=self.config.smtp_from_address,
            max_emails_per_day=1
        )
        return EmailNotificationManager(email_config)
    
    def _get_current_analysis_window(self) -> int:
        """
        Get current analysis window size with progressive expansion
        
        Logic:
        - Check if we have a start date configured
        - If so, calculate days since start date with progressive buildup
        - Otherwise, use stored window size or default
        - Cap at max_days (default 30)
        
        Uses database to track progress across runs
        """
        try:
            # Check if we have a configured start date
            start_date_result = self.db_manager.adapter.execute_query("""
                SELECT config_value 
                FROM system_config 
                WHERE config_key = 'daily_report_start_date'
                LIMIT 1
            """)
            
            if start_date_result:
                # We have a start date - calculate progressive window
                start_date_str = start_date_result[0]['config_value']
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                current_date = get_houston_now().date()
                
                days_since_start = (current_date - start_date).days + 1  # +1 to include start date
                
                # Progressive buildup: start with 2 days, add 1 day for each day since start
                if days_since_start <= 1:
                    current_days = 2  # Minimum 2 days
                else:
                    current_days = min(2 + (days_since_start - 1), self.config.max_days)
                
                self.logger.debug(f"Calculated analysis window: {current_days} days (start: {start_date}, days since: {days_since_start})")
                
                # Update stored value for consistency
                self._store_current_window(current_days)
                
                return current_days
            
            # No start date configured - use stored window size
            result = self.db_manager.adapter.execute_query("""
                SELECT config_value 
                FROM system_config 
                WHERE config_key = 'daily_report_analysis_days'
                LIMIT 1
            """)
            
            if result:
                current_days = int(result[0]['config_value'])
                self.logger.debug(f"Retrieved stored analysis window: {current_days} days")
            else:
                # First time running - start with initial window
                current_days = self.config.start_days
                self.logger.info(f"First time running daily report - starting with {current_days} days")
                
                # Store initial value
                self._store_current_window(current_days)
            
            return min(current_days, self.config.max_days)
            
        except Exception as e:
            self.logger.warning(f"Error getting current analysis window, using default: {e}")
            return self.config.start_days
    
    def _store_current_window(self, days: int):
        """Store current analysis window size"""
        try:
            # Use upsert to handle both insert and update
            self.db_manager.adapter.execute_update("""
                INSERT INTO system_config (config_key, config_value, updated_at)
                VALUES ('daily_report_analysis_days', %s, %s)
                ON CONFLICT (config_key) 
                DO UPDATE SET 
                    config_value = EXCLUDED.config_value,
                    updated_at = EXCLUDED.updated_at
            """, (str(days), get_houston_now()))
            
            self.logger.debug(f"Stored analysis window: {days} days")
            
        except Exception as e:
            self.logger.error(f"Error storing current analysis window: {e}")
    
    def _increment_analysis_window(self, current_days: int) -> int:
        """
        Calculate next analysis window size
        
        If we have a start date configured, the window size is calculated automatically
        based on days since start date. Otherwise, increment manually.
        
        Args:
            current_days: Current window size
            
        Returns:
            New window size for next run (or current size if auto-calculated)
        """
        try:
            # Check if we have a start date configured
            start_date_result = self.db_manager.adapter.execute_query("""
                SELECT config_value 
                FROM system_config 
                WHERE config_key = 'daily_report_start_date'
                LIMIT 1
            """)
            
            if start_date_result:
                # We have a start date - window size is auto-calculated, just return current
                self.logger.debug(f"Analysis window auto-calculated from start date: {current_days} days")
                return current_days
            
            # No start date - use manual increment logic
            if current_days >= self.config.max_days:
                # Already at maximum - stay at max (rolling 30-day window)
                next_days = self.config.max_days
                self.logger.debug(f"Analysis window at maximum: {next_days} days (rolling)")
            else:
                # Increment by configured amount
                next_days = min(current_days + self.config.days_increment, self.config.max_days)
                self.logger.info(f"Incrementing analysis window: {current_days} -> {next_days} days")
            
            # Store for next run
            self._store_current_window(next_days)
            return next_days
            
        except Exception as e:
            self.logger.warning(f"Error calculating next analysis window: {e}")
            return current_days
    
    def generate_report_content(self, analysis_days: int, target_date: date = None) -> str:
        """
        Generate usage analytics report content
        
        Args:
            analysis_days: Number of days to analyze
            target_date: Target date for analysis (defaults to yesterday)
            
        Returns:
            Report content as string
        """
        if target_date is None:
            target_date = get_houston_now().date() - timedelta(days=1)
        
        start_date = target_date - timedelta(days=analysis_days - 1)
        
        self.logger.info(f"Generating usage analytics report for {start_date} to {target_date} ({analysis_days} days)")
        
        # Capture the analytics output
        output_buffer = io.StringIO()
        
        try:
            # Get usage flag analysis
            analysis = self.analytics.analyze_usage_flags(start_date, target_date)
            
            # Generate report header
            report_lines = [
                "=" * 80,
                f"DAILY HYDRAWISE USAGE ANALYTICS REPORT",
                "=" * 80,
                f"Report Generated: {get_display_timestamp(get_houston_now())} (Houston Time)",
                f"Analysis Period: {start_date} to {target_date} ({analysis_days} days)",
                ""
            ]
            
            # Add summary analysis
            missing_info = analysis.missing_usage_analysis
            report_lines.extend([
                "[SUMMARY] Actual vs Expected Usage Analysis:",
                f"  Total Reported Usage: {missing_info['total_actual_usage']:.2f} gallons (includes {missing_info['estimated_gallons_used']:.2f}g estimated for zero reported)",
                f"  Total Expected Usage: {missing_info['total_calculated_usage']:.2f} gallons",
            ])
            
            # Add variance analysis
            variance_pct = missing_info['missing_percentage']
            if variance_pct > 0:
                report_lines.append(f"  Variance: {variance_pct:.1f}% UNDER expected (zones reported lower usage than expected)")
            elif variance_pct < 0:
                report_lines.append(f"  Variance: {abs(variance_pct):.1f}% OVER expected (zones reported higher usage than expected)")
            else:
                report_lines.append(f"  Variance: {variance_pct:.1f}% (perfect match)")
            
            report_lines.append("")
            
            # Add overall flag distribution
            total_runs = sum(analysis.flag_counts.values())
            if total_runs > 0:
                normal_count = analysis.flag_counts.get('normal', 0)
                too_high_count = analysis.flag_counts.get('too_high', 0)
                too_low_count = analysis.flag_counts.get('too_low', 0)
                zero_reported_count = analysis.flag_counts.get('zero_reported', 0)
                
                report_lines.extend([
                    "[RESULTS] Overall Usage Flag Distribution:",
                    f"  NORMAL: {normal_count} runs ({normal_count/total_runs*100:.1f}%)",
                    f"  TOO_HIGH: {too_high_count} runs ({too_high_count/total_runs*100:.1f}%)",
                    f"  TOO_LOW: {too_low_count} runs ({too_low_count/total_runs*100:.1f}%)",
                    f"  ZERO_REPORTED: {zero_reported_count} runs ({zero_reported_count/total_runs*100:.1f}%)",
                    f"  TOTAL: {total_runs} runs",
                    ""
                ])
            
            # Add problematic zones
            if analysis.problematic_zones:
                report_lines.append("[ALERT] Problematic Zones Detected:")
                for zone in analysis.problematic_zones:
                    if zone['issue'] == 'high_zero_reported':
                        report_lines.append(f"  - {zone['zone_name']}: Zone has {zone.get('count', 'multiple')} zero-reported runs out of {zone.get('total', 'unknown')} total")
                    else:
                        report_lines.append(f"  - {zone['zone_name']}: {zone['issue']}")
                report_lines.append("")
            
            # Add zone-by-zone analysis (top 10 most problematic zones)
            zone_patterns = list(analysis.zone_flag_patterns.items())
            # Sort by variance percentage (absolute value) to show most problematic first
            zone_patterns.sort(key=lambda x: abs(x[1]['missing_usage_percentage']), reverse=True)
            
            if zone_patterns:
                report_lines.extend([
                    "[DETAILS] Zone-by-Zone Analysis (Top Issues):",
                    ""
                ])
                
                # Show top 10 zones with issues
                zones_shown = 0
                for zone_name, pattern in zone_patterns[:10]:
                    if pattern['total_runs'] == 0:
                        continue
                        
                    report_lines.append(f"  Zone: {zone_name}")
                    report_lines.append(f"    Total Runs: {pattern['total_runs']}")
                    
                    # Flag distribution
                    report_lines.append(f"    Flag Distribution:")
                    for flag, percentage in pattern['flag_percentages'].items():
                        report_lines.append(f"      {flag.upper():<12}: {percentage:5.1f}%")
                    
                    # Variance analysis
                    variance_pct = pattern['missing_usage_percentage']
                    if variance_pct > 0:
                        report_lines.append(f"    vs Expected:   {variance_pct:5.1f}% UNDER (zone reported lower usage than expected)")
                    elif variance_pct < 0:
                        report_lines.append(f"    vs Expected:   {abs(variance_pct):5.1f}% OVER (zone reported higher usage than expected)")
                    else:
                        report_lines.append(f"    vs Expected:   {variance_pct:5.1f}% (perfect match)")
                    
                    # Recent issues
                    if pattern['recent_issues']:
                        recent_issues_str = ', '.join([f'{issue_date}:{flag}' for issue_date, flag in pattern['recent_issues']])
                        report_lines.append(f"    Recent Issues: {recent_issues_str}")
                    
                    report_lines.append("")
                    zones_shown += 1
                
                if len(zone_patterns) > 10:
                    report_lines.append(f"  ... and {len(zone_patterns) - 10} more zones with normal performance")
                    report_lines.append("")
            
            # Add footer
            report_lines.extend([
                "=" * 80,
                "This report will expand from 2 days to 30 days over time.",
                f"Next report will analyze {self._increment_analysis_window(analysis_days)} days.",
                "=" * 80
            ])
            
            return "\n".join(report_lines)
            
        except Exception as e:
            self.logger.error(f"Error generating report content: {e}")
            return f"Error generating usage analytics report: {e}"
    
    def send_daily_report(self, target_date: date = None, force: bool = False) -> bool:
        """
        Generate and send daily usage analytics report
        
        Args:
            target_date: Target date for analysis (defaults to yesterday)
            force: Force send even if already sent today
            
        Returns:
            True if report was sent successfully, False otherwise
        """
        if target_date is None:
            target_date = get_houston_now().date() - timedelta(days=1)
        
        if not self.config.enabled:
            self.logger.info("Daily usage analytics reports are disabled")
            return False
        
        if not self.email_manager:
            self.logger.warning("Email not configured - cannot send daily report")
            return False
        
        # Check if we've already sent a report today (unless forced)
        if not force and self._already_sent_today():
            self.logger.info("Daily usage analytics report already sent today")
            return False
        
        try:
            # Get current analysis window
            analysis_days = self._get_current_analysis_window()
            
            # Generate report content
            report_content = self.generate_report_content(analysis_days, target_date)
            
            # Create email subject
            subject = f"Daily Hydrawise Usage Analytics - {target_date} ({analysis_days} day analysis)"
            
            # Send email
            success = self.email_manager._send_email(
                subject=subject,
                body=report_content,
                notification_type='daily_usage_analytics',
                affected_zones=[],  # Not applicable for usage analytics
                target_date=target_date
            )
            
            if success:
                self.logger.info(f"Daily usage analytics report sent successfully for {target_date} ({analysis_days} days)")
                self._mark_report_sent_today()
            else:
                self.logger.error(f"Failed to send daily usage analytics report for {target_date}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending daily usage analytics report: {e}")
            return False
    
    def _already_sent_today(self) -> bool:
        """Check if we've already sent a report today"""
        try:
            today = get_houston_now().date()
            result = self.db_manager.adapter.execute_query("""
                SELECT COUNT(*) as count
                FROM email_notifications_log 
                WHERE notification_date = %s
                AND notification_type = 'daily_usage_analytics'
                AND email_sent = true
            """, (today.isoformat(),))
            
            return result[0]['count'] > 0 if result else False
            
        except Exception as e:
            self.logger.warning(f"Error checking if report already sent: {e}")
            return False
    
    def _mark_report_sent_today(self):
        """Mark that we've sent a report today"""
        try:
            today = get_houston_now().date()
            now = get_houston_now()
            
            # Log to email_notifications_log table
            self.db_manager.adapter.execute_insert("""
                INSERT INTO email_notifications_log (
                    notification_date, notification_type, trigger_event, recipients,
                    subject, body_preview, affected_zones, runs_affected_count,
                    email_sent, sent_at, error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                today.isoformat(),
                'daily_usage_analytics',
                f"Daily usage analytics report for {today}",
                json.dumps(self.config.email_recipients),
                f"Daily Hydrawise Usage Analytics - {today}",
                "Daily irrigation usage analytics report with zone performance analysis",
                json.dumps([]),  # No specific zones affected
                0,  # No runs affected
                True,  # Email sent successfully
                now.isoformat(),
                None  # No error
            ))
            
        except Exception as e:
            self.logger.error(f"Error marking report as sent: {e}")

def load_config_from_env() -> DailyReportConfig:
    """Load daily report configuration from environment variables"""
    
    def _load_env_bool(key: str, default: bool = False) -> bool:
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def _load_env_int(key: str, default: int) -> int:
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default
    
    def _load_env_list(key: str, default: list = None) -> list:
        value = os.getenv(key, '')
        if not value.strip():
            return default or []
        return [item.strip() for item in value.split(',') if item.strip()]
    
    return DailyReportConfig(
        enabled=_load_env_bool("DAILY_USAGE_REPORTS_ENABLED", True),
        email_recipients=_load_env_list("EMAIL_RECIPIENTS", []),
        smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        smtp_port=_load_env_int("SMTP_PORT", 587),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from_address=os.getenv("SMTP_FROM_ADDRESS", ""),
        start_days=_load_env_int("DAILY_REPORT_START_DAYS", 2),
        max_days=_load_env_int("DAILY_REPORT_MAX_DAYS", 30),
        days_increment=_load_env_int("DAILY_REPORT_DAYS_INCREMENT", 1),
        report_time_hour=_load_env_int("DAILY_REPORT_TIME_HOUR", 7)
    )

def main():
    """Main function for standalone execution"""
    import argparse
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description="Daily Usage Analytics Reporter")
    parser.add_argument("--target-date", type=str, help="Target date for analysis (YYYY-MM-DD, defaults to yesterday)")
    parser.add_argument("--days", type=int, help="Number of days to analyze (overrides progressive window)")
    parser.add_argument("--force", action="store_true", help="Force send even if already sent today")
    parser.add_argument("--dry-run", action="store_true", help="Generate report but don't send email")
    parser.add_argument("--config-test", action="store_true", help="Test configuration and exit")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config_from_env()
    
    if args.config_test:
        print("Daily Usage Analytics Report Configuration:")
        print(f"  Enabled: {config.enabled}")
        print(f"  Email Recipients: {config.email_recipients}")
        print(f"  SMTP Server: {config.smtp_server}:{config.smtp_port}")
        print(f"  SMTP Username: {config.smtp_username}")
        print(f"  From Address: {config.smtp_from_address}")
        print(f"  Start Days: {config.start_days}")
        print(f"  Max Days: {config.max_days}")
        print(f"  Days Increment: {config.days_increment}")
        print(f"  Report Time Hour: {config.report_time_hour}")
        
        if config.smtp_username and config.smtp_password and config.email_recipients:
            print("  Configuration: COMPLETE")
        else:
            print("  Configuration: INCOMPLETE (missing email settings)")
        
        return 0
    
    # Parse target date
    target_date = None
    if args.target_date:
        try:
            target_date = datetime.strptime(args.target_date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.target_date}'. Use YYYY-MM-DD")
            return 1
    
    # Create reporter
    reporter = DailyUsageAnalyticsReporter(config)
    
    if args.dry_run:
        # Generate report content only
        analysis_days = args.days if args.days else reporter._get_current_analysis_window()
        report_content = reporter.generate_report_content(analysis_days, target_date)
        print(report_content)
        return 0
    
    # Send daily report
    if args.days:
        # Override progressive window with specified days
        original_days = reporter._get_current_analysis_window()
        reporter._store_current_window(args.days)
        success = reporter.send_daily_report(target_date, args.force)
        reporter._store_current_window(original_days)  # Restore original
    else:
        success = reporter.send_daily_report(target_date, args.force)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
