#!/bin/bash
# Fix NSSM Service Account - Use LocalSystem

echo "=== Switching NSSM Service to LocalSystem Account ==="
echo ""

SERVICE_NAME="HydrawiseCollector"

# Stop the service
echo "Stopping service..."
nssm stop $SERVICE_NAME
sleep 3

# Change to LocalSystem (no password required)
echo "Setting service to run as LocalSystem..."
nssm set $SERVICE_NAME ObjectName "LocalSystem"

# Reset back to our original script
echo "Setting correct script parameters..."
nssm set $SERVICE_NAME AppParameters "C:\Users\laure\Dev\Hydrawise\automated_collector.py"

# Try starting the service
echo ""
echo "Starting service..."
nssm start $SERVICE_NAME

# Check status after a few seconds
echo "Waiting 5 seconds..."
sleep 5

status=$(nssm status $SERVICE_NAME)
echo "Service Status: $status"

if [ "$status" = "SERVICE_RUNNING" ]; then
    echo ""
    echo "🎉 SUCCESS: Service is running!"
    echo ""
    echo "Check the logs:"
    echo "  tail -f logs/nssm_stdout.log"
    echo "  tail -f logs/hydrawise_service.log"
else
    echo ""
    echo "Service still not running. Let's check for any output:"
    echo ""
    echo "=== STDOUT Log ==="
    cat logs/nssm_stdout.log 2>/dev/null || echo "No stdout log found"
    echo ""
    echo "=== STDERR Log ==="
    cat logs/nssm_stderr.log 2>/dev/null || echo "No stderr log found"
    echo ""
    echo "=== Service Configuration ==="
    nssm dump $SERVICE_NAME | head -10
fi

echo ""
echo "=== Fix Complete ==="
