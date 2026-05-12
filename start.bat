@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

set "VENV_EXISTS=0"
if exist "venv\Scripts\activate.bat" set "VENV_EXISTS=1"

:menu
cls
echo.
echo ================================================================
echo           BTC Collision Engine - Startup Menu
echo ================================================================
echo.
echo System Status:
if !VENV_EXISTS! equ 1 (
    echo   Virtual Environment: [OK] Found
) else (
    echo   Virtual Environment: [WARN] Not Found
)
if exist "targets.txt" (
    echo   Targets File: [OK] Found
) else (
    echo   Targets File: [WARN] Not Found
)
echo.
echo Please select an option:
echo.
echo   1. Interactive Wizard (Recommended)
echo   2. GPU Async Mode (for experienced users)
echo   3. Start Monitor
echo   4. Maintenance and Cleanup
echo   5. Show Help
echo   0. Exit
echo.
echo ================================================================
echo.

set "CHOICE="
set /p "CHOICE=Enter option (0-5): "

if "!CHOICE!"=="" goto :menu

if "!CHOICE!"=="1" (
    if !VENV_EXISTS! equ 1 call venv\Scripts\activate.bat >nul 2>&1
    python key_collision_cli.py --quick-start
    goto :end_action
)

if "!CHOICE!"=="2" (
    start "" cmd /c "start_async_optimized.bat"
    goto :menu
)

if "!CHOICE!"=="3" (
    start "" powershell -Command "& 'monitor.ps1'"
    goto :menu
)

if "!CHOICE!"=="4" (
    call :cleanup_menu
    goto :menu
)

if "!CHOICE!"=="5" (
    if !VENV_EXISTS! equ 1 call venv\Scripts\activate.bat >nul 2>&1
    python key_collision_cli.py --help
    pause
    goto :menu
)

if "!CHOICE!"=="0" (
    echo [INFO] Goodbye!
    exit /b 0
)

echo [ERROR] Invalid option: !CHOICE!
pause
goto :menu

:cleanup_menu
cls
echo.
echo ================================================================
echo           Maintenance and Cleanup Menu
echo ================================================================
echo.
echo   1. Clear log files
echo   2. Clear checkpoint files
echo   3. Clear all temporary files
echo   0. Back
echo.
echo ================================================================
echo.

set "CLEAN_CHOICE="
set /p "CLEAN_CHOICE=Enter option (0-3): "

if "!CLEAN_CHOICE!"=="1" (
    echo [INFO] Clearing log files...
    for /r . %%f in (*.log) do del "%%f" >nul 2>&1
    echo [OK] Done
    pause
    goto :cleanup_menu
)

if "!CLEAN_CHOICE!"=="2" (
    echo [INFO] Clearing checkpoint files...
    for /r . %%f in (*.ckpt) do del "%%f" >nul 2>&1
    echo [OK] Done
    pause
    goto :cleanup_menu
)

if "!CLEAN_CHOICE!"=="3" (
    set "CONFIRM="
    set /p "CONFIRM=Are you sure? (Y/N): "
    if /i not "!CONFIRM!"=="Y" (
        echo [INFO] Cancelled
        pause
        goto :cleanup_menu
    )
    for /r . %%f in (*.log) do del "%%f" >nul 2>&1
    for /r . %%f in (*.ckpt) do del "%%f" >nul 2>&1
    for /d /r . %%d in (__pycache__) do rmdir /s /q "%%d" >nul 2>&1
    echo [OK] All temporary files cleared
    pause
    goto :cleanup_menu
)

if "!CLEAN_CHOICE!"=="0" (
    goto :eof
)

echo [ERROR] Invalid option
pause
goto :cleanup_menu

:end_action
echo.
echo Press any key to return to menu...
pause >nul
goto :menu
