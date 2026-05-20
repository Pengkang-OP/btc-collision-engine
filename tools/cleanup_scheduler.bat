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

call :check_file_exists "scripts\cleanup_cache.py"

echo [INFO] Cleaning temporary files and cache...
python scripts\cleanup_cache.py --max-age 30

echo.
echo ============================================
echo   Cleanup completed!
echo ============================================
pause
