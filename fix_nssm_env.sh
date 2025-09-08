#!/bin/bash
# Fix NSSM Environment Variables - Bash Script

echo "=== Fixing NSSM Service Environment Variables ==="
echo ""

SERVICE_NAME="HydrawiseCollector"
ENV_FILE=".env"

# Check if service exists
echo "Checking service status..."
if ! nssm status $SERVICE_NAME > /dev/null 2>&1; then
    echo "ERROR: Service $SERVICE_NAME not found"
    exit 1
fi

echo "✓ Service found"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found"
    exit 1
fi

echo "✓ .env file found"

# Stop the service
echo ""
echo "Stopping service..."
nssm stop $SERVICE_NAME
sleep 3

# Clear existing environment variables
echo "Clearing existing environment variables..."
nssm set $SERVICE_NAME AppEnvironmentExtra ""

# Read .env file and set environment variables
echo "Setting environment variables from .env file..."
echo ""

count=0
while IFS= read -r line; do
    # Skip comments and empty lines
    if [[ $line =~ ^[[:space:]]*# ]] || [[ -z "${line// }" ]]; then
        continue
    fi
    
    # Check if line contains =
    if [[ $line == *"="* ]]; then
        # Split on first = sign
        key="${line%%=*}"
        value="${line#*=}"
        
        # Trim whitespace
        key=$(echo "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        
        # Remove quotes if present
        if [[ $value =~ ^\".*\"$ ]]; then
            value="${value:1:-1}"
        elif [[ $value =~ ^\'.*\'$ ]]; then
            value="${value:1:-1}"
        fi
        
        # Set the environment variable in NSSM
        nssm set $SERVICE_NAME AppEnvironmentExtra "$key=$value"
        
        # Display progress (mask sensitive values)
        if [[ $key == *"PASSWORD"* ]] || [[ $key == *"URL"* ]]; then
            echo "  Setting $key = ********"
        else
            echo "  Setting $key = $value"
        fi
        
        ((count++))
    fi
done < "$ENV_FILE"

echo ""
echo "✓ Set $count environment variables"

# Verify key variables
echo ""
echo "Verifying key environment variables were set..."
key_vars=("DATABASE_TYPE" "DATABASE_URL" "USE_ROTATING_LOGS" "LOG_LEVEL")
for var in "${key_vars[@]}"; do
    if grep -q "^$var=" "$ENV_FILE"; then
        echo "✓ $var is configured"
    else
        echo "⚠ $var not found in .env"
    fi
done

# Ask if user wants to start the service
echo ""
read -p "Do you want to start the service now? (y/N): " start_service

if [[ $start_service =~ ^[Yy]$ ]]; then
    echo ""
    echo "Starting service..."
    nssm start $SERVICE_NAME
    
    sleep 5
    
    # Check service status
    status=$(nssm status $SERVICE_NAME)
    echo "Service Status: $status"
    
    if [ "$status" = "SERVICE_RUNNING" ]; then
        echo ""
        echo "🎉 SUCCESS: Service is now running!"
        echo ""
        echo "Monitor the service with:"
        echo "  tail -f logs/hydrawise_service.log"
        echo "  tail -f logs/nssm_stdout.log"
        echo ""
        echo "Service management commands:"
        echo "  nssm status $SERVICE_NAME"
        echo "  nssm stop $SERVICE_NAME"
        echo "  nssm restart $SERVICE_NAME"
    else
        echo ""
        echo "⚠ Service started but may have issues. Check logs:"
        echo "  tail logs/nssm_stderr.log"
        echo "  tail logs/nssm_stdout.log"
    fi
else
    echo ""
    echo "Service not started. To start manually:"
    echo "  nssm start $SERVICE_NAME"
fi

echo ""
echo "=== Environment Fix Complete ==="
