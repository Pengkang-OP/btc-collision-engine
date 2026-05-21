@echo off
setlocal

rem ============================================================
rem  BTC Collision Engine - 启动入口
rem  注意：若无特殊需要，安装后首次运行应使用 install.bat
rem ============================================================

rem 切换到 bat 所在目录（使用绝对路径）
cd /d "%~dp0"

rem ============================================================
rem 检查 Python
rem ============================================================
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未安装或不在 PATH 中
    echo         请安装 Python 3.9+ 并确保 "python" 命令可用
    echo         下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

rem ============================================================
rem 优先使用虚拟环境中的 Python（依赖完整）
rem ============================================================
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYAPP=%~dp0venv\Scripts\python.exe"
) else (
    set "PYAPP=python"
)

echo [INFO] Starting...

rem ============================================================
rem 启动交互菜单（直接执行，不显式超时等待 - 菜单自身接管输入）
rem ============================================================
"%PYAPP%" "%~dp0start_menu.py"

rem ============================================================
rem 菜单退出后的收尾
rem ============================================================
if errorlevel 1 (
    echo.
    echo [ERROR] 启动出错，退出码: %errorlevel%
)

pause
