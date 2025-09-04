#!/bin/bash
# Render.com build script to install Chrome and dependencies

echo "=== Installing Chrome for Selenium ==="

# Install Chrome via direct download (more reliable on render.com)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Update and install Chrome with dependencies
apt-get update
apt-get install -y \
    google-chrome-stable \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    libxtst6 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0

# Verify Chrome installation
if command -v google-chrome >/dev/null 2>&1; then
    echo "✅ Chrome installed successfully"
    google-chrome --version
else
    echo "❌ Chrome installation failed"
    exit 1
fi

# Set Chrome binary path for Selenium
export CHROME_BIN=/usr/bin/google-chrome

# Install Python dependencies
echo "=== Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== Build completed successfully ==="
