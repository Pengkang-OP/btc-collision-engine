@echo off
setlocal enabledelayedexpansion

call "%~dp0..\common.bat"
call :init_encoding
cd /d "%~dp0.."

echo ============================================
echo   Cleaning Up Monitoring Data
echo ============================================
echo.

call :check_python
call :check_python_version
call :activate_venv

call :check_file_exists "tools\cleanup_monitoring_data.py"

echo [INFO] Cleaning monitoring data older than 30 days...
python tools\cleanup_monitoring_data.py --max-age 30

echo.
echo ============================================
echo   Cleanup completed!
echo ============================================
pause