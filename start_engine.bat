@echo off
chcp 936 >nul 2>&1
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat >nul 2>&1
)

echo.
echo ================================================================
echo   BTC Collision Engine - Quick Start
echo ================================================================
echo.

python key_collision_cli.py --quick-start
set "EXIT_CODE=%errorlevel%"

echo.
if %EXIT_CODE% equ 0 (
    echo [OK] Completed
) else if %EXIT_CODE% equ 130 (
    echo [INFO] Interrupted by user
) else (
    echo [ERROR] Exit code: %EXIT_CODE%
)

echo.
pause
exit /b %EXIT_CODE%