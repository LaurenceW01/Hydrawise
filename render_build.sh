#!/usr/bin/env bash
set -e

echo "=== Render.com Custom Build Script ==="
echo "Installing Chrome and dependencies for Selenium web scraping..."

# Use render.com writable directory
STORAGE_DIR=/opt/render/project/.render
echo "Setting up Chrome installation directory: $STORAGE_DIR"
mkdir -p $STORAGE_DIR/chrome
cd $STORAGE_DIR/chrome

# Download Chrome stable .deb package (more reliable)
echo "Downloading Google Chrome stable..."
if ! wget -O google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb; then
    echo "❌ Failed to download Chrome .deb package"
    exit 1
fi

# Extract Chrome from .deb package (no installation needed)
echo "Extracting Chrome from .deb package..."
if ! dpkg-deb -x google-chrome-stable_current_amd64.deb ./; then
    echo "❌ Failed to extract Chrome .deb package"
    exit 1
fi

# Clean up .deb file
rm google-chrome-stable_current_amd64.deb

# Chrome binary will be at ./opt/google/chrome/chrome
echo "Chrome extracted to: $STORAGE_DIR/chrome/opt/google/chrome/chrome"

# Download latest stable ChromeDriver
echo "Downloading ChromeDriver..."
CHROME_VERSION=$(./opt/google/chrome/chrome --version | grep -oP '\d+\.\d+\.\d+\.\d+')
echo "Chrome version: $CHROME_VERSION"

# Get matching ChromeDriver version
CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION%%.*}")
echo "ChromeDriver version: $CHROMEDRIVER_VERSION"

if ! wget -O chromedriver_linux64.zip "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"; then
    echo "❌ Failed to download ChromeDriver"
    exit 1
fi

echo "Extracting ChromeDriver..."
if ! unzip -q chromedriver_linux64.zip; then
    echo "❌ Failed to extract ChromeDriver"
    exit 1
fi

chmod +x chromedriver
rm chromedriver_linux64.zip

# Add Chrome to PATH for this build
export PATH="$STORAGE_DIR/chrome:$PATH"
export CHROME_BIN="$STORAGE_DIR/chrome/opt/google/chrome/chrome"

# Verify installations
echo "Verifying Chrome installation..."
if $STORAGE_DIR/chrome/opt/google/chrome/chrome --version; then
    echo "✅ Chrome installed successfully"
    echo "Chrome location: $STORAGE_DIR/chrome/opt/google/chrome/chrome"
else
    echo "❌ Chrome installation failed"
    exit 1
fi

echo "Verifying ChromeDriver installation..."
if $STORAGE_DIR/chrome/chromedriver --version; then
    echo "✅ ChromeDriver installed successfully"
    echo "ChromeDriver location: $STORAGE_DIR/chrome/chromedriver"
else
    echo "❌ ChromeDriver installation failed"
    exit 1
fi

# Go back to project directory
cd $RENDER_SRC_ROOT || cd /opt/render/project/src

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "✅ Build completed successfully!"
echo "Chrome binary location: /opt/chrome/chrome"
echo "ChromeDriver location: /usr/bin/chromedriver"
