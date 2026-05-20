@echo off
call "%~dp0common.bat" :init_encoding
call "%~dp0common.bat" :set_script_dir
call "%~dp0common.bat" :activate_venv

rem -- Start the engine --
python key_collision_cli.py
if not defined CI if not defined AUTOMATION pause
