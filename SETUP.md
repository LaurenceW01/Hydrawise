# Hydrawise Irrigation Data Collector - Setup Guide

This guide covers the complete setup process for the Hydrawise Irrigation Data Collector with PostgreSQL database support.

## 🎯 Overview

The Hydrawise Irrigation Data Collector is a Python application that:
- Automatically scrapes irrigation schedules and actual runs from Hydrawise portal
- Stores data in PostgreSQL (or SQLite for development)
- Runs as a Windows service using NSSM
- Provides irrigation tracking, status change detection, and email notifications
- Uses rotating logs to prevent disk space issues

## 📋 Prerequisites

### Required Software
- **Python 3.8+** (tested with Python 3.11)
- **Git** (for cloning and version control)
- **Google Chrome browser** (latest version recommended)
- **PostgreSQL database** (local or cloud-hosted like render.com)
- **NSSM** (Non-Sucking Service Manager) for Windows service deployment

### System Requirements
- **Windows 10/11** (for NSSM service deployment)
- **4GB+ RAM** (Chrome browser can be memory intensive)
- **1GB+ disk space** (for logs, database, and dependencies)

## 🚀 Installation Steps

### 1. Clone Repository
```bash
git clone <repository-url>
cd Hydrawise
```

### 2. Create Python Virtual Environment
```bash
python -m venv hydrawise-venv
```

**Activate virtual environment:**
- **Windows (Git Bash):** `source hydrawise-venv/Scripts/activate`
- **Windows (CMD):** `hydrawise-venv\Scripts\activate.bat`
- **Windows (PowerShell):** `hydrawise-venv\Scripts\Activate.ps1`

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Database Setup

#### Option A: PostgreSQL (Recommended)
1. **Create PostgreSQL database** (local or cloud service like render.com)
2. **Initialize schema:**
   ```bash
   psql -h your_host -U your_user -d your_database -f database/postgresql_schema.sql
   ```

#### Option B: SQLite (Development only)
- No setup required - database file will be created automatically

### 5. Configuration

#### Create Environment File
```bash
cp env_local_example.txt .env
```

#### Edit `.env` file with your settings:

**Required Settings:**
```env
# Hydrawise Login
HYDRAWISE_USERNAME=your_hydrawise_email
HYDRAWISE_PASSWORD=your_hydrawise_password

# Database (PostgreSQL)
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://user:password@host:port/database
# OR individual parameters:
DB_HOST=your_db_host
DB_PORT=5432
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# Logging
USE_ROTATING_LOGS=true
LOG_ROTATION_TYPE=size
MAX_LOG_SIZE_MB=10
LOG_BACKUP_COUNT=20
LOG_LEVEL=INFO
LOG_DIRECTORY=logs
```

**Optional Settings:**
```env
# Collection Schedule (Houston time)
DAILY_COLLECTION_TIME=06:00
ACTIVE_START_TIME=06:00
ACTIVE_END_TIME=20:00
HOURLY_INTERVAL_MINUTES=60

# Browser Settings
HEADLESS_MODE=true

# Email Notifications
EMAIL_NOTIFICATIONS_ENABLED=false
EMAIL_RECIPIENTS=your_email@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_app_password
```

### 6. Test Installation
```bash
# Activate virtual environment
source hydrawise-venv/Scripts/activate

# Test database connection
python -c "from database.universal_database_manager import get_universal_database_manager; print('Database connection:', get_universal_database_manager().get_connection_info())"

# Test single collection run
python automated_collector.py --run-once
```

## 🔧 Windows Service Setup (NSSM)

### Install NSSM
```bash
# Using Chocolatey
choco install nssm

# Or download from: https://nssm.cc/download
```

### Configure Service
1. **Create batch file for service:**
   ```batch
   @echo off
   cd /d "C:\path\to\your\Hydrawise"
   call hydrawise-venv\Scripts\activate.bat
   python automated_collector.py
   ```

2. **Install service (run as Administrator):**
   ```bash
   nssm install HydrawiseCollector "C:\path\to\your\Hydrawise\hydrawise-venv\Scripts\python.exe"
   nssm set HydrawiseCollector AppParameters "automated_collector.py"
   nssm set HydrawiseCollector AppDirectory "C:\path\to\your\Hydrawise"
   nssm set HydrawiseCollector Description "Hydrawise Irrigation Data Collection Service"
   nssm set HydrawiseCollector Start SERVICE_AUTO_START
   nssm set HydrawiseCollector AppExit Default Restart
   nssm set HydrawiseCollector AppRestartDelay 30000
   nssm set HydrawiseCollector ObjectName LocalSystem
   ```

3. **Set environment variables:**
   ```bash
   # Use the provided script
   ./fix_nssm_single_env.sh
   ```

4. **Configure logging:**
   ```bash
   mkdir -p logs
   nssm set HydrawiseCollector AppStdout "C:\path\to\your\Hydrawise\logs\nssm_stdout.log"
   nssm set HydrawiseCollector AppStderr "C:\path\to\your\Hydrawise\logs\nssm_stderr.log"
   ```

5. **Start service:**
   ```bash
   nssm start HydrawiseCollector
   ```

## 📁 File Structure

```
Hydrawise/
├── automated_collector.py          # Main application entry point
├── requirements.txt                # Python dependencies
├── .env                           # Environment configuration (create from example)
├── env_local_example.txt          # Environment configuration template
├── SETUP.md                       # This setup guide
├── database/
│   ├── postgresql_schema.sql      # Database schema for PostgreSQL
│   ├── universal_database_manager.py  # Database abstraction layer
│   └── ...                       # Other database modules
├── utils/
│   ├── universal_logging.py       # Logging configuration
│   └── ...                       # Utility modules
├── logs/                          # Log files (created automatically)
└── hydrawise-venv/                # Python virtual environment
```

## 🔍 Monitoring and Troubleshooting

### Check Service Status
```bash
nssm status HydrawiseCollector
```

### View Logs
```bash
# Service logs
tail -f logs/nssm_stdout.log
tail -f logs/nssm_stderr.log

# Application logs
tail -f logs/automated_collector_main.log
```

### Common Issues

1. **ChromeDriver version mismatch:**
   ```bash
   python fix_chromedriver_service.py
   nssm restart HydrawiseCollector
   ```

2. **Database connection errors:**
   - Verify DATABASE_URL or individual DB_* parameters
   - Check network connectivity to database
   - Ensure database schema is initialized

3. **Service won't start:**
   - Check NSSM configuration: `nssm dump HydrawiseCollector`
   - Verify file paths are correct
   - Ensure virtual environment is properly configured

4. **Permission issues:**
   - Run NSSM commands as Administrator
   - Ensure service account has proper permissions

### Manual Testing
```bash
# Test database connection
python -c "from database.universal_database_manager import get_universal_database_manager; db = get_universal_database_manager(); print('Connected:', db.test_connection())"

# Test single collection
python automated_collector.py --run-once --verbose

# Test specific components
python admin_schedule_collection.py collect today
python admin_reported_runs.py collect yesterday
```

## 🎯 Production Deployment

### Recommended Settings for Production:
```env
# Performance
HEADLESS_MODE=true
LOG_LEVEL=INFO

# Reliability
USE_ROTATING_LOGS=true
MAX_LOG_SIZE_MB=10
LOG_BACKUP_COUNT=20

# Security
# Use strong database passwords
# Limit email recipients
# Use app passwords for SMTP
```

### Monitoring:
- Monitor log file sizes
- Check service status regularly
- Verify data collection is working
- Monitor database storage usage

## 📞 Support

For issues or questions:
1. Check the logs first
2. Verify configuration settings
3. Test components individually
4. Check database connectivity
5. Ensure Chrome/ChromeDriver compatibility

## 🔄 Updates and Maintenance

### Update Dependencies:
```bash
source hydrawise-venv/Scripts/activate
pip install --upgrade -r requirements.txt
```

### Update ChromeDriver:
```bash
python fix_chromedriver_service.py
```

### Service Maintenance:
```bash
# Restart service
nssm restart HydrawiseCollector

# Update service configuration
nssm edit HydrawiseCollector

# Remove service (if needed)
nssm remove HydrawiseCollector confirm
```
