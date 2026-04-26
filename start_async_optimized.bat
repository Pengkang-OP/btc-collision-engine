@echo off
REM ============================================================
REM BTC 碰撞引擎 - GPU 异步优化版本 (Intel Arc A770)
REM 配置: 双缓冲异步执行 + 1M batch size
REM ============================================================

chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "CONFIG_FILE=config.intel_arc.json"
set "PYTHON_SCRIPT=key_collision_cli.py"

REM ── 检查配置文件 ───────────────────────────────────────────
if not exist "!CONFIG_FILE!" (
    echo [ERROR] 配置文件不存在: !CONFIG_FILE!
    echo [INFO] 请确认 config.intel_arc.json 在项目根目录
    pause
    exit /b 1
)

REM ── 激活虚拟环境 ───────────────────────────────────────────
if not defined VIRTUAL_ENV (
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat 2>nul
    )
)

REM ── 创建必要目录 ───────────────────────────────────────────
for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" mkdir "%%D" 2>nul
)

echo.
echo ================================================================
echo   BTC 碰撞引擎 - GPU 异步优化版本
echo ================================================================
echo.
echo   配置: !CONFIG_FILE!
echo   GPU:  Intel Arc A770 (双缓冲异步)
echo   批量: 1,000,000 keys/batch
echo.

REM ── 启动引擎 ───────────────────────────────────────────────
echo [INFO] 启动 GPU 异步引擎...
echo.

cmd /c python !PYTHON_SCRIPT! --config "!CONFIG_FILE!" %*
set "EXIT_CODE=!errorlevel!"

echo.
if !EXIT_CODE! equ 0 (
    echo [OK] GPU 异步引擎执行完成
) else if !EXIT_CODE! equ 130 (
    echo [INFO] 用户中止 ^(Ctrl+C^)
) else (
    echo [ERROR] 引擎退出，错误码: !EXIT_CODE!
)

echo.
pause
exit /b !EXIT_CODE!
