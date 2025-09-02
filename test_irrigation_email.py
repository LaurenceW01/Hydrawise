#!/usr/bin/env python3
"""
Test irrigation email system to verify the threading fix
"""
import os
import sys
from datetime import datetime, date
from dotenv import load_dotenv

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_irrigation_email():
    """Test the irrigation tracking email system"""
    load_dotenv()
    
    print("Testing Irrigation Email System")
    print("=" * 40)
    
    try:
        from irrigation_tracking_system import IrrigationTrackingSystem
        from utils.automated_collector_integration import load_config_from_env
        
        # Load configuration
        config = load_config_from_env()
        print(f"Email enabled: {config.get('email_notifications_enabled', False)}")
        print(f"Recipients: {config.get('notification_recipients', [])}")
        print()
        
        if not config.get('email_notifications_enabled', False):
            print("❌ Email notifications are disabled in configuration")
            return False
        
        # Create a simple test using the email manager directly
        from utils.email_notifications import EmailNotificationManager, EmailConfig
        
        # Create email config
        email_config = EmailConfig(
            enabled=config.get('email_notifications_enabled', False),
            recipients=config.get('notification_recipients', []),
            smtp_server=config.get('smtp_server', 'smtp.gmail.com'),
            smtp_port=config.get('smtp_port', 587),
            username=config.get('smtp_username', ''),
            password=config.get('smtp_password', ''),
            from_address=config.get('smtp_from_address', ''),
            max_emails_per_day=config.get('max_emails_per_day', 1)
        )
        
        # Initialize email manager
        email_manager = EmailNotificationManager(email_config)
        
        print("🔄 Testing comprehensive email sending...")
        
        # Create test email content
        test_email_content = {
            'subject': 'TEST: Hydrawise Email Threading Fix - ' + str(datetime.now()),
            'body': f"""This is a test email to verify that the email threading fix is working.

Test Details:
- Sent at: {datetime.now()}
- Purpose: Verify non-daemon thread email delivery
- System: Irrigation Tracking System

If you received this email, the threading fix is working correctly!

The system will now wait up to 15 seconds for email delivery to complete instead of using daemon threads that get terminated early.
"""
        }
        
        # Send test email using the email manager directly
        import threading
        
        def send_email():
            try:
                success = email_manager._send_email(
                    subject=test_email_content['subject'],
                    body=test_email_content['body'],
                    notification_type='comprehensive_status',
                    target_date=date.today()
                )
                if success:
                    print("✅ Email sent successfully from thread!")
                else:
                    print("❌ Email sending failed from thread")
            except Exception as e:
                print(f"❌ Error in email thread: {e}")
        
        # Test the fixed threading approach (non-daemon with timeout)
        print("🔄 Starting email thread (non-daemon with timeout)...")
        email_thread = threading.Thread(target=send_email, daemon=False)
        email_thread.start()
        
        # Wait up to 15 seconds for email to send (ensures completion)
        email_thread.join(timeout=15)
        if email_thread.is_alive():
            print("⚠️ Email thread still running after 15 seconds")
        else:
            print("✅ Email thread completed within timeout")
        
        print("✅ Email sending process completed!")
        print("📧 Check your email inbox for the test message")
        print("   (If you don't receive it, there may be other delivery issues)")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Failed to test irrigation email: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_irrigation_email()
