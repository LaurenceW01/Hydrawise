# Test Hydrawise Collector Script
# This script tests the automated collector manually before running as a service

Write-Host "=== Hydrawise Collector Manual Test ===" -ForegroundColor Green
Write-Host ""

# Configuration
$WorkingDir = "C:\Users\laure\Dev\Hydrawise"
$PythonExe = "$WorkingDir\hydrawise-venv\Scripts\python.exe"
$ScriptPath = "$WorkingDir\automated_collector.py"
$EnvFile = "$WorkingDir\.env"

# Change to working directory
Write-Host "Changing to working directory..." -ForegroundColor Yellow
Set-Location $WorkingDir
Write-Host "Current directory: $(Get-Location)" -ForegroundColor Green

# Check if files exist
Write-Host ""
Write-Host "Checking required files..." -ForegroundColor Yellow

if (!(Test-Path $PythonExe)) {
    Write-Host "ERROR: Python executable not found at: $PythonExe" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Python executable found: $PythonExe" -ForegroundColor Green

if (!(Test-Path $ScriptPath)) {
    Write-Host "ERROR: Script not found at: $ScriptPath" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Script found: $ScriptPath" -ForegroundColor Green

if (!(Test-Path $EnvFile)) {
    Write-Host "WARNING: .env file not found at: $EnvFile" -ForegroundColor Red
    Write-Host "The service may not work without environment variables." -ForegroundColor Red
} else {
    Write-Host "✓ .env file found: $EnvFile" -ForegroundColor Green
}

# Test 1: Check script help
Write-Host ""
Write-Host "=== TEST 1: Script Help ===" -ForegroundColor Cyan
Write-Host "Testing: python automated_collector.py --help"
Write-Host ""

& $PythonExe $ScriptPath --help
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Script help command successful" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "✗ Script help command failed with exit code: $LASTEXITCODE" -ForegroundColor Red
}

# Test 2: Check environment variables
Write-Host ""
Write-Host "=== TEST 2: Environment Variables Check ===" -ForegroundColor Cyan

if (Test-Path $EnvFile) {
    Write-Host "Reading .env file..." -ForegroundColor Yellow
    Write-Host ""
    
    $envContent = Get-Content $EnvFile
    $envCount = 0
    
    foreach ($line in $envContent) {
        if ($line -match '^([^#][^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            
            if ($key -like "*PASSWORD*" -or $key -like "*URL*") {
                Write-Host "  $key = ********" -ForegroundColor Green
            } else {
                Write-Host "  $key = $value" -ForegroundColor Green
            }
            $envCount++
        }
    }
    
    Write-Host ""
    Write-Host "Total environment variables found: $envCount" -ForegroundColor Cyan
} else {
    Write-Host "No .env file found - environment variables not available" -ForegroundColor Red
}

# Test 3: Quick run test
Write-Host ""
Write-Host "=== TEST 3: Quick Run Test ===" -ForegroundColor Cyan
Write-Host "Testing: python automated_collector.py --run-once"
Write-Host ""

$runTest = Read-Host "Do you want to run a quick test of the collector? (Y/N)"

if ($runTest -eq "Y" -or $runTest -eq "y") {
    Write-Host ""
    Write-Host "Running automated collector test..." -ForegroundColor Yellow
    Write-Host ""
    
    & $PythonExe $ScriptPath --run-once
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✓ Automated collector test completed successfully!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "✗ Automated collector test failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    }
} else {
    Write-Host "Skipping automated collector test." -ForegroundColor Yellow
}

# Test 4: Check log files
Write-Host ""
Write-Host "=== TEST 4: Log Files Check ===" -ForegroundColor Cyan

$logFiles = @(
    "$WorkingDir\logs\hydrawise_service.log",
    "$WorkingDir\logs\nssm_stdout.log", 
    "$WorkingDir\logs\nssm_stderr.log"
)

foreach ($logFile in $logFiles) {
    if (Test-Path $logFile) {
        $size = (Get-Item $logFile).Length
        $lastWrite = (Get-Item $logFile).LastWriteTime
        Write-Host "✓ $logFile ($size bytes, modified: $lastWrite)" -ForegroundColor Green
    } else {
        Write-Host "✗ $logFile (not found)" -ForegroundColor Red
    }
}

# Summary and recommendations
Write-Host ""
Write-Host "=== SUMMARY AND RECOMMENDATIONS ===" -ForegroundColor Cyan

if (Test-Path $EnvFile) {
    Write-Host "✓ Environment file exists" -ForegroundColor Green
} else {
    Write-Host "✗ Create a .env file with database configuration" -ForegroundColor Red
}

Write-Host ""
Write-Host "Service Management Commands:" -ForegroundColor Yellow
Write-Host "  nssm start HydrawiseCollector"
Write-Host "  nssm stop HydrawiseCollector" 
Write-Host "  nssm status HydrawiseCollector"
Write-Host ""
Write-Host "Log Monitoring:" -ForegroundColor Yellow
Write-Host "  Get-Content logs\nssm_stdout.log -Wait -Tail 10"
Write-Host "  Get-Content logs\nssm_stderr.log -Wait -Tail 10"

Write-Host ""
Write-Host "=== Test Complete ===" -ForegroundColor Green