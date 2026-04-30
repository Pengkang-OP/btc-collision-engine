@echo off
cls
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ================================================================
echo              [快速启动] BTC 碰撞引擎 - 交互式向导
echo ================================================================
echo.
echo [提示] 如需使用完整菜单，请运行 start.bat
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python
    echo         请安装 Python 3.9+ 并添加到 PATH
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 版本过旧
    echo         需要 Python 3.9 或更高版本
    pause
    exit /b 1
)

set "VENV_ACTIVATED=0"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat >nul 2>&1
    if not errorlevel 1 (
        set "VENV_ACTIVATED=1"
        echo [OK] 虚拟环境已激活
    )
)

if !VENV_ACTIVATED! equ 0 (
    echo [WARN] 虚拟环境不存在或激活失败
    echo        使用系统 Python - 某些功能可能无法正常工作
    echo        建议运行 install.bat 设置环境
    echo.
)

for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" mkdir "%%D" >nul 2>&1
)

if not exist "config.json" (
    if exist "config.example.json" (
        copy "config.example.json" "config.json" >nul 2>&1
        echo [OK] 已从模板创建 config.json
    )
)

echo [INFO] 正在启动交互式向导...
echo [INFO] 将逐步引导您完成配置
echo.

python key_collision_cli.py --quick-start
set "EXIT_CODE=!errorlevel!"

echo.
echo ================================================================
if !EXIT_CODE! equ 0 (
    echo [OK] 操作完成
) else if !EXIT_CODE! equ 130 (
    echo [INFO] 用户中断操作 (Ctrl+C)
) else if !EXIT_CODE! equ 1 (
    echo [ERROR] 引擎退出，错误码: !EXIT_CODE!
    echo.
    echo [INFO] 故障排除:
    echo        1. 如果看到 '需要指定目标地址' 错误:
    echo           - --quick-start 向导需要安装所有依赖
    echo           - 请先运行 install.bat 安装所需包
    echo           - 或使用直接命令: python key_collision_cli.py -t ^<地址^> -m random
    echo.
    echo        2. 如需使用完整菜单:
    echo           - 运行 start.bat
    echo.
    echo        3. 手动命令示例:
    echo           python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
) else (
    echo [ERROR] 意外错误，错误码: !EXIT_CODE!
    echo         查看 logs/collision.log 获取详情
)
echo ================================================================
echo.
pause