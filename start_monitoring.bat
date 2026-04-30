@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

call :check_python
call :check_python_version
call :check_file_exists "start_monitoring.py"
call :activate_venv

:menu
cls
call :print_header "BTC 碰撞引擎 - 监控系统"

echo   1. 启动 CPU 监控
echo   2. 启动 GPU 监控
echo   3. 带报告模式启动
echo   4. 打开日志文件夹
echo   0. 退出
echo.
echo =============================================

set "CHOICE="
set /p "CHOICE=请选择 (0-4): "

if "!CHOICE!"=="" goto :menu
if "!CHOICE!"=="1" goto :basic
if "!CHOICE!"=="2" goto :gpu
if "!CHOICE!"=="3" goto :report
if "!CHOICE!"=="4" goto :viewlog
if "!CHOICE!"=="0" goto :exit

echo [ERROR] 无效选项: !CHOICE!
timeout /t 1 >nul
goto :menu

:basic
echo.
echo [INFO] 正在启动 CPU 监控...
python start_monitoring.py --mode cpu
goto :done

:gpu
echo.
echo [INFO] 正在启动 GPU 监控...
python start_monitoring.py --mode gpu
goto :done

:report
echo.
echo [INFO] 正在启动带报告模式...
python start_monitoring.py --mode cpu --report
goto :done

:viewlog
echo.
echo [INFO] 正在打开日志文件夹...
explorer logs
goto :menu

:done
echo.
echo 按任意键返回菜单...
pause >nul
goto :menu

:exit
cls
echo.
echo [INFO] 正在退出...
echo.