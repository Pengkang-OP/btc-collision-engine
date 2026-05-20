@echo off
call "%~dp0common.bat"
call :init_encoding
call :set_script_dir
call :print_header "BTC Collision Engine - Installer"

call :check_python
call :check_python_version
call :create_required_dirs
call :create_config

rem -- Create virtual environment --
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call :activate_venv

rem -- Install dependencies --
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo ================================================================
echo   Installation complete!
echo   Run start.bat to launch the engine
echo ================================================================
echo.
pause
