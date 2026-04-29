@echo off
chcp 936 >nul 2>&1
cd /d "%~dp0"

set "CONFIG_FILE=config.intel_arc.json"
set "PYTHON_SCRIPT=key_collision_cli.py"

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

if not exist "!CONFIG_FILE!" (
    echo [ERROR] Config file not found: !CONFIG_FILE!
    pause
    exit /b 1
)

if not defined VIRTUAL_ENV (
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat >nul 2>&1
    )
)

for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" mkdir "%%D" 2>nul
)

echo.
echo ================================================================
echo   BTC Collision Engine - GPU Async Optimized
echo ================================================================
echo.
echo   Config: !CONFIG_FILE!
echo   GPU: Intel Arc A770 (Dual Buffer Async)
echo   Batch: 1,000,000 keys/batch
echo.

echo [INFO] Starting GPU async engine...
echo [INFO] Press Ctrl+C to stop safely
echo.

python !PYTHON_SCRIPT! --config "!CONFIG_FILE!" %*
set "EXIT_CODE=!errorlevel!"

echo.
if !EXIT_CODE! equ 0 (
    echo [OK] Engine completed
) else if !EXIT_CODE! equ 130 (
    echo [INFO] Interrupted by user
) else (
    echo [ERROR] Exit code: !EXIT_CODE!
)

echo.
pause
exit /b !EXIT_CODE!