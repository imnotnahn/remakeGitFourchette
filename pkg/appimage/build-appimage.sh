#!/usr/bin/env bash

set -e

export QT_API=${QT_API:-pyqt6}
export PYVER=${PYVER:-3.12}

HERE="$(dirname "$(readlink -f -- "$0")" )"
ROOT="$(readlink -f -- "$HERE/../..")"

ARCH="$(uname -m)"

cd "$ROOT"
APPVER="$(python3 -c 'from gitfourchette.appconsts import APP_VERSION; print(APP_VERSION)')"
echo "App version: $APPVER"

mkdir -p "$ROOT/build"
cd "$ROOT/build"

# Freeze app constants
"$ROOT/update_resources.py" --freeze $QT_API

# Build AppImage
echo -e "$ROOT[$QT_API,pygments]"

# Try building using the standard python-appimage approach
if python3 -m python_appimage -v -a continuous build app -p $PYVER "$ROOT" 2>/tmp/appimage-error.log; then
    echo "AppImage built successfully!"
else
    echo "AppImage build had errors. Trying to fix..."
    cat /tmp/appimage-error.log
    
    # Apply our custom fix
    if [ -d "AppDir" ]; then
        python3 "$HERE/fix-appimage.py" "AppDir"
        
        # Continue with the AppImage build process manually
        if [ -f "squashfs-root/AppRun" ]; then
            echo "Using existing squashfs-root..."
        else
            echo "Extracting base AppImage..."
            if [ -f "base.AppImage" ]; then
                chmod +x base.AppImage
                ./base.AppImage --appimage-extract
            else
                echo "Error: base.AppImage not found. Cannot continue."
                exit 1
            fi
        fi
        
        # Copy our desktop file and icon
        cp -f "$HERE/gitfourchette.desktop" squashfs-root/
        cp -f "$HERE/gitfourchette.png" squashfs-root/

        # Create AppImage using appimagetool
        echo "Creating AppImage with appimagetool..."
        if command -v appimagetool &>/dev/null; then
            appimagetool squashfs-root
        else
            echo "appimagetool not found. Installing..."
            wget -O appimagetool "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
            chmod +x appimagetool
            ./appimagetool squashfs-root
        fi
    else
        echo "Error: AppDir not found. Cannot continue."
        exit 1
    fi
fi

# Rename to desired filename
for APPIM in ./*AppImage
do
    # Skip appimagetool itself
    if [[ "$APPIM" == *"appimagetool"* ]]; then
        continue
    fi
    
    NEWNAME="GitFourchette-$APPVER-$ARCH.AppImage"
    echo "Renaming $APPIM to $NEWNAME"
    mv "$APPIM" "$NEWNAME"
    chmod +x "$NEWNAME"
done

# Done
echo "AppImage created in $(pwd)"
