#!/usr/bin/env bash
set -e

echo "=== Render.com Custom Build Script ==="
echo "Installing Chrome and dependencies for Selenium web scraping..."

# Update package lists first (with sudo for render.com)
echo "Updating package lists..."
sudo apt-get update

# Install essential dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    wget \
    curl \
    unzip \
    xvfb \
    libnss3 \
    libgconf-2-4 \
    libxss1 \
    libappindicator1 \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libgtk-3-0

# Download and install Chrome directly
echo "Downloading Google Chrome..."
wget -q -O chrome-linux64.zip https://storage.googleapis.com/chrome-for-testing/119.0.6045.105/linux64/chrome-linux64.zip
unzip -q chrome-linux64.zip

# Install Chrome to system location (with sudo)
echo "Installing Chrome to system location..."
sudo mv chrome-linux64 /opt/chrome
sudo chmod +x /opt/chrome/chrome

# Create symlink for standard location
sudo ln -sf /opt/chrome/chrome /usr/bin/google-chrome

# Download matching ChromeDriver
echo "Downloading ChromeDriver..."
wget -q -O chromedriver-linux64.zip https://storage.googleapis.com/chrome-for-testing/119.0.6045.105/linux64/chromedriver-linux64.zip
unzip -q chromedriver-linux64.zip

# Install ChromeDriver to system location (with sudo)
echo "Installing ChromeDriver to system location..."
sudo mv chromedriver-linux64/chromedriver /usr/bin/chromedriver
sudo chmod +x /usr/bin/chromedriver

# Clean up downloaded files
rm -f chrome-linux64.zip chromedriver-linux64.zip
rm -rf chromedriver-linux64

# Verify installations
echo "Verifying Chrome installation..."
if /opt/chrome/chrome --version; then
    echo "✅ Chrome installed successfully"
else
    echo "❌ Chrome installation failed"
    exit 1
fi

echo "Verifying ChromeDriver installation..."
if chromedriver --version; then
    echo "✅ ChromeDriver installed successfully"
else
    echo "❌ ChromeDriver installation failed"
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "✅ Build completed successfully!"
echo "Chrome binary location: /opt/chrome/chrome"
echo "ChromeDriver location: /usr/bin/chromedriver"
