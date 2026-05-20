@echo off
call "%~dp0common.bat"
call :init_encoding
call :set_script_dir
call :activate_venv

rem -- Start async optimized engine --
python -c "from src.cli.main import main; main()"
pause
