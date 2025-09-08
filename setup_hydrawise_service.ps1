# Hydrawise Collector NSSM Service Setup Script
# Run this script as Administrator in PowerShell

Write-Host "=== Hydrawise Collector Service Setup ===" -ForegroundColor Green
Write-Host ""

# Configuration variables
$ServiceName = "HydrawiseCollector"
$WorkingDir = "C:\Users\laure\Dev\Hydrawise"
$PythonExe = "$WorkingDir\hydrawise-venv\Scripts\python.exe"
$ScriptPath = "$WorkingDir\automated_collector.py"
$LogsDir = "$WorkingDir\logs"

# Ensure logs directory exists
Write-Host "Creating logs directory..." -ForegroundColor Yellow
if (!(Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force
    Write-Host "Created logs directory: $LogsDir" -ForegroundColor Green
} else {
    Write-Host "Logs directory already exists: $LogsDir" -ForegroundColor Green
}

# Stop and remove existing service if it exists
Write-Host ""
Write-Host "Checking for existing service..." -ForegroundColor Yellow
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Stopping existing service..." -ForegroundColor Yellow
    nssm stop $ServiceName
    Start-Sleep -Seconds 3
    
    Write-Host "Removing existing service..." -ForegroundColor Yellow
    nssm remove $ServiceName confirm
    Start-Sleep -Seconds 2
    Write-Host "Existing service removed." -ForegroundColor Green
} else {
    Write-Host "No existing service found." -ForegroundColor Green
}

# Verify paths exist
Write-Host ""
Write-Host "Verifying paths..." -ForegroundColor Yellow
if (!(Test-Path $PythonExe)) {
    Write-Host "ERROR: Python executable not found at: $PythonExe" -ForegroundColor Red
    exit 1
}
if (!(Test-Path $ScriptPath)) {
    Write-Host "ERROR: Script not found at: $ScriptPath" -ForegroundColor Red
    exit 1
}
if (!(Test-Path $WorkingDir)) {
    Write-Host "ERROR: Working directory not found at: $WorkingDir" -ForegroundColor Red
    exit 1
}
Write-Host "All paths verified successfully." -ForegroundColor Green

# Install the service
Write-Host ""
Write-Host "Installing new service..." -ForegroundColor Yellow
nssm install $ServiceName $PythonExe $ScriptPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install service" -ForegroundColor Red
    exit 1
}

# Configure service parameters
Write-Host "Configuring service parameters..." -ForegroundColor Yellow

# Set working directory
nssm set $ServiceName AppDirectory $WorkingDir

# Set service description
nssm set $ServiceName Description "Hydrawise Irrigation Data Collection Service - Collects schedules and reported runs hourly from 6 AM to 8 PM"

# Set display name
nssm set $ServiceName DisplayName "Hydrawise Collector"

# Set startup type to automatic
nssm set $ServiceName Start SERVICE_AUTO_START

# Configure logging
nssm set $ServiceName AppStdout "$LogsDir\nssm_stdout.log"
nssm set $ServiceName AppStderr "$LogsDir\nssm_stderr.log"

# Set restart behavior
nssm set $ServiceName AppExit Default Restart
nssm set $ServiceName AppRestartDelay 30000

# Set service to run as Network Service (has better permissions than LocalSystem)
nssm set $ServiceName ObjectName "NT AUTHORITY\NetworkService"

# Set process priority to normal
nssm set $ServiceName AppPriority NORMAL_PRIORITY_CLASS

# Configure environment variables for the service
Write-Host "Setting environment variables..." -ForegroundColor Yellow

# Check if .env file exists
$envFile = "$WorkingDir\.env"
if (Test-Path $envFile) {
    Write-Host "Found .env file, reading configuration..." -ForegroundColor Green
    
    # Read .env file and set environment variables for the service
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            
            # Remove quotes if present
            $value = $value -replace '^"(.*)"$', '$1'
            $value = $value -replace "^'(.*)'$", '$1'
            
            # Set environment variable for the service
            nssm set $ServiceName AppEnvironmentExtra "$key=$value"
            Write-Host "  Set $key" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "WARNING: .env file not found at $envFile" -ForegroundColor Red
    Write-Host "Service may not work correctly without environment variables." -ForegroundColor Red
}

# Verify service installation
Write-Host ""
Write-Host "Verifying service installation..." -ForegroundColor Yellow
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    Write-Host "Service installed successfully!" -ForegroundColor Green
    Write-Host "Service Status: $($service.Status)" -ForegroundColor Green
} else {
    Write-Host "ERROR: Service installation failed" -ForegroundColor Red
    exit 1
}

# Display configuration
Write-Host ""
Write-Host "=== Service Configuration ===" -ForegroundColor Cyan
Write-Host "Service Name: $ServiceName"
Write-Host "Python Path: $PythonExe"
Write-Host "Script Path: $ScriptPath"
Write-Host "Working Directory: $WorkingDir"
Write-Host "Stdout Log: $LogsDir\nssm_stdout.log"
Write-Host "Stderr Log: $LogsDir\nssm_stderr.log"
Write-Host "Service Account: NT AUTHORITY\NetworkService"

# Ask if user wants to start the service
Write-Host ""
$startService = Read-Host "Do you want to start the service now? (Y/N)"
if ($startService -eq "Y" -or $startService -eq "y") {
    Write-Host "Starting service..." -ForegroundColor Yellow
    nssm start $ServiceName
    
    Start-Sleep -Seconds 3
    
    # Check service status
    $service = Get-Service -Name $ServiceName
    Write-Host "Service Status: $($service.Status)" -ForegroundColor Green
    
    if ($service.Status -eq "Running") {
        Write-Host ""
        Write-Host "SUCCESS: Hydrawise Collector service is running!" -ForegroundColor Green
        Write-Host ""
        Write-Host "=== Service Management Commands ===" -ForegroundColor Cyan
        Write-Host "Check status: nssm status $ServiceName"
        Write-Host "Stop service: nssm stop $ServiceName"
        Write-Host "Start service: nssm start $ServiceName"
        Write-Host "Restart service: nssm restart $ServiceName"
        Write-Host ""
        Write-Host "=== Log Files ===" -ForegroundColor Cyan
        Write-Host "Application logs: $WorkingDir\logs\hydrawise_service.log"
        Write-Host "Service stdout: $LogsDir\nssm_stdout.log"
        Write-Host "Service stderr: $LogsDir\nssm_stderr.log"
        Write-Host ""
        Write-Host "Monitor logs with: Get-Content '$LogsDir\nssm_stdout.log' -Wait -Tail 10"
    } else {
        Write-Host "WARNING: Service is not running. Check the error logs:" -ForegroundColor Red
        Write-Host "  $LogsDir\nssm_stderr.log"
    }
} else {
    Write-Host ""
    Write-Host "Service installed but not started." -ForegroundColor Yellow
    Write-Host "To start manually: nssm start $ServiceName"
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
