@echo off
call "%~dp0common.bat"
call :init_encoding
call :set_script_dir
call :activate_venv

rem -- Start the engine --
python key_collision_cli.py
pause
