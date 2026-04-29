@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Cannot change directory
    pause
    exit /b 1
)

if not exist "key_collision_cli.py" (
    echo [ERROR] key_collision_cli.py not found
    pause
    exit /b 1
)

set "PYTHON_SCRIPT=key_collision_cli.py"

where python >nul 2>&1
if errorlevel 1 (
    echo [WARN] Python not found
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat >nul 2>&1
)

if not exist "logs" mkdir "logs" 2>nul
if not exist "data_logs" mkdir "data_logs" 2>nul
if not exist "monitoring_data" mkdir "monitoring_data" 2>nul

if not exist "config.json" (
    if exist "config.example.json" (
        copy "config.example.json" "config.json" >nul 2>&1
        echo [OK] Created config.json from template
    )
)

echo.
echo ========================================
echo   BTC Collision Engine - Startup Menu
echo ========================================
echo.
echo Select startup mode:
echo.
echo   1. Interactive Wizard (Recommended)
echo   2. Quick Run (using targets.txt)
echo   3. Dual Window Mode (Interactive + Log Monitor)
echo   4. Monitoring System
echo   5. Show Help
echo   0. Exit
echo.
set "CHOICE="
set /p CHOICE=Enter option (0-5, default 1):

if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="1" (
    echo [INFO] Starting Interactive Wizard...
    python "%PYTHON_SCRIPT%" --quick-start
) else if "%CHOICE%"=="2" (
    if not exist "targets.txt" (
        echo [ERROR] targets.txt not found
        echo Please create targets.txt first
        pause
        exit /b 1
    )
    echo [INFO] Starting Quick Run...
    python "%PYTHON_SCRIPT%" --quick-run
) else if "%CHOICE%"=="3" (
    echo [INFO] Starting Dual Window Mode...
    echo [INFO] Log monitor will open in a separate window
    python dual_launcher.py
) else if "%CHOICE%"=="4" (
    echo [INFO] Starting Monitoring System...
    start_monitoring.bat
) else if "%CHOICE%"=="5" (
    python "%PYTHON_SCRIPT%" --help
) else if "%CHOICE%"=="0" (
    echo [INFO] Exiting...
    pause
    exit /b 0
) else (
    echo [ERROR] Invalid option: %CHOICE%
    echo Defaulting to Interactive Wizard...
    python "%PYTHON_SCRIPT%" --quick-start
)

pause