#!/usr/bin/env python3
"""
Fix script for python-appimage with Python 3.13
This script modifies the AppDir/AppRun script to use the correct Python path
"""

import os
import sys
import re
from pathlib import Path

def fix_apprun_script(appdir_path):
    """Fix the AppRun script in the AppDir"""
    apprun_path = os.path.join(appdir_path, "AppRun")
    
    if not os.path.exists(apprun_path):
        print(f"Error: {apprun_path} does not exist")
        return False
    
    # Read the current script
    with open(apprun_path, 'r') as f:
        content = f.read()
    
    # Backup the original
    with open(apprun_path + '.bak', 'w') as f:
        f.write(content)
    
    # Fix the Python path in the script
    python_version = os.environ.get('PYVER', '3.12')
    
    # Replace any reference to a mount point Python path with a direct path
    fixed_content = re.sub(
        r'/tmp/\.mount_[^/]+/opt/python\d+\.\d+/bin/python\d+\.\d+',
        f'$APPDIR/opt/python{python_version}/bin/python{python_version}',
        content
    )
    
    # Write the fixed script
    with open(apprun_path, 'w') as f:
        f.write(fixed_content)
    
    # Make it executable
    os.chmod(apprun_path, 0o755)
    
    print(f"Fixed {apprun_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        appdir_path = sys.argv[1]
    else:
        # Default to current directory/AppDir
        appdir_path = os.path.join(os.getcwd(), "AppDir")
    
    if not os.path.isdir(appdir_path):
        print(f"Error: {appdir_path} is not a directory")
        sys.exit(1)
    
    if fix_apprun_script(appdir_path):
        print("AppRun script fixed successfully")
        sys.exit(0)
    else:
        print("Failed to fix AppRun script")
        sys.exit(1) 