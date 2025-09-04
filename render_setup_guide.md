# Hydrawise Automated Collection - Render.com Deployment Guide

This guide walks you through deploying the Hydrawise automated collection system to render.com with PostgreSQL database support.

## 📋 Prerequisites

1. **Render.com Account**: Sign up at [render.com](https://render.com)
2. **GitHub Repository**: Your Hydrawise code should be in a GitHub repository
3. **Hydrawise Credentials**: Your Hydrawise username and password

## 🚀 Deployment Steps

### Step 1: Create PostgreSQL Database

1. Log into your render.com dashboard
2. Click **"New"** → **"PostgreSQL"**
3. Configure the database:
   - **Name**: `hydrawise-database`
   - **Database Name**: `hydrawise`
   - **User**: `hydrawise` 
   - **Region**: Choose closest to your location
   - **Plan**: Start with **Starter** (can upgrade later)
4. Click **"Create Database"**
5. **Important**: Note the database connection details (render.com will provide `DATABASE_URL`)

### Step 2: Create Web Service

1. In render.com dashboard, click **"New"** → **"Web Service"**
2. Connect your GitHub repository containing the Hydrawise code
3. Configure the service:
   - **Name**: `hydrawise-collector`
   - **Environment**: `Python 3`
   - **Region**: Same as your database
   - **Branch**: `main` (or your preferred branch)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python render_deployment.py`
   - **Plan**: Start with **Starter**

### Step 3: Configure Environment Variables

In the web service settings, add these environment variables:

#### Required Variables
```bash
# Database Configuration (automatically provided by render.com)
DATABASE_TYPE=postgresql

# Hydrawise Credentials (REQUIRED - set these securely)
HYDRAWISE_USERNAME=your_hydrawise_username
HYDRAWISE_PASSWORD=your_hydrawise_password

# Logging Configuration
LOGGING_MODE=stdout
LOG_LEVEL=INFO
ENABLE_FILE_LOGGING=false
ENABLE_CONSOLE_LOGGING=true

# Browser Configuration
HEADLESS_MODE=true

# Timezone (Houston, TX)
TZ=America/Chicago
```

#### Optional Configuration Variables
```bash
# Collection Schedule (Houston time - 24-hour format)
DAILY_COLLECTION_TIME=06:00
HOURLY_INTERVAL_MINUTES=60
ACTIVE_START_TIME=06:00
ACTIVE_END_TIME=20:00

# Collection Options
COLLECTION_ENABLED=true
COLLECT_SCHEDULES=true
COLLECT_REPORTED_RUNS=true
COLLECT_YESTERDAY_ON_STARTUP=true
SMART_STARTUP_CHECK=true

# Email Notifications (optional)
EMAIL_NOTIFICATIONS_ENABLED=false
EMAIL_RECIPIENTS=your_email@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
SMTP_FROM_ADDRESS=your_email@example.com

# Tracking System (optional)
TRACK_SENSOR_STATUS=true
TRACK_STATUS_CHANGES=true
SENSOR_CHANGE_NOTIFICATIONS=true
STATUS_CHANGE_NOTIFICATIONS=true
DAILY_SUMMARY_NOTIFICATIONS=true
```

### Step 4: Connect Database to Web Service

**Method 1: Automatic Connection (Recommended)**
1. In your web service settings, scroll down to **"Environment Variables"** section
2. Look for **"Add from Database"** or **"Connect Database"** button
3. Select your `hydrawise-database` PostgreSQL service
4. This will automatically add the `DATABASE_URL` environment variable

**Method 2: Manual Connection (if automatic method not available)**
1. Go to your PostgreSQL database service (`hydrawise-database`)
2. In the database dashboard, find the **"Connections"** or **"Info"** tab
3. Copy the **"External Database URL"** (it looks like: `postgresql://username:password@hostname:port/database_name`)
4. Go back to your web service settings
5. In **"Environment Variables"**, manually add:
   - Key: `DATABASE_URL`
   - Value: [paste the database URL you copied]
   - Mark as **"Secret"** for security

**Method 3: Using Internal Database URL (for render.com services)**
1. Go to your PostgreSQL database service
2. Copy the **"Internal Database URL"** (faster connection within render.com)
3. Add it as `DATABASE_URL` in your web service environment variables

### Step 5: Deploy

1. Click **"Create Web Service"**
2. Render.com will automatically build and deploy your service
3. Monitor the deployment logs for any errors
4. Once deployed, the service will be available at your render.com URL

## 🔍 Monitoring and Verification

### Health Check
Your service includes a built-in health check endpoint at `/` that returns:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-27T12:00:00",
  "collector_running": true,
  "database_type": "postgresql"
}
```

### Logs
View real-time logs in the render.com dashboard:
1. Go to your web service
2. Click on **"Logs"** tab
3. Monitor for successful collections and any errors

### Database Access
To access your PostgreSQL database:
1. Go to your database service in render.com
2. Use the provided connection details
3. Connect using tools like pgAdmin, DBeaver, or psql

## 🛠️ Troubleshooting

### Common Issues

#### 1. Database Connection Errors
```bash
# Check these environment variables are set:
DATABASE_URL=postgresql://username:password@hostname:port/database_name
DATABASE_TYPE=postgresql
```

**If you can't find the database linking option:**
- The render.com interface changes periodically
- Try Method 2 (Manual Connection) above
- Look for "Add Environment Variable" instead of "Link Database"
- The database URL is always available in your PostgreSQL service dashboard

**Finding your Database URL:**
1. Go to your render.com dashboard
2. Click on your PostgreSQL database service (`hydrawise-database`)
3. Look for one of these sections:
   - **"Connections"** tab
   - **"Info"** tab  
   - **"Connect"** section
4. Copy either the "Internal Database URL" or "External Database URL"
5. Internal URL is faster (recommended for render.com services)

**Database URL Format:**
```
postgresql://username:password@hostname:port/database_name
```
Example:
```
postgresql://hydrawise_user:abc123xyz@dpg-abc123-a.oregon-postgres.render.com:5432/hydrawise_db
```

#### 2. Missing Hydrawise Credentials
```bash
# Ensure these are set securely:
HYDRAWISE_USERNAME=your_username
HYDRAWISE_PASSWORD=your_password
```

#### 3. Browser/Selenium Issues
```bash
# Ensure headless mode is enabled:
HEADLESS_MODE=true
```

#### 4. Timezone Issues
```bash
# Set correct timezone for Houston:
TZ=America/Chicago
```

### Viewing Logs
```bash
# In render.com dashboard, check logs for:
# - "Database connection successful"
# - "Automated collector started successfully"
# - "Collection completed successfully"
```

### Database Schema Initialization
The system automatically creates the database schema on first run. Look for:
```
Database schema initialized successfully
Initialized X zones in database
```

## 📊 Monitoring Collections

### Successful Collection Logs
```
[DAILY] Running scheduled daily collection at 06:00 Houston time
Collection completed: 15 scheduled runs, 12 actual runs collected
[INTERVAL] Hourly collection completed successfully
```

### Error Patterns to Watch
```
Database configuration validation failed
Failed to initialize database
Collection failed: [error details]
```

## 🔧 Scaling and Optimization

### Upgrading Plans
- **Starter Plan**: Good for initial testing
- **Standard Plan**: Recommended for production use
- **Pro Plan**: For high-volume or critical deployments

### Database Scaling
- Monitor database usage in render.com dashboard
- Upgrade database plan if needed
- Consider connection pooling for high-volume scenarios

### Performance Monitoring
- Monitor collection duration in logs
- Watch for memory usage patterns
- Scale service plan if needed

## 🔐 Security Best Practices

1. **Use Environment Variables**: Never hardcode credentials
2. **Secure Secrets**: Use render.com's secret management
3. **Database Access**: Restrict database access to your services only
4. **Regular Updates**: Keep dependencies updated
5. **Monitor Logs**: Watch for suspicious activity

## 📞 Support

If you encounter issues:
1. Check the logs in render.com dashboard
2. Verify all environment variables are set correctly
3. Ensure database service is running
4. Check GitHub repository for updates

## 🔄 Local Development vs Production

| Feature | Local Development | Render.com Production |
|---------|------------------|----------------------|
| Database | SQLite file | PostgreSQL service |
| Logging | File + Console | Stdout only |
| Browser | Can be non-headless | Always headless |
| Storage | Local files | Memory only |
| Monitoring | Manual | Health checks + logs |

Remember to test locally before deploying to production!
