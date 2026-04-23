@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================
echo BTC 碰撞引擎 - 安装脚本
echo ========================================
echo.

:: 1. 检查Python版本
echo [1/7] 检查Python版本...
python --version > nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.9+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [成功] Python版本: %PYTHON_VERSION%

:: 检查Python版本是否 >= 3.9
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>nul
if errorlevel 1 (
    echo [错误] Python版本过低，需要3.9或更高版本
    echo 当前版本: %PYTHON_VERSION%
    pause
    exit /b 1
)

:: 2. 检查虚拟环境
echo.
echo [2/7] 检查虚拟环境...
if exist "venv\Scripts\activate.bat" (
    echo [信息] 检测到现有虚拟环境
    set /p USE_EXISTING="是否使用现有虚拟环境? (Y/N): "
    if /i "!USE_EXISTING!"=="N" (
        echo [信息] 删除现有虚拟环境...
        rmdir /s /q venv
    ) else (
        goto ACTIVATE_VENV
    )
)

:: 创建虚拟环境
echo [信息] 创建虚拟环境...
python -m venv venv
if errorlevel 1 (
    echo [错误] 创建虚拟环境失败
    pause
    exit /b 1
)
echo [成功] 虚拟环境创建成功

:ACTIVATE_VENV
:: 3. 激活虚拟环境
echo.
echo [3/7] 激活虚拟环境...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [错误] 激活虚拟环境失败
    pause
    exit /b 1
)
echo [成功] 虚拟环境已激活

:: 4. 安装基础依赖
echo.
echo [4/7] 安装基础依赖...
echo [信息] 这可能需要几分钟时间，请耐心等待...
pip install -r requirements-base.txt
if errorlevel 1 (
    echo [警告] 基础依赖安装失败，尝试继续...
) else (
    echo [成功] 基础依赖安装完成
)

:: 5. 提示安装GPU依赖
echo.
echo [5/7] GPU加速支持（可选）...
set /p INSTALL_GPU="是否安装GPU加速依赖? (Y/N): "
if /i "!INSTALL_GPU!"=="Y" (
    echo [信息] 安装GPU依赖...
    pip install -r requirements-gpu.txt
    if errorlevel 1 (
        echo [警告] GPU依赖安装失败，可以稍后手动安装
    ) else (
        echo [成功] GPU依赖安装完成
    )
) else (
    echo [信息] 跳过GPU依赖安装
)

:: 6. 复制配置文件
echo.
echo [6/7] 初始化配置文件...
if not exist "config.json" (
    copy config.example.json config.json > nul
    echo [成功] 配置文件已创建: config.json
) else (
    echo [信息] 配置文件已存在: config.json
)

:: 7. 验证关键依赖
echo.
echo [7/7] 验证关键依赖...
python -c "import coincurve; print('[成功] coincurve')" 2>nul || echo [警告] coincurve未安装
python -c "import gmpy2; print('[成功] gmpy2')" 2>nul || echo [警告] gmpy2未安装
python -c "import psutil; print('[成功] psutil')" 2>nul || echo [警告] psutil未安装

:: 创建必要目录
if not exist "logs" mkdir logs
if not exist "data_logs" mkdir data_logs
if not exist "monitoring_data" mkdir monitoring_data

echo.
echo ========================================
echo 安装完成！
echo ========================================
echo.
echo 快速开始:
echo   1. 激活虚拟环境: venv\Scripts\activate
echo   2. 运行碰撞测试: python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random --duration 10
echo   3. 查看帮助: python key_collision_cli.py --help
echo.
echo 或使用启动脚本:
echo   start.bat -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
echo.
pause
