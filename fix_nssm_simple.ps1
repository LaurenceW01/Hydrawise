# Simple NSSM Environment Fix Script
Write-Host "=== Fixing NSSM Service Environment ===" -ForegroundColor Green

$ServiceName = "HydrawiseCollector"

# Check service exists
Write-Host "Checking service..." -ForegroundColor Yellow
nssm status $ServiceName
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Service not found" -ForegroundColor Red
    exit 1
}

# Check .env file
if (!(Test-Path ".env")) {
    Write-Host "ERROR: .env file not found" -ForegroundColor Red
    exit 1
}
Write-Host "✓ .env file found" -ForegroundColor Green

# Stop service
Write-Host "Stopping service..." -ForegroundColor Yellow
nssm stop $ServiceName
Start-Sleep -Seconds 3

# Clear existing environment
Write-Host "Clearing environment..." -ForegroundColor Yellow
nssm set $ServiceName AppEnvironmentExtra ""

# Read .env and set variables
Write-Host "Setting environment variables..." -ForegroundColor Yellow
$count = 0
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        
        # Remove quotes
        $value = $value -replace '^"(.*)"$', '$1'
        $value = $value -replace "^'(.*)'$", '$1'
        
        # Set the environment variable
        nssm set $ServiceName AppEnvironmentExtra "$key=$value"
        
        if ($key -like "*PASSWORD*" -or $key -like "*URL*") {
            Write-Host "  $key = ********" -ForegroundColor Gray
        } else {
            Write-Host "  $key = $value" -ForegroundColor Gray
        }
        $count++
    }
}

Write-Host ""
Write-Host "✓ Set $count environment variables" -ForegroundColor Green

# Ask to start service
Write-Host ""
$start = Read-Host "Start the service now? (Y/N)"
if ($start -eq "Y" -or $start -eq "y") {
    Write-Host "Starting service..." -ForegroundColor Yellow
    nssm start $ServiceName
    
    Start-Sleep -Seconds 5
    
    $status = nssm status $ServiceName
    Write-Host "Service Status: $status" -ForegroundColor Green
    
    if ($status -eq "SERVICE_RUNNING") {
        Write-Host ""
        Write-Host "🎉 SUCCESS! Service is running!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Monitor logs with:"
        Write-Host "  Get-Content logs\hydrawise_service.log -Wait -Tail 10"
        Write-Host "  Get-Content logs\nssm_stdout.log -Wait -Tail 10"
    } else {
        Write-Host ""
        Write-Host "Service may have issues. Check logs:" -ForegroundColor Yellow
        Write-Host "  Get-Content logs\nssm_stderr.log -Tail 20"
    }
}

Write-Host ""
Write-Host "=== Environment Fix Complete ===" -ForegroundColor Green
