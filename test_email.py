#!/usr/bin/env python3
"""
Simple email test script to verify email configuration
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

def test_email():
    """Test email sending with current configuration"""
    # Load environment variables
    load_dotenv()
    
    # Get email configuration
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_address = os.getenv("SMTP_FROM_ADDRESS", "")
    recipients = os.getenv("EMAIL_RECIPIENTS", "").split(",")
    
    print("Email Configuration Test")
    print("=" * 40)
    print(f"SMTP Server: {smtp_server}:{smtp_port}")
    print(f"Username: {username}")
    print(f"From Address: {from_address}")
    print(f"Recipients: {recipients}")
    print(f"Password: {'*' * len(password) if password else 'NOT SET'}")
    print()
    
    if not username or not password:
        print("❌ ERROR: SMTP credentials not configured")
        return False
    
    if not recipients or not recipients[0]:
        print("❌ ERROR: No email recipients configured")
        return False
    
    try:
        # Create test message
        msg = MIMEMultipart()
        msg['From'] = from_address
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = "Hydrawise Email Test - " + str(__import__('datetime').datetime.now())
        
        body = """This is a test email from your Hydrawise irrigation monitoring system.

If you received this email, your email configuration is working correctly!

Test Details:
- Sent from: Hydrawise Email Test Script
- Configuration: Gmail SMTP
- Time: """ + str(__import__('datetime').datetime.now())
        
        msg.attach(MIMEText(body, 'plain'))
        
        print("🔄 Connecting to SMTP server...")
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            print("🔄 Starting TLS...")
            server.starttls()
            
            print("🔄 Logging in...")
            server.login(username, password)
            
            print("🔄 Sending email...")
            server.send_message(msg)
        
        print("✅ SUCCESS: Test email sent successfully!")
        print(f"📧 Check {recipients[0]} for the test email")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Failed to send test email: {e}")
        return False

if __name__ == "__main__":
    test_email()
