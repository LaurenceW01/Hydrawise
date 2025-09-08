#!/bin/bash
# Fix NSSM Environment Variables - Single Command Approach

echo "=== Fixing NSSM Service Environment Variables (Single Command) ==="
echo ""

SERVICE_NAME="HydrawiseCollector"
ENV_FILE=".env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found"
    exit 1
fi

echo "✓ .env file found"

# Stop the service
echo "Stopping service..."
nssm stop $SERVICE_NAME
sleep 3

# Build a single environment string with all variables
echo "Building environment variables string..."
env_string=""
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
        
        # Add to environment string (TAB separated for NSSM)
        if [ -n "$env_string" ]; then
            env_string="$env_string"$'\t'"$key=$value"
        else
            env_string="$key=$value"
        fi
        
        # Display progress (mask sensitive values)
        if [[ $key == *"PASSWORD"* ]] || [[ $key == *"URL"* ]]; then
            echo "  Adding $key = ********"
        else
            echo "  Adding $key = $value"
        fi
        
        ((count++))
    fi
done < "$ENV_FILE"

echo ""
echo "Setting all $count environment variables in single command..."

# Set all environment variables at once using TAB-separated format
nssm set $SERVICE_NAME AppEnvironmentExtra "$env_string"

if [ $? -eq 0 ]; then
    echo "✓ Successfully set all environment variables"
else
    echo "✗ Failed to set environment variables"
    exit 1
fi

# Verify the configuration
echo ""
echo "Verifying configuration..."
nssm get $SERVICE_NAME AppEnvironmentExtra | head -5
echo "... (truncated for display)"

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
    else
        echo ""
        echo "Service may have issues. Let's check what happened:"
        echo ""
        echo "Recent Windows service events:"
        echo "  Get-EventLog -LogName System -Source 'Service Control Manager' -Newest 5"
    fi
else
    echo ""
    echo "Service not started. To start manually:"
    echo "  nssm start $SERVICE_NAME"
fi

echo ""
echo "=== Environment Fix Complete ==="
