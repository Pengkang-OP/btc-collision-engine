@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat" :init_encoding
call "%~dp0common.bat" :set_script_dir

echo [INFO] 正在启动 BTC Collision Engine...
echo [INFO] 若窗口立即关闭，请从命令行运行: python start_menu.py
echo.

rem -- Start Python menu --
python start_menu.py
set "MENU_EXIT=%errorlevel%"

if "%MENU_EXIT%" NEQ "0" (
    echo.
    echo [ERROR] 启动失败，退出码: !MENU_EXIT!
    echo        请从命令行运行以查看详细错误:
    echo         python start_menu.py
    echo         python start_engine.bat
)
pause
exit /b %MENU_EXIT%

