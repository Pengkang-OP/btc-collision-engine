@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================
echo BTC 碰撞引擎 - 命令行模式
echo ========================================
echo.

:: 1. 检查Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.9+
    pause
    exit /b 1
)

:: 2. 检查虚拟环境是否激活
if not defined VIRTUAL_ENV (
    echo [警告] 虚拟环境未激活
    if exist "venv\Scripts\activate.bat" (
        set /p ACTIVATE="是否激活虚拟环境? (Y/N): "
        if /i "!ACTIVATE!"=="Y" (
            call venv\Scripts\activate.bat
            echo [成功] 虚拟环境已激活
        )
    ) else (
        echo [信息] 未找到虚拟环境，建议先运行: scripts\install.bat
    )
)

:: 3. 检查配置文件
if not exist "config.json" (
    echo [警告] 配置文件不存在，从示例复制...
    if exist "config.example.json" (
        copy config.example.json config.json > nul
        echo [成功] 配置文件已创建: config.json
    ) else (
        echo [错误] 示例配置文件也不存在
        pause
        exit /b 1
    )
)

:: 4. 检查必要目录
if not exist "logs" mkdir logs
if not exist "data_logs" mkdir data_logs
if not exist "monitoring_data" mkdir monitoring_data

echo.
echo 用法示例:
echo.
echo   随机碰撞:
echo     python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
echo.
echo   范围扫描:
echo     python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFFFFFF
echo.
echo   查看全部选项:
echo     python key_collision_cli.py --help
echo.
python key_collision_cli.py %*
pause
