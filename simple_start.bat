@echo off
call "%~dp0common.bat" :init_encoding
call "%~dp0common.bat" :set_script_dir
call "%~dp0common.bat" :activate_venv
if errorlevel 1 (
    echo [WARNING] 虚拟环境不可用，使用系统 Python
)

rem -- Start the engine --
python key_collision_cli.py
if not defined CI if not defined AUTOMATION pause
