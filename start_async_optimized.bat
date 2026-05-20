@echo off
call "%~dp0common.bat" :init_encoding
call "%~dp0common.bat" :set_script_dir
call "%~dp0common.bat" :activate_venv

rem -- Start async optimized engine --
python -c "from src.cli.main import main; main()"
if not defined CI if not defined AUTOMATION pause
