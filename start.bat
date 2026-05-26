@echo off
setlocal enabledelayedexpansion
title BTC Collision Engine

rem ============================================================
rem  BTC Collision Engine - 统一启动入口 (v5.3.0)
rem  首次运行前请先执行 install.bat 安装依赖
rem
rem  用法:
rem     start.bat                  → 交互式菜单
rem     start.bat --help           → 直接透传给 CLI
rem     start.bat -t <地址> ...    → 直接透传给 CLI
rem ============================================================

rem ── 切换到脚本所在目录 ──────────────────────────────────────
cd /d "%~dp0"

rem ── UTF-8 编码 ──────────────────────────────────────────────
chcp 65001 >nul 2>&1

rem ── 确保运行时目录 ──────────────────────────────────────────
for %%D in (logs data_logs) do (
    if not exist "%%D" mkdir "%%D" >nul 2>&1
)

rem ── 检查 Python 是否可用 ────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 goto :no_python

rem ── 选择 Python (优先 venv) ──────────────────────────────────
set "PYAPP=python"
if exist "venv\Scripts\python.exe" set "PYAPP=venv\Scripts\python.exe"

rem ── 检查目标文件  ───────────────────────────────────────────
if not exist "targets.txt" (
    echo [INFO] 未找到 targets.txt，首次运行可先创建目标文件
    echo.
)

rem ── 有参数 → 直接透传给 CLI；无参数 → 交互菜单 ──────────────
if not "%~1"=="" goto :direct_cli

rem ── 交互菜单模式 ────────────────────────────────────────────
echo.
echo [INFO] 正在启动 BTC Collision Engine...
echo.
"%PYAPP%" "start_menu.py" 2>&1
set "EXIT_CODE=!errorlevel!"
goto :exit_handle

rem ── 直接 CLI 模式 ───────────────────────────────────────────
:direct_cli
echo [INFO] 启动命令: "%PYAPP%" key_collision_cli.py %*
echo.
"%PYAPP%" "key_collision_cli.py" %* 2>&1
set "EXIT_CODE=!errorlevel!"

rem ── 退出处理 ────────────────────────────────────────────────
:exit_handle
if !EXIT_CODE! neq 0 (
    echo.
    echo [INFO] 引擎退出码: !EXIT_CODE! ^(非零退出码通常是正常的^)
    echo.
    echo 需要帮助? 运行: start.bat --help
    echo 有问题? 查看日志: logs\collision.log
)
echo.
pause
exit /b !EXIT_CODE!

rem ── Python 未找到 ───────────────────────────────────────────
:no_python
echo.
echo ================================================================
echo   [错误] 未找到 Python
echo ================================================================
echo.
echo   请安装 Python 3.9+ 并添加到 PATH
echo   下载: https://www.python.org/downloads/
echo.
pause
exit /b 1
