@echo off
setlocal

:: Set Python interpreter (default to python if not specified)
if "%PYTHON%"=="" set PYTHON=python

:: Set APP_VERSION
for /f "tokens=*" %%i in ('%PYTHON% -c "from gitfourchette.appconsts import APP_VERSION; print(APP_VERSION)"') do set APP_VERSION=%%i
echo Building GitFourchette version %APP_VERSION%

:: Set environment variables for spec file
set QT_API=pyqt6

:: Get the directory of this script
set "SCRIPT_DIR=%~dp0"
cd "%SCRIPT_DIR%\.."

:: Create file_version.txt for Windows version info
echo VSVersionInfo(
echo   ffi=FixedFileInfo(
echo     filevers=(1, 3, 0, 0),
echo     prodvers=(1, 3, 0, 0),
echo     mask=0x3f,
echo     flags=0x0,
echo     OS=0x40004,
echo     fileType=0x1,
echo     subtype=0x0,
echo     date=(0, 0)
echo   ),
echo   kids=[
echo     StringFileInfo(
echo       [
echo         StringTable(
echo           u'040904B0',
echo           [StringStruct(u'CompanyName', u'GitFourchette'),
echo           StringStruct(u'FileDescription', u'The comfortable Git UI'),
echo           StringStruct(u'FileVersion', u'%APP_VERSION%'),
echo           StringStruct(u'InternalName', u'GitFourchette'),
echo           StringStruct(u'LegalCopyright', u'Copyright (C) 2025 Iliyas Jorio'),
echo           StringStruct(u'OriginalFilename', u'GitFourchette.exe'),
echo           StringStruct(u'ProductName', u'GitFourchette'),
echo           StringStruct(u'ProductVersion', u'%APP_VERSION%')])
echo       ]
echo     ),
echo     VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
echo   ]
echo ) > file_version.txt

:: Install necessary packages
%PYTHON% -m pip install --upgrade pip setuptools wheel
%PYTHON% -m pip install --upgrade -e .[pyqt6,pygments]
%PYTHON% -m pip install --upgrade pyinstaller

:: Build the Windows executable using the simplified spec
%PYTHON% -m PyInstaller pkg/pyinstaller/simple-windows.spec --noconfirm

:: Clean up temporary files
del file_version.txt

echo Windows build completed successfully. Output is in the dist directory. 