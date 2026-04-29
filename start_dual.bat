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

if not exist "log_monitor.py" (
    echo [ERROR] log_monitor.py not found
    pause
    exit /b 1
)

if not exist "run_engine_no_log.py" (
    echo [ERROR] run_engine_no_log.py not found
    pause
    exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
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
echo ================================================================
echo   BTC Collision Engine - Dual Window Mode
echo ================================================================
echo.
echo [INFO] Starting Log monitor will open in a separate window
echo [INFO] Engine wizard will open in another window
echo.

python dual_launcher.py

echo.
echo [OK] Both windows started!
echo.
echo Press any key to exit this launcher...
pause >nul

REM Exit immediately, let the two windows run independently
exit /b 0