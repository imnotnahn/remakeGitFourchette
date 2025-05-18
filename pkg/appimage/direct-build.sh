#!/usr/bin/env bash
# Direct AppImage builder without using python-appimage
# This uses PyInstaller to create the base and appimagetool to package it

set -e

export QT_API=${QT_API:-pyqt6}
PYTHON=${PYTHON:-python3}
HERE="$(dirname "$(readlink -f -- "$0")" )"
ROOT="$(readlink -f -- "$HERE/../..")"
ARCH="$(uname -m)"
cd "$ROOT"

APPVER="$($PYTHON -c 'from gitfourchette.appconsts import APP_VERSION; print(APP_VERSION)')"
echo "App version: $APPVER"

# Export APP_VERSION for use in spec files
export APP_VERSION=$APPVER

# Install required packages
$PYTHON -m pip install --upgrade pip setuptools wheel
$PYTHON -m pip install --upgrade -e .[$QT_API,pygments]
$PYTHON -m pip install --upgrade pyinstaller

# Freeze app constants
"$ROOT/update_resources.py" --freeze $QT_API

# Create PyInstaller build
mkdir -p "$ROOT/build"
cd "$ROOT/build"

# Replace the path in the spec file with the correct one
TEMP_SPEC="simple-linux-temp.spec"
cat "$ROOT/pkg/pyinstaller/simple-linux.spec" | sed "s|ROOT_DIR = os.path.abspath.*|ROOT_DIR = os.path.abspath('$ROOT')|" > $TEMP_SPEC

# Run PyInstaller with the modified spec file
$PYTHON -m PyInstaller $TEMP_SPEC --noconfirm

# Clean up temporary spec file
rm $TEMP_SPEC

# Create AppDir structure
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps
mkdir -p AppDir/usr/share/metainfo

# Copy binaries
cp -r dist/GitFourchette/* AppDir/usr/bin/

# Create a SSL certificate helper script
cat > AppDir/usr/bin/pygit2_ssl_helper.py << 'EOF'
"""
Helper script to configure SSL certificates for pygit2
This is automatically imported when the app starts
"""
import os
import sys
import logging
from pathlib import Path

def configure_ssl_certs():
    """Configure SSL certificates for pygit2"""
    logging.info("Configuring SSL certificates for pygit2")
    
    # First try environment variables
    if os.environ.get('SSL_CERT_DIR') and os.environ.get('SSL_CERT_FILE'):
        logging.info(f"Using SSL certificates from environment: {os.environ.get('SSL_CERT_DIR')}, {os.environ.get('SSL_CERT_FILE')}")
        return
    
    # Common certificate directories
    cert_dirs = [
        '/etc/ssl/certs',
        '/etc/pki/tls/certs',
        '/etc/pki/ca-trust/extracted/pem',
        '/usr/share/ca-certificates'
    ]
    
    # Common certificate files
    cert_files = [
        '/etc/ssl/certs/ca-certificates.crt',
        '/etc/pki/tls/certs/ca-bundle.crt',
        '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem'
    ]
    
    # Check bundled certificate directory in AppImage
    appdir = os.environ.get('APPDIR')
    if appdir:
        bundled_cert_dir = os.path.join(appdir, 'etc/ssl/certs')
        if os.path.isdir(bundled_cert_dir):
            os.environ['SSL_CERT_DIR'] = bundled_cert_dir
            logging.info(f"Using bundled SSL certificate directory: {bundled_cert_dir}")
            
            # Look for bundled certificate file
            for cert_file in os.listdir(bundled_cert_dir):
                if cert_file.endswith('.crt') or cert_file.endswith('.pem'):
                    full_path = os.path.join(bundled_cert_dir, cert_file)
                    os.environ['SSL_CERT_FILE'] = full_path
                    logging.info(f"Using bundled SSL certificate file: {full_path}")
                    return
    
    # Try to find certificate directory on the system
    for cert_dir in cert_dirs:
        if os.path.isdir(cert_dir):
            os.environ['SSL_CERT_DIR'] = cert_dir
            logging.info(f"Using system SSL certificate directory: {cert_dir}")
            break
    
    # Try to find certificate file on the system
    for cert_file in cert_files:
        if os.path.isfile(cert_file):
            os.environ['SSL_CERT_FILE'] = cert_file
            logging.info(f"Using system SSL certificate file: {cert_file}")
            break
    
    if not os.environ.get('SSL_CERT_DIR') or not os.environ.get('SSL_CERT_FILE'):
        logging.warning("Could not find SSL certificates!")

# Configure SSL certificates
configure_ssl_certs()
EOF

# Create a helper script for Git authentication settings
cat > AppDir/usr/bin/git_auth_helper.py << 'EOF'
"""
Helper script to configure Git authentication settings
"""
import os
import sys
import logging
import subprocess
from pathlib import Path

def configure_git_auth():
    """Configure Git authentication"""
    # Ensure HOME is properly set
    if not os.environ.get('HOME'):
        os.environ['HOME'] = str(Path.home())
        logging.info(f"Set HOME environment variable to {os.environ['HOME']}")
    
    # Make sure Git credential helper is available
    try:
        subprocess.run(
            ['git', 'config', '--global', 'credential.helper', 'store'],
            check=True,
            capture_output=True,
            text=True
        )
        logging.info("Configured Git credential.helper to 'store'")
    except Exception as e:
        logging.warning(f"Failed to configure Git credential helper: {e}")
    
    # Ensure credentials are used properly
    try:
        subprocess.run(
            ['git', 'config', '--global', 'credential.interactive', 'always'],
            check=True, 
            capture_output=True,
            text=True
        )
        logging.info("Set credential.interactive to 'always'")
    except Exception as e:
        logging.warning(f"Failed to set credential.interactive: {e}")

# Configure Git authentication
configure_git_auth()
EOF

# Create a hook to import the SSL helper script
cat > AppDir/usr/bin/sitecustomize.py << 'EOF'
"""
This file is automatically imported by Python on startup
We use it to configure SSL certificates for pygit2
"""
import os
import sys
import importlib.util
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Try to import our SSL helper
try:
    spec = importlib.util.spec_from_file_location(
        "pygit2_ssl_helper", 
        os.path.join(os.path.dirname(__file__), "pygit2_ssl_helper.py")
    )
    if spec:
        ssl_helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ssl_helper)
        logging.info("SSL certificate helper loaded successfully")
except Exception as e:
    logging.error(f"Error loading SSL certificate helper: {e}")

# Try to import our Git auth helper
try:
    spec = importlib.util.spec_from_file_location(
        "git_auth_helper", 
        os.path.join(os.path.dirname(__file__), "git_auth_helper.py")
    )
    if spec:
        auth_helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(auth_helper)
        logging.info("Git authentication helper loaded successfully")
except Exception as e:
    logging.error(f"Error loading Git authentication helper: {e}")
EOF

# Copy desktop file and icon
cp "$ROOT/pkg/appimage/gitfourchette.desktop" AppDir/usr/share/applications/
cp "$ROOT/pkg/appimage/gitfourchette.desktop" AppDir/  # Copy to root as well for appimagetool
cp "$ROOT/pkg/appimage/gitfourchette.png" AppDir/usr/share/icons/hicolor/256x256/apps/
cp "$ROOT/pkg/appimage/gitfourchette.png" AppDir/  # Copy to root as well for appimagetool

# Create AppRun script
cat > AppDir/AppRun << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"

# Ensure HOME is set correctly
if [ -z "$HOME" ]; then
  export HOME="$(getent passwd $(whoami) | cut -d: -f6)"
  echo "Setting HOME to $HOME"
fi

# Set Git credential helper to make authentication work
git config --global credential.helper 'store'
git config --global credential.interactive always

# Set up SSL certificate environment variables for pygit2
# Try common certificate locations in order of preference
for cert_dir in \
    /etc/ssl/certs \
    /etc/pki/tls/certs \
    /etc/pki/ca-trust/extracted/pem \
    /usr/share/ca-certificates
do
    if [ -d "$cert_dir" ]; then
        export SSL_CERT_DIR="$cert_dir"
        echo "Using SSL certificate directory: $cert_dir"
        break
    fi
done

for cert_file in \
    /etc/ssl/certs/ca-certificates.crt \
    /etc/pki/tls/certs/ca-bundle.crt \
    /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem
do
    if [ -f "$cert_file" ]; then
        export SSL_CERT_FILE="$cert_file"
        echo "Using SSL certificate file: $cert_file"
        break
    fi
done

# Export APPDIR for the Python helper script
export APPDIR="${HERE}"

# Run the application
exec "${HERE}/usr/bin/gitfourchette-bin" "$@"
EOF
chmod +x AppDir/AppRun

# Download and use appimagetool if not available
if ! command -v appimagetool &> /dev/null; then
    echo "Downloading appimagetool..."
    wget -O appimagetool "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool
    env ARCH=x86_64 ./appimagetool AppDir "GitFourchette-$APPVER-$ARCH.AppImage"
else
    env ARCH=x86_64 appimagetool AppDir "GitFourchette-$APPVER-$ARCH.AppImage"
fi

echo "AppImage created: GitFourchette-$APPVER-$ARCH.AppImage" 