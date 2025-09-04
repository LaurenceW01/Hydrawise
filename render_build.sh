#!/usr/bin/env bash
set -e

echo "=== Render.com Custom Build Script ==="
echo "Installing Chrome and dependencies for Selenium web scraping..."

# Create local directory for Chrome installation (avoid system directories)
echo "Setting up Chrome installation directory..."
mkdir -p $HOME/chrome
cd $HOME/chrome

# Download and install Chrome directly to user space
echo "Downloading Google Chrome..."
wget -q -O chrome-linux64.zip https://storage.googleapis.com/chrome-for-testing/119.0.6045.105/linux64/chrome-linux64.zip
unzip -q chrome-linux64.zip

# Set up Chrome in user directory
echo "Setting up Chrome..."
mv chrome-linux64 chrome
chmod +x chrome/chrome

# Download matching ChromeDriver
echo "Downloading ChromeDriver..."
wget -q -O chromedriver-linux64.zip https://storage.googleapis.com/chrome-for-testing/119.0.6045.105/linux64/chromedriver-linux64.zip
unzip -q chromedriver-linux64.zip

# Set up ChromeDriver
echo "Setting up ChromeDriver..."
mv chromedriver-linux64/chromedriver .
chmod +x chromedriver

# Clean up downloaded files
rm -f chrome-linux64.zip chromedriver-linux64.zip
rm -rf chromedriver-linux64

# Add Chrome to PATH for this build
export PATH="$HOME/chrome:$PATH"
export PATH="$HOME/chrome/chrome:$PATH"
export CHROME_BIN="$HOME/chrome/chrome/chrome"

# Verify installations
echo "Verifying Chrome installation..."
if $HOME/chrome/chrome/chrome --version; then
    echo "✅ Chrome installed successfully"
    echo "Chrome location: $HOME/chrome/chrome/chrome"
else
    echo "❌ Chrome installation failed"
    exit 1
fi

echo "Verifying ChromeDriver installation..."
if $HOME/chrome/chromedriver --version; then
    echo "✅ ChromeDriver installed successfully"
    echo "ChromeDriver location: $HOME/chrome/chromedriver"
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
