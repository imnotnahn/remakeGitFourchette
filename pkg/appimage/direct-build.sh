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