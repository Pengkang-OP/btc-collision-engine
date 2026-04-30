@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

call :check_file_exists "key_collision_cli.py"
call :check_file_exists "log_monitor.py"
call :check_file_exists "run_engine_no_log.py"

call :check_python
call :check_python_version
call :activate_venv
call :create_required_dirs
call :create_config

call :print_header "BTC 碰撞引擎 - 双窗口模式"

echo [INFO] 日志监控将在单独窗口打开
echo [INFO] 引擎向导将在另一个窗口打开
echo.

python dual_launcher.py

echo.
echo [OK] 两个窗口已启动!
echo.
echo 按任意键退出此启动器...
pause >nul

exit /b 0