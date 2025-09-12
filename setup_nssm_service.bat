@echo off
REM ====================================================================
REM Hydrawise NSSM Service Setup Script
REM ====================================================================
REM This script configures the Hydrawise Collector as a Windows service
REM using NSSM (Non-Sucking Service Manager)
REM
REM Prerequisites:
REM - NSSM must be installed (via chocolatey: choco install nssm)
REM - Python virtual environment must exist at specified path
REM - Run this script as Administrator
REM ====================================================================

echo Setting up Hydrawise Collector NSSM Service...
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Define paths and service name
set SERVICE_NAME=HydrawiseCollector
set NSSM_PATH=C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe
set PYTHON_PATH=C:\Users\laure\Dev\Hydrawise\hydrawise-venv\Scripts\python.exe
set APP_DIR=C:\Users\laure\Dev\Hydrawise
set LOG_DIR=%APP_DIR%\logs

REM Check if NSSM exists
if not exist "%NSSM_PATH%" (
    echo ERROR: NSSM not found at %NSSM_PATH%
    echo Please install NSSM first: choco install nssm
    pause
    exit /b 1
)

REM Check if Python virtual environment exists
if not exist "%PYTHON_PATH%" (
    echo ERROR: Python virtual environment not found at %PYTHON_PATH%
    echo Please verify the virtual environment path
    pause
    exit /b 1
)

REM Check if application directory exists
if not exist "%APP_DIR%" (
    echo ERROR: Application directory not found at %APP_DIR%
    echo Please verify the application path
    pause
    exit /b 1
)

REM Create logs directory if it doesn't exist
if not exist "%LOG_DIR%" (
    echo Creating logs directory...
    mkdir "%LOG_DIR%"
)

REM Stop and remove existing service if it exists
echo Checking for existing service...
"%NSSM_PATH%" status %SERVICE_NAME% >nul 2>&1
if %errorLevel% equ 0 (
    echo Stopping existing service...
    "%NSSM_PATH%" stop %SERVICE_NAME%
    echo Removing existing service...
    "%NSSM_PATH%" remove %SERVICE_NAME% confirm
    timeout /t 3 /nobreak >nul
)

echo.
echo Installing new service...

REM Install the service
"%NSSM_PATH%" install %SERVICE_NAME% "%PYTHON_PATH%"

REM Configure service parameters
echo Configuring service parameters...
"%NSSM_PATH%" set %SERVICE_NAME% AppParameters "automated_collector.py"
"%NSSM_PATH%" set %SERVICE_NAME% AppDirectory "%APP_DIR%"
"%NSSM_PATH%" set %SERVICE_NAME% AppExit Default Restart

REM Set environment variables
echo Configuring environment variables...
"%NSSM_PATH%" set %SERVICE_NAME% AppEnvironmentExtra ":HUNTER_HYDRAWISE_API_KEY=6820-4445-8013-194e HYDRAWISE_USER=laurence.wright01@gmail.com HYDRAWISE_PASSWORD=EALDl1v1ng GCS_BUCKET_NAME=hydrawise-database GOOGLE_CLOUD_PROJECT=GardenLLM DB_SYNC_ENABLED=true DB_SYNC_DAILY=true DB_BACKUP_RETENTION_DAYS=90 TRACK_SENSOR_STATUS=true TRACK_STATUS_CHANGES=true EMAIL_NOTIFICATIONS_ENABLED=true EMAIL_RECIPIENTS=laurence.wright01@gmail.com SMTP_SERVER=smtp.gmail.com SMTP_PORT=587 SMTP_USERNAME=laurence.wright01@gmail.com SMTP_PASSWORD=cutz iaso hoqy hznx SMTP_FROM_ADDRESS=laurence.wright01@gmail.com USE_ROTATING_LOGS=true LOG_ROTATION_TYPE=size MAX_LOG_SIZE_MB=10 LOG_BACKUP_COUNT=20 LOG_LEVEL=INFO LOG_DIRECTORY=logs DAILY_EMAIL_TIME=19:00 MAX_EMAILS_PER_DAY=1 DB_PATH=database/irrigation_data.db HEADLESS_MODE=true SENSOR_CHANGE_NOTIFICATIONS=true STATUS_CHANGE_NOTIFICATIONS=true DAILY_SUMMARY_NOTIFICATIONS=true DB_PORT=5432 DB_DATABASE=hydrawise DB_USERNAME=hydrawise DB_PASSWORD=mZ7HctrqAwJrAeSKG7sQaAp6WfoaL0AG DB_INTERNAL_DATABASE_URL=postgresql://hydrawise:mZ7HctrqAwJrAeSKG7sQaAp6WfoaL0AG@dpg-d2su1j15pdvs7390mq70-a/hydrawise DB_EXTERNAL_DATABASE_URL=postgresql://hydrawise:mZ7HctrqAwJrAeSKG7sQaAp6WfoaL0AG@dpg-d2su1j15pdvs7390mq70-a.oregon-postgres.render.com/hydrawise DB_PSL_COMMAND=PGPASSWORD=mZ7HctrqAwJrAeSKG7sQaAp6WfoaL0AG psql -h dpg-d2su1j15pdvs7390mq70-a.oregon-postgres.render.com -U hydrawise hydrawise DATABASE_TYPE=postgresql DATABASE_URL=postgresql://hydrawise:mZ7HctrqAwJrAeSKG7sQaAp6WfoaL0AG@dpg-d2su1j15pdvs7390mq70-a.oregon-postgres.render.com/hydrawise DB_USER=hydrawise DB_NAME=hydrawise DB_HOST=dpg-d2su1j15pdvs7390mq70-a LOGGING_MODE=stdout ENABLE_FILE_LOGGING=false"

REM Configure service behavior
echo Configuring service behavior...
"%NSSM_PATH%" set %SERVICE_NAME% AppRestartDelay 30000

REM Configure logging with truncation
echo Configuring logging...
"%NSSM_PATH%" set %SERVICE_NAME% AppStdout "%LOG_DIR%\nssm_stdout.log"
"%NSSM_PATH%" set %SERVICE_NAME% AppStdoutCreationDisposition 2
"%NSSM_PATH%" set %SERVICE_NAME% AppStderr "%LOG_DIR%\nssm_stderr.log"
"%NSSM_PATH%" set %SERVICE_NAME% AppStderrCreationDisposition 2

REM Configure service metadata
echo Configuring service metadata...
"%NSSM_PATH%" set %SERVICE_NAME% Description "Hydrawise Irrigation Data Collection Service - Collects schedules and reported runs hourly from 6 AM to 8 PM"
"%NSSM_PATH%" set %SERVICE_NAME% DisplayName "Hydrawise Collector"
"%NSSM_PATH%" set %SERVICE_NAME% ObjectName LocalSystem
"%NSSM_PATH%" set %SERVICE_NAME% Start SERVICE_AUTO_START
"%NSSM_PATH%" set %SERVICE_NAME% Type SERVICE_WIN32_OWN_PROCESS

echo.
echo Service installation completed successfully!
echo.
echo Service Details:
echo   Name: %SERVICE_NAME%
echo   Display Name: Hydrawise Collector
echo   Python: %PYTHON_PATH%
echo   App Directory: %APP_DIR%
echo   Logs Directory: %LOG_DIR%
echo.
echo To start the service: nssm start %SERVICE_NAME%
echo To stop the service:  nssm stop %SERVICE_NAME%
echo To check status:      nssm status %SERVICE_NAME%
echo To view logs:         type "%LOG_DIR%\nssm_stdout.log"
echo.

REM Ask if user wants to start the service now
set /p START_NOW=Start the service now? (y/n): 
if /i "%START_NOW%"=="y" (
    echo Starting service...
    "%NSSM_PATH%" start %SERVICE_NAME%
    echo Service started!
) else (
    echo Service installed but not started.
    echo Use 'nssm start %SERVICE_NAME%' to start it manually.
)

echo.
echo Setup complete!
pause
