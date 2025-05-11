# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Add the repo root to sys.path so we can import the spec_helper module
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '../..'))
sys.path.insert(0, ROOT_DIR)

from pkg.pyinstaller import spec_helper
from gitfourchette.appconsts import APP_VERSION

QT_API = "pyqt6"
spec_helper.writeBuildConstants(QT_API)

a = Analysis(
    [Path(ROOT_DIR) / 'gitfourchette/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[(Path(ROOT_DIR) / 'gitfourchette/assets', 'assets')],
    hiddenimports=['_cffi_backend'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=spec_helper.getExcludeList(QT_API),
    noarchive=False,  # True: keep pyc files
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GitFourchette',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # False for a Windows GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=Path(ROOT_DIR) / 'gitfourchette/assets/icons/gitfourchette.ico',  # Add Windows icon
    version='file_version.txt'
) 