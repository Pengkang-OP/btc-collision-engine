@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

call :check_python
call :check_python_version
call :check_file_exists "log_monitor.py"
call :activate_venv

echo [INFO] Starting log monitor...
python log_monitor.py %*

pause