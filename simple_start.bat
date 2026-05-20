@echo off
cd /d "%~dp0"
echo Starting BTC Collision Engine...
echo.

rem Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    if errorlevel 1 (
        echo [ERROR] Virtual environment activation failed
        pause
        exit /b 1
    )
) else (
    echo [WARNING] Virtual environment not found, using system Python
)

rem Start the engine
python key_collision_cli.py

pause
