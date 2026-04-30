@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

set "CONFIG_FILE=config.intel_arc.json"
set "PYTHON_SCRIPT=key_collision_cli.py"

call :check_python
call :check_python_version

call :check_file_exists "!CONFIG_FILE!"

call :activate_venv
call :create_required_dirs

call :print_header "BTC 碰撞引擎 - GPU 异步优化模式"

echo   配置文件: !CONFIG_FILE!
echo   GPU: Intel Arc A770 (双缓冲异步)
echo   批处理: 1,000,000 密钥/批次
echo.

echo [INFO] 正在启动 GPU 异步引擎...
echo [INFO] 按 Ctrl+C 安全停止
echo.

python "!PYTHON_SCRIPT!" --config "!CONFIG_FILE!" %*
set "EXIT_CODE=!errorlevel!"

echo.
if !EXIT_CODE! equ 0 (
    echo [OK] 引擎运行完成
) else if !EXIT_CODE! equ 130 (
    echo [INFO] 用户中断操作
) else (
    echo [ERROR] 退出码: !EXIT_CODE!
)

echo.
pause
exit /b !EXIT_CODE!