@echo off
setlocal enabledelayedexpansion

call "%~dp0..\common.bat" :init_encoding
cd /d "%~dp0.."

echo ============================================
echo   Cleaning Up Monitoring Data
echo ============================================
echo.

call "%~dp0..\common.bat" :check_python
if errorlevel 1 exit /b 1
call "%~dp0..\common.bat" :check_python_version
if errorlevel 1 exit /b 1
call "%~dp0..\common.bat" :activate_venv
if errorlevel 1 exit /b 1

call "%~dp0..\common.bat" :check_file_exists "scripts\cleanup_cache.py"
if errorlevel 1 exit /b 1

echo [INFO] Cleaning temporary files and cache...
python scripts\cleanup_cache.py --max-age 30
if errorlevel 1 echo [WARNING] Cleanup completed with warnings

echo.
echo ============================================
echo   Cleanup completed!
echo ============================================
if not defined CI if not defined AUTOMATION pause
