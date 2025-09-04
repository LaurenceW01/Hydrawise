#!/bin/bash
# Render.com build script to install Chrome and dependencies

echo "=== Installing Chrome for Selenium ==="

# Update package lists
apt-get update

# Install Chrome dependencies
apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    default-jdk

# Add Google's official GPG key
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -

# Add Google Chrome repository
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Update package lists again
apt-get update

# Install Google Chrome
apt-get install -y google-chrome-stable

# Verify installation
google-chrome --version

echo "=== Chrome installation completed ==="

# Install Python dependencies
echo "=== Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== Build completed ==="
