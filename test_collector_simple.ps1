# Simple Test Script for Hydrawise Collector
Write-Host "=== Hydrawise Collector Test ===" -ForegroundColor Green

# Set paths
$WorkingDir = "C:\Users\laure\Dev\Hydrawise"
$PythonExe = "$WorkingDir\hydrawise-venv\Scripts\python.exe"
$ScriptPath = "$WorkingDir\automated_collector.py"

# Change directory
Set-Location $WorkingDir
Write-Host "Working directory: $(Get-Location)" -ForegroundColor Yellow

# Test 1: Check files exist
Write-Host ""
Write-Host "=== File Check ===" -ForegroundColor Cyan
if (Test-Path $PythonExe) {
    Write-Host "✓ Python found: $PythonExe" -ForegroundColor Green
} else {
    Write-Host "✗ Python NOT found: $PythonExe" -ForegroundColor Red
}

if (Test-Path $ScriptPath) {
    Write-Host "✓ Script found: $ScriptPath" -ForegroundColor Green
} else {
    Write-Host "✗ Script NOT found: $ScriptPath" -ForegroundColor Red
}

if (Test-Path ".env") {
    Write-Host "✓ .env file found" -ForegroundColor Green
} else {
    Write-Host "✗ .env file NOT found" -ForegroundColor Red
}

# Test 2: Run help command
Write-Host ""
Write-Host "=== Help Test ===" -ForegroundColor Cyan
Write-Host "Running: python automated_collector.py --help"
Write-Host ""

& $PythonExe $ScriptPath --help

Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Help command successful" -ForegroundColor Green
} else {
    Write-Host "✗ Help command failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
}

# Test 3: Show environment variables
Write-Host ""
Write-Host "=== Environment Variables ===" -ForegroundColor Cyan
if (Test-Path ".env") {
    $envLines = Get-Content ".env" | Where-Object { $_ -match "^[^#].*=" }
    Write-Host "Found $($envLines.Count) environment variables:"
    foreach ($line in $envLines) {
        if ($line -like "*PASSWORD*" -or $line -like "*URL*") {
            $parts = $line -split "=", 2
            Write-Host "  $($parts[0]) = ********" -ForegroundColor Gray
        } else {
            Write-Host "  $line" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "No .env file found" -ForegroundColor Red
}

# Test 4: Optional run test
Write-Host ""
Write-Host "=== Quick Run Test ===" -ForegroundColor Cyan
$doTest = Read-Host "Run a quick test? (Y/N)"
if ($doTest -eq "Y" -or $doTest -eq "y") {
    Write-Host "Running: python automated_collector.py --run-once"
    Write-Host ""
    & $PythonExe $ScriptPath --run-once
    Write-Host ""
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Quick test successful" -ForegroundColor Green
    } else {
        Write-Host "✗ Quick test failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
    }
}

# Test 5: Check logs
Write-Host ""
Write-Host "=== Log Files ===" -ForegroundColor Cyan
$logs = @("logs\hydrawise_service.log", "logs\nssm_stdout.log", "logs\nssm_stderr.log")
foreach ($log in $logs) {
    if (Test-Path $log) {
        $size = (Get-Item $log).Length
        Write-Host "✓ $log ($size bytes)" -ForegroundColor Green
    } else {
        Write-Host "✗ $log (not found)" -ForegroundColor Red
    }
}

# Summary
Write-Host ""
Write-Host "=== Service Commands ===" -ForegroundColor Yellow
Write-Host "Start:  nssm start HydrawiseCollector"
Write-Host "Stop:   nssm stop HydrawiseCollector"
Write-Host "Status: nssm status HydrawiseCollector"
Write-Host ""
Write-Host "=== Test Complete ===" -ForegroundColor Green
