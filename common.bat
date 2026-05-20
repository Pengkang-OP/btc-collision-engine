@echo off
:init_encoding
chcp 65001 >nul 2>&1
goto :eof

:set_script_dir
cd /d "%~dp0"
goto :eof

:print_header
echo.
echo ================================================================
echo   %~1
echo ================================================================
echo.
goto :eof

:print_section
echo.
echo --- %~1 ---
echo.
goto :eof

:check_python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)
echo [OK] Python found
goto :eof

:check_python_version
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python version too old
    pause
    exit /b 1
)
echo [OK] Python version OK
goto :eof

:create_required_dirs
for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" mkdir "%%D" >nul 2>&1
)
echo [OK] Runtime directories created
goto :eof

:create_config
if not exist "config.json" (
    if exist "config.example.json" (
        copy "config.example.json" "config.json" >nul 2>&1
        echo [OK] config.json created
    )
) else (
    echo [INFO] config.json exists
)
goto :eof

:activate_venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat >nul 2>&1
    if not errorlevel 1 (
        echo [OK] Virtual env activated
        goto :eof
    )
)
echo [WARNING] Virtual env not found
exit /b 1
goto :eof
