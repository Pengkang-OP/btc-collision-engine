@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

call :print_header "BTC Collision Engine - Report Generator"

call :check_python
call :check_python_version
call :check_file_exists "generate_report.py"
call :activate_venv

echo   1. Generate daily report
echo   2. Generate weekly report
echo   3. Generate monthly report
echo   4. Generate HTML format report
echo   5. Exit
echo.

set "CHOICE="
set /p "CHOICE=Select operation (1-5): "

if "!CHOICE!"=="1" goto :daily
if "!CHOICE!"=="2" goto :weekly
if "!CHOICE!"=="3" goto :monthly
if "!CHOICE!"=="4" goto :html
if "!CHOICE!"=="5" goto :exit

echo [ERROR] Invalid option: !CHOICE!
goto :end

:daily
echo [INFO] Generating daily report...
python generate_report.py --type daily
goto :end

:weekly
echo [INFO] Generating weekly report...
python generate_report.py --type weekly
goto :end

:monthly
echo [INFO] Generating monthly report...
python generate_report.py --type monthly
goto :end

:html
echo [INFO] Generating HTML report...
python generate_report.py --type daily --html --output report.html
echo [OK] HTML report saved to report.html
goto :end

:exit
echo [INFO] Exiting...
goto :end

:end
echo.
echo Operation completed, press any key to exit...
pause >nul