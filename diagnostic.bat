@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

call :print_header "BTC Collision Engine - Diagnostic Tool"

echo [1/5] Checking Python environment...
call :check_python

for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
echo [OK] Python version: !PY_VER!

echo.
echo [2/5] Checking Python version requirement...
call :check_python_version
echo [OK] Python version check passed

echo.
echo [3/5] Checking dependencies...
set "ALL_DEPS_OK=1"

python -c "import rich" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Missing dependency: rich
    set "ALL_DEPS_OK=0"
) else (
    echo [OK] rich
)

python -c "import ecdsa" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Missing dependency: ecdsa
    set "ALL_DEPS_OK=0"
) else (
    echo [OK] ecdsa
)

python -c "import psutil" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Missing dependency: psutil
    set "ALL_DEPS_OK=0"
) else (
    echo [OK] psutil
)

if !ALL_DEPS_OK! equ 1 (
    echo [OK] All critical dependencies found
) else (
    echo [ERROR] Some dependencies are missing
    goto :error_end
)

echo.
echo [4/5] Checking file structure...
call :check_file_exists "key_collision_cli.py"
echo [OK] key_collision_cli.py exists

echo.
echo [5/5] Testing module import...
python -c "import sys; sys.path.insert(0, '.'); from src.cli.main import main; print('[OK] Module import successful')"
if errorlevel 1 (
    echo [ERROR] Module import failed
    goto :error_end
)

echo.
echo ========================================
echo   Diagnostic completed successfully!
echo ========================================
echo.
pause
exit /b 0

:error_end
echo.
echo [ERROR] Diagnostic failed, please check the errors above
echo.
pause
exit /b 1