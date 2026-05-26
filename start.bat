﻿﻿﻿@echo off
::: BTC Collision Engine Launcher (v5.0.0)
::: NOTE: This file MUST be saved as UTF-8 with BOM for Windows compatibility.
:::
::: Usage:
:::   start.bat                  -> Interactive menu
:::   start.bat --help           -> Pass to CLI
:::   start.bat -t <addr> ...    -> Pass to CLI

setlocal enabledelayedexpansion
title BTC Collision Engine

cd /d "%~dp0"

::: Set UTF-8 codepage BEFORE any echo
chcp 65001 >nul 2>nul

::: Ensure runtime directories exist
for %%D in (logs data_logs) do (
    if not exist "%%D" mkdir "%%D" >nul 2>&1
)

::: Check if python is available
where python >nul 2>&1
if errorlevel 1 goto :no_python

::: Prefer venv python
set "PYAPP=python"
if exist "venv\Scripts\python.exe" set "PYAPP=venv\Scripts\python.exe"

::: Check targets file hint
if not exist "targets.txt" (
    echo [INFO] targets.txt not found. Create it before first run.
    echo.
)

::: With args -> direct CLI mode; Without args -> interactive menu
if not "%~1"=="" goto :direct_cli

::: ========================
:::  Interactive Menu Mode
::: ========================
echo.
echo [INFO] Starting BTC Collision Engine...
echo.
"%PYAPP%" "start_menu.py"
set "EXIT_CODE=!errorlevel!"
goto :exit_handle

::: ========================
:::  Direct CLI Mode (pass all args through)
::: ========================
:direct_cli
echo [INFO] Command: "%PYAPP%" key_collision_cli.py %*
echo.
"%PYAPP%" "key_collision_cli.py" %*
set "EXIT_CODE=!errorlevel!"
exit /b !EXIT_CODE!

::: ========================
:::  Exit handler (interactive only)
::: ========================
:exit_handle
@echo off
if !EXIT_CODE! neq 0 (
    echo.
    echo [INFO] Engine stopped (code: !EXIT_CODE!)
    echo.
    echo   Need help? Run: start.bat --help
    echo   See logs? File: logs\collision.log
)
echo.
echo --------------------------------------------------
echo   Press any key to exit...
pause >nul
exit /b !EXIT_CODE!

::: ========================
:::  Python Not Found
::: ========================
:no_python
@echo off
echo.
echo ================================================================
echo   [ERROR] Python NOT found!
echo ================================================================
echo.
echo   Please install Python 3.10+ and add to PATH
  (Recommended: Python 3.12)
echo   Download: https://www.python.org/downloads/
echo.
echo   Press any key to exit...
pause >nul
exit /b 1
