@echo off
setlocal

echo.
echo ================================================================
echo              [Quick Start] BTC Collision Engine
echo ================================================================
echo.

rem Check prerequisites before launching
if not exist "venv\Scripts\python.exe" (
    echo [WARN] Virtual environment not found.
    echo        Run install.bat first to set up the environment.
    echo.
    pause
    exit /b 1
)

rem Quick status check
if exist "config.json" (
    echo [OK] config.json found
) else (
    echo [INFO] config.json not found, will use config.example.json as template
)

echo.
echo [INFO] Redirecting to main menu (start_menu.py)...
echo [TIP]  For GPU async optimized mode, run: start_async_optimized.bat
echo [TIP]  To check GPU compatibility first, run: optimize_arc.bat
echo.
timeout /t 2 >nul
python "%~dp0start_menu.py"
