@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat" :init_encoding
call "%~dp0common.bat" :set_script_dir

rem -- Start Python menu --
python start_menu.py
set "MENU_EXIT=%errorlevel%"
if not defined CI if not defined AUTOMATION pause
exit /b %MENU_EXIT%
