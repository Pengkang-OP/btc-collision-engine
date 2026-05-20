@echo off
call "%~dp0common.bat"
call :init_encoding
call :set_script_dir
call :activate_venv

rem -- Optimize for Intel Arc --
python optimize_intel_arc.py
pause
