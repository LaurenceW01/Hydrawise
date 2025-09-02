# Hydrawise Irrigation Tracking Configuration Guide

## Overview

The Hydrawise irrigation tracking system monitors rain sensor status and scheduled run changes, providing email notifications when critical irrigation events occur. All configuration is managed through environment variables.

## Quick Setup

### 1. Create Configuration File

Run the interactive setup script:
```bash
python setup_tracking_config.py
```

This will create a `.env` file with your tracking preferences.

### 2. Manual Configuration

Alternatively, copy the example file and customize:
```bash
cp env.example .env
# Edit .env with your settings
```

## Configuration Options

### Core Tracking Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `TRACK_SENSOR_STATUS` | `true` | Monitor rain sensor "stopping irrigation" status |
| `TRACK_STATUS_CHANGES` | `true` | Detect popup status changes (rainfall abort, sensor abort, etc.) |

### Email Notifications

| Variable | Default | Description |
|----------|---------|-------------|
| `EMAIL_NOTIFICATIONS_ENABLED` | `false` | Enable email notifications |
| `EMAIL_RECIPIENTS` | _(none)_ | Comma-separated list of email addresses |
| `SMTP_SERVER` | `smtp.gmail.com` | SMTP server for sending emails |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` | _(none)_ | Gmail username |
| `SMTP_PASSWORD` | _(none)_ | Gmail app password (NOT regular password) |
| `SMTP_FROM_ADDRESS` | _(same as username)_ | From address for emails |

### Email Timing

| Variable | Default | Description |
|----------|---------|-------------|
| `DAILY_EMAIL_TIME` | `19:00` | Time to send daily summary (Houston time) |
| `MAX_EMAILS_PER_DAY` | `1` | Maximum emails per day (prevents spam) |

### Advanced Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `database/irrigation_data.db` | Database file path |
| `HEADLESS_MODE` | `true` | Run browser in headless mode |
| `SENSOR_CHANGE_NOTIFICATIONS` | `true` | Include sensor changes in emails |
| `STATUS_CHANGE_NOTIFICATIONS` | `true` | Include status changes in emails |
| `DAILY_SUMMARY_NOTIFICATIONS` | `true` | Enable daily summary emails |

## Email Setup (Gmail)

### 1. Enable 2-Factor Authentication
- Go to your Google Account settings
- Enable 2-Factor Authentication if not already enabled

### 2. Generate App Password
- Go to **Security** → **2-Step Verification** → **App passwords**
- Select **Mail** and generate a password
- Use this 16-character password in `SMTP_PASSWORD`

### 3. Configure Email Settings
```bash
EMAIL_NOTIFICATIONS_ENABLED=true
EMAIL_RECIPIENTS=admin@yourdomain.com,manager@yourdomain.com
SMTP_USERNAME=alerts@yourdomain.com
SMTP_PASSWORD=abcd efgh ijkl mnop  # 16-character app password
```

## Configuration Examples

### Basic Tracking (No Emails)
```bash
TRACK_SENSOR_STATUS=true
TRACK_STATUS_CHANGES=true
EMAIL_NOTIFICATIONS_ENABLED=false
```

### Full Tracking with Email Alerts
```bash
TRACK_SENSOR_STATUS=true
TRACK_STATUS_CHANGES=true
EMAIL_NOTIFICATIONS_ENABLED=true
EMAIL_RECIPIENTS=admin@example.com,backup@example.com
SMTP_USERNAME=irrigation.alerts@gmail.com
SMTP_PASSWORD=your_app_password_here
```

### Testing Mode
```bash
TRACK_SENSOR_STATUS=false
TRACK_STATUS_CHANGES=true
EMAIL_NOTIFICATIONS_ENABLED=false
```

## Email Notification Examples

### Daily Summary Email
```
Subject: Hydrawise Alert - 3 zones affected by irrigation changes

STATUS CHANGES DETECTED:

🌧️ HIGH RAINFALL ABORTS (2 zones):
- Front Planters: 6:00 AM (15.5 gallons prevented)
- Rear Beds: 6:15 AM (12.3 gallons prevented)

🔧 SENSOR INPUT ABORTS (1 zone):
- Side Garden: 7:00 AM (8.7 gallons prevented)

SUMMARY:
- Total zones affected: 3
- Total water prevented: 36.5 gallons
- Detection date: August 26, 2025
- Report generated: August 26, 2025 7:00 PM Houston time
```

## Troubleshooting

### Check Current Configuration
```bash
python setup_tracking_config.py status
```

### Test Email Configuration
```bash
python -c "
import os
os.environ['EMAIL_NOTIFICATIONS_ENABLED'] = 'true'
os.environ['EMAIL_RECIPIENTS'] = 'test@example.com'
os.environ['SMTP_USERNAME'] = 'your.email@gmail.com'
os.environ['SMTP_PASSWORD'] = 'your_app_password'

from utils.automated_collector_integration import load_config_from_env
config = load_config_from_env()
print('Email config loaded successfully')
"
```

### Common Issues

**Email notifications not working:**
- Check Gmail app password (not regular password)
- Verify 2-factor authentication is enabled
- Ensure `EMAIL_RECIPIENTS` contains valid addresses
- Check logs for SMTP errors

**Tracking not detecting changes:**
- Verify `TRACK_STATUS_CHANGES=true` in `.env`
- Check that scheduled runs are being collected successfully
- Review logs for tracking analysis messages

**Database errors:**
- Ensure `database/` directory exists and is writable
- Check `DB_PATH` points to correct location
- Verify database migrations completed successfully

## Integration with Automated Collector

The tracking system automatically integrates with the existing automated collector:

1. **Startup Collection** - Tracks status changes for yesterday and today
2. **Daily Collection** - Monitors scheduled run status changes
3. **Interval Collection** - Detects real-time status updates

No additional configuration needed - tracking runs automatically when enabled.

## Security Notes

- **Never commit `.env` file** to version control
- Use Gmail app passwords, not regular passwords  
- Limit email recipients to necessary personnel
- Consider using dedicated email account for alerts
- Review email logs periodically for delivery issues

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review configuration with `setup_tracking_config.py status`
3. Test individual components before reporting bugs
4. Include relevant log excerpts when seeking help


