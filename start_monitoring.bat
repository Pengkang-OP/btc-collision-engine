@echo off
chcp 936 >nul 2>&1
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

if not exist "start_monitoring.py" (
    echo [ERROR] start_monitoring.py not found
    pause
    exit /b 1
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat >nul 2>&1
)

:menu
cls
echo ===============================================
echo   BTC Collision Engine - Monitoring
echo ===============================================
echo.
echo   1. Start CPU monitoring
echo   2. Start GPU monitoring
echo   3. Start with report
echo   4. Open logs folder
echo   0. Exit
echo.
echo =============================================

set "CHOICE="
set /p CHOICE=Select (0-4):

if "%CHOICE%"=="" goto menu
if "%CHOICE%"=="1" goto basic
if "%CHOICE%"=="2" goto gpu
if "%CHOICE%"=="3" goto report
if "%CHOICE%"=="4" goto viewlog
if "%CHOICE%"=="0" goto exit

echo [ERROR] Invalid option: %CHOICE%
timeout /t 1 >nul
goto menu

:basic
echo.
echo [INFO] Starting CPU monitoring...
python start_monitoring.py --mode cpu
goto done

:gpu
echo.
echo [INFO] Starting GPU monitoring...
python start_monitoring.py --mode gpu
goto done

:report
echo.
echo [INFO] Starting with report...
python start_monitoring.py --mode cpu --report
goto done

:viewlog
echo.
explorer logs
goto menu

:done
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:exit
cls
echo.
echo [INFO] Exiting...
echo.