@echo off
REM 监控系统启动批处理文件

echo ===============================================
echo BTC 碰撞引擎 - 监控系统启动脚本
echo ===============================================
echo.

echo 1. 启动基本监控（CPU模式）
echo 2. 启动GPU监控（如果支持）
echo 3. 启动带报告的监控
echo 4. 退出
echo.

set /p choice=请选择操作 (1-4): 

if "%choice%"=="1" goto basic
if "%choice%"=="2" goto gpu
if "%choice%"=="3" goto report
if "%choice%"=="4" goto exit

:basic
echo 启动基本监控系统（CPU模式）...
python start_monitoring.py --mode cpu
goto end

:gpu
echo 启动GPU监控系统...
python start_monitoring.py --mode gpu
goto end

:report
echo 启动带报告的监控系统...
python start_monitoring.py --mode cpu --report
goto end

:exit
echo 退出...
goto end

:end
echo.
echo 操作完成，按任意键退出...
pause >nul
