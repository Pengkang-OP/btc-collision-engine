@echo off
call "%~dp0common.bat" :init_encoding
call "%~dp0common.bat" :set_script_dir
call "%~dp0common.bat" :activate_venv
if errorlevel 1 (
    echo [WARNING] 虚拟环境不可用，将使用系统 Python
)

rem -- Start async optimized engine --
echo [INFO] 启动 BTC Collision Engine (异步优化)...
python key_collision_cli.py %*

echo.
echo [INFO] 引擎已退出，按任意键关闭...
pause >nul
