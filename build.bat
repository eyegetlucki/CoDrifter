@echo off
setlocal
:: Always run from the directory this script lives in
cd /d "%~dp0"

echo.
echo =============================================
echo   CoDrifter Build Script
echo =============================================
echo.

:: Step 1 - PyInstaller
echo [1/2] Running PyInstaller...
call venv\Scripts\pyinstaller.exe build.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. Check output above.
    pause
    exit /b 1
)

echo.
echo PyInstaller complete. Output: dist\CoDrifter\CoDrifter.exe
echo.

:: Step 2 - Inno Setup
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 7\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 7\ISCC.exe
if exist "C:\Program Files\Inno Setup 7\ISCC.exe" set ISCC=C:\Program Files\Inno Setup 7\ISCC.exe
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe

if "%ISCC%"=="" (
    echo [2/2] Inno Setup not found.
    echo       Install from: https://jrsoftware.org/isdl.php
    pause
    exit /b 0
)

echo [2/2] Running Inno Setup...
"%ISCC%" installer\build.iss

if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup failed.
    pause
    exit /b 1
)

echo.
echo =============================================
echo   BUILD COMPLETE
echo   Installer: installer\CoDrifter_Setup.exe
echo =============================================
echo.
pause
