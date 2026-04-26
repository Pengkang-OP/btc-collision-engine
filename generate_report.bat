@echo off
REM 监控报告生成批处理文件

echo ===============================================
echo BTC 碰撞引擎 - 监控报告生成脚本
echo ===============================================
echo.

echo 1. 生成每日报告
echo 2. 生成每周报告
echo 3. 生成每月报告
echo 4. 生成HTML格式报告
echo 5. 退出
echo.

set /p choice=请选择操作 (1-5): 

if "%choice%"=="1" goto daily
if "%choice%"=="2" goto weekly
if "%choice%"=="3" goto monthly
if "%choice%"=="4" goto html
if "%choice%"=="5" goto exit

:daily
echo 生成每日报告...
python generate_report.py --type daily
goto end

:weekly
echo 生成每周报告...
python generate_report.py --type weekly
goto end

:monthly
echo 生成每月报告...
python generate_report.py --type monthly
goto end

:html
echo 生成HTML格式报告...
python generate_report.py --type daily --html --output report.html
echo HTML报告已保存到 report.html
goto end

:exit
echo 退出...
goto end

:end
echo.
echo 操作完成，按任意键退出...
pause >nul
