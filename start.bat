@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat" :init_encoding
call "%~dp0common.bat" :set_script_dir

call "%~dp0common.bat" :check_python
if errorlevel 1 (
    echo [ERROR] Python 未安装或不在 PATH 中
    pause
    exit /b 1
)

echo [INFO] 正在启动 BTC Collision Engine...

if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [INFO] 使用: %PYTHON_EXE%
echo.

echo [INFO] 验证 Python 版本...
"%PYTHON_EXE%" --version > _start_test.log 2>&1
type _start_test.log

echo [INFO] 检查 start_menu.py 是否存在...
if not exist "start_menu.py" (
    echo [ERROR] start_menu.py 未找到
    pause
    exit /b 1
)

echo [INFO] 启动菜单...
"%PYTHON_EXE%" start_menu.py
set "MENU_EXIT=%errorlevel%"

if "%MENU_EXIT%" NEQ "0" (
    echo.
    echo [ERROR] 启动失败，退出码: !MENU_EXIT!
)
pause
exit /b %MENU_EXIT%
