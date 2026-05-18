@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

rem ── 启动 Python 双语菜单 (通过 i18n 系统自动检测语言) ──────────
python start_menu.py
set "MENU_EXIT=%errorlevel%"
if not defined CI if not defined AUTOMATION pause
exit /b %MENU_EXIT%
