#!/usr/bin/env bash

# GitFourchette build script for all platforms
# This script detects the current platform and builds the appropriate package

set -e

PYTHON=${PYTHON:-python3}
export QT_API=${QT_API:-pyqt6}
export PYVER=${PYVER:-3.12}  # Changed from 3.13 to 3.12
SCRIPT_DIR="$(dirname "$(readlink -f -- "$0")" )"
cd "$SCRIPT_DIR"

echo "===== Building GitFourchette packages ====="
echo "Python: $PYTHON"
echo "Python version: $PYVER"
echo "Qt API: $QT_API"

# Install common dependencies
$PYTHON -m pip install --upgrade pip setuptools wheel
$PYTHON -m pip install --upgrade -e .[$QT_API,pygments]
$PYTHON -m pip install --upgrade pyinstaller

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "===== Building for Linux (AppImage) ====="
    
    # Use our direct build script (doesn't depend on python-appimage)
    ./pkg/appimage/direct-build.sh
    
    echo "AppImage created in build/ directory"

elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "===== Building for macOS ====="
    
    # Build macOS app
    ./pkg/pyinstaller/build-macos-app.sh
    
    # Create ZIP archive
    ditto -c -k --keepParent dist/GitFourchette.app GitFourchette-mac.zip
    
    echo "macOS app created in dist/ directory"
    echo "ZIP archive: GitFourchette-mac.zip"

elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    echo "===== Building for Windows ====="
    
    # Install Pillow for icon conversion if not already installed
    $PYTHON -m pip install --upgrade pillow
    
    # Create ICO file if it doesn't exist
    if [ ! -f "gitfourchette/assets/icons/gitfourchette.ico" ]; then
        echo "Creating ICO file from PNG..."
        $PYTHON -c "from PIL import Image; img = Image.open('gitfourchette/assets/icons/gitfourchette.png'); img.save('gitfourchette/assets/icons/gitfourchette.ico')"
    fi
    
    # Convert shell script call to cmd for Windows
    cmd /c pkg\\pyinstaller\\build-windows-exe.bat
    
    # Create ZIP archive
    if command -v 7z &> /dev/null; then
        7z a -tzip GitFourchette-win.zip ./dist/GitFourchette.exe
        echo "ZIP archive: GitFourchette-win.zip"
    else
        echo "7-Zip not found. Please manually zip the executable in dist/GitFourchette.exe"
    fi
    
    echo "Windows executable created in dist/ directory"

else
    echo "Unsupported operating system: $OSTYPE"
    exit 1
fi

echo "===== Build completed successfully =====" 