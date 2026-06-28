@echo off
setlocal

echo.
echo =============================================
echo   DriftLine Build Script
echo =============================================
echo.

:: Step 1 — PyInstaller
echo [1/2] Running PyInstaller...
call venv\Scripts\pyinstaller.exe build.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. Check output above.
    pause
    exit /b 1
)

echo.
echo PyInstaller complete. Output: dist\DriftLine\DriftLine.exe
echo.

:: Step 2 — Inno Setup
:: Try default install paths for Inno Setup 7 and 6
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 7\ISCC.exe" (
    set ISCC=C:\Program Files (x86)\Inno Setup 7\ISCC.exe
)
if exist "C:\Program Files\Inno Setup 7\ISCC.exe" (
    set ISCC=C:\Program Files\Inno Setup 7\ISCC.exe
)
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
)

if "%ISCC%"=="" (
    echo [2/2] Inno Setup not found at default path.
    echo       Install Inno Setup 7 from: https://jrsoftware.org/isdl.php
    echo       Then run manually: iscc installer\build.iss
    echo.
    echo PyInstaller output is ready at: dist\DriftLine\
    pause
    exit /b 0
)

echo [2/2] Running Inno Setup...
"%ISCC%" installer\build.iss

if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup failed. Check output above.
    pause
    exit /b 1
)

echo.
echo =============================================
echo   BUILD COMPLETE
echo   Installer: installer\DriftLine_Setup.exe
echo =============================================
echo.
pause
