# Fix NSSM Environment Variables Script
# This script sets all environment variables from .env file for the NSSM service

Write-Host "=== Fixing NSSM Service Environment Variables ===" -ForegroundColor Green
Write-Host ""

$ServiceName = "HydrawiseCollector"
$EnvFile = ".env"

# Check if service exists
Write-Host "Checking service status..." -ForegroundColor Yellow
$serviceStatus = nssm status $ServiceName 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Service $ServiceName not found" -ForegroundColor Red
    exit 1
}
Write-Host "Service found with status: $serviceStatus" -ForegroundColor Green

# Check if .env file exists
if (!(Test-Path $EnvFile)) {
    Write-Host "ERROR: .env file not found" -ForegroundColor Red
    exit 1
}
Write-Host ".env file found" -ForegroundColor Green

# Stop the service first
Write-Host ""
Write-Host "Stopping service..." -ForegroundColor Yellow
nssm stop $ServiceName
Start-Sleep -Seconds 3

# Clear existing environment variables
Write-Host "Clearing existing environment variables..." -ForegroundColor Yellow
nssm set $ServiceName AppEnvironmentExtra ""

# Read .env file and set environment variables
Write-Host "Setting environment variables from .env file..." -ForegroundColor Yellow
$envCount = 0
$envVars = @()

Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        
        # Remove quotes if present
        $value = $value -replace '^"(.*)"$', '$1'
        $value = $value -replace "^'(.*)'$", '$1'
        
        $envVars += "$key=$value"
        $envCount++
        
        # Show progress (mask sensitive values)
        if ($key -like "*PASSWORD*" -or $key -like "*URL*") {
            Write-Host "  Setting $key = ********" -ForegroundColor Gray
        } else {
            Write-Host "  Setting $key = $value" -ForegroundColor Gray
        }
    }
}

# Set all environment variables at once
Write-Host ""
Write-Host "Applying $envCount environment variables to service..." -ForegroundColor Yellow
foreach ($envVar in $envVars) {
    nssm set $ServiceName AppEnvironmentExtra $envVar
}

Write-Host "✓ Environment variables applied successfully" -ForegroundColor Green

# Verify some key variables were set
Write-Host ""
Write-Host "Verifying key environment variables..." -ForegroundColor Yellow
$keyVars = @("DATABASE_TYPE", "DATABASE_URL", "USE_ROTATING_LOGS")
foreach ($keyVar in $keyVars) {
    $found = $envVars | Where-Object { $_ -like "$keyVar=*" }
    if ($found) {
        Write-Host "✓ $keyVar is set" -ForegroundColor Green
    } else {
        Write-Host "✗ $keyVar is missing" -ForegroundColor Red
    }
}

# Ask if user wants to start the service
Write-Host ""
$startService = Read-Host "Do you want to start the service now? (Y/N)"
if ($startService -eq "Y" -or $startService -eq "y") {
    Write-Host ""
    Write-Host "Starting service..." -ForegroundColor Yellow
    nssm start $ServiceName
    
    Start-Sleep -Seconds 5
    
    # Check service status
    $newStatus = nssm status $ServiceName
    Write-Host "Service Status: $newStatus" -ForegroundColor Green
    
    if ($newStatus -eq "SERVICE_RUNNING") {
        Write-Host ""
        Write-Host "🎉 SUCCESS: Service is now running!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Monitor the service with:" -ForegroundColor Cyan
        Write-Host "  Get-Content logs\nssm_stdout.log -Wait -Tail 10"
        Write-Host "  Get-Content logs\hydrawise_service.log -Wait -Tail 10"
    } else {
        Write-Host ""
        Write-Host "⚠️  Service started but may have issues. Check logs:" -ForegroundColor Yellow
        Write-Host "  Get-Content logs\nssm_stderr.log -Tail 20"
        Write-Host "  Get-Content logs\nssm_stdout.log -Tail 20"
    }
} else {
    Write-Host ""
    Write-Host "Service not started. To start manually:" -ForegroundColor Yellow
    Write-Host "  nssm start $ServiceName"
}

Write-Host ""
Write-Host "=== Environment Fix Complete ===" -ForegroundColor Green
