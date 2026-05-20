@echo off
call "%~dp0common.bat" :init_encoding
call "%~dp0common.bat" :set_script_dir
call "%~dp0common.bat" :activate_venv

rem -- Optimize for Intel Arc --
python optimize_intel_arc.py
if not defined CI if not defined AUTOMATION pause
