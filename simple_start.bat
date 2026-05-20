@echo off
cd /d "%~dp0"
echo Starting BTC Collision Engine...
echo.

rem Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

rem Start the engine
python key_collision_cli.py

pause
