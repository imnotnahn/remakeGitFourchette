# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Define root directory (absolute path to repo root)
ROOT_DIR = os.path.abspath('/run/media/imnahn/Data/Code/gitfourchette')

# Get version from environment or default to 1.3.0
APP_VERSION = os.environ.get('APP_VERSION', '1.3.0')
QT_API = os.environ.get('QT_API', 'pyqt6')

# Write build constants
with open(os.path.join(ROOT_DIR, 'gitfourchette', 'appconsts.py'), 'r+') as f:
    content = f.read()
    # Get current date in UTC
    from datetime import datetime, timezone
    buildDate = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    
    import re
    pattern = r'# BEGIN_FREEZE_CONSTS.*?# END_FREEZE_CONSTS'
    replacement = f'''# BEGIN_FREEZE_CONSTS
####################################
# Do not commit these changes!
####################################

APP_FREEZE_COMMIT = "unknown"
APP_FREEZE_DATE = "{buildDate}"
APP_FREEZE_QT = "{QT_API.lower()}"
# END_FREEZE_CONSTS'''
    
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    f.seek(0)
    f.write(content)
    f.truncate()

# Exclude list based on QT API
excludes = []
if QT_API == 'pyqt6':
    excludes = ['PySide6', 'PyQt5', 'PySide2', 'PyQt6.uic', 'PyQt6.QtChart', 'PyQt6.Qt3D', 'PyQt6.QtDataVisualization']
elif QT_API == 'pyqt5':
    excludes = ['PySide6', 'PySide2', 'PyQt6', 'PyQt5.uic']
elif QT_API == 'pyside6':
    excludes = ['PyQt5', 'PySide2', 'PyQt6', 'PySide6.QtUiTools']
elif QT_API == 'pyside2':
    excludes = ['PyQt5', 'PySide6', 'PyQt6', 'PySide2.QtUiTools']

a = Analysis(
    [os.path.join(ROOT_DIR, 'gitfourchette/__main__.py')],
    pathex=[],
    binaries=[],
    datas=[(os.path.join(ROOT_DIR, 'gitfourchette/assets'), 'assets')],
    hiddenimports=['_cffi_backend'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,  # True: keep pyc files
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='gitfourchette-bin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='GitFourchette',
) 