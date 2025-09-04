#!/bin/bash
# Quick verification script to test Chrome installation steps

echo "=== Chrome Installation Verification ==="

# Check if we can download Chrome
echo "Testing Chrome download..."
wget -q --spider https://storage.googleapis.com/chrome-for-testing/119.0.6045.105/linux64/chrome-linux64.zip
if [ $? -eq 0 ]; then
    echo "✅ Chrome download URL accessible"
else
    echo "❌ Chrome download URL not accessible"
fi

# Check if we can download ChromeDriver
echo "Testing ChromeDriver download..."
wget -q --spider https://storage.googleapis.com/chrome-for-testing/119.0.6045.105/linux64/chromedriver-linux64.zip
if [ $? -eq 0 ]; then
    echo "✅ ChromeDriver download URL accessible"
else
    echo "❌ ChromeDriver download URL not accessible"
fi

# Check system commands
echo "Checking required system commands..."
for cmd in wget unzip chmod ln; do
    if command -v $cmd >/dev/null 2>&1; then
        echo "✅ $cmd available"
    else
        echo "❌ $cmd not available"
    fi
done

echo "=== Verification Complete ==="
