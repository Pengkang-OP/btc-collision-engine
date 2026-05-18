@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

call :print_header "BTC Collision Engine - 安装向导"

call :print_section "Step 1: 检查 Python 环境"
call :check_python

for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
echo [OK] Python 版本: !PY_VER!

call :check_python_version

call :print_section "Step 2: 设置虚拟环境"

if exist "venv\Scripts\activate.bat" (
    goto :handle_existing_venv
) else (
    goto :create_venv
)

:handle_existing_venv
echo [INFO] 检测到现有虚拟环境
echo.
echo   1. 保留现有虚拟环境 (修复问题时推荐)
echo   2. 删除并重新创建 (环境损坏时使用)
echo.

:ask_venv
set "VENV_CHOICE="
set /p "VENV_CHOICE=   请选择 [1/2]: "
if "!VENV_CHOICE!"=="1" goto :activate_venv
if "!VENV_CHOICE!"=="2" (
    echo [INFO] 正在删除旧虚拟环境...
    rmdir /s /q venv >nul 2>&1
    goto :create_venv
)
echo [错误] 请输入 1 或 2
goto :ask_venv

:create_venv
echo [INFO] 正在创建虚拟环境...
python -m venv venv
if errorlevel 1 (
    echo [错误] 无法创建虚拟环境
    echo         尝试: python -m pip install virtualenv
    pause
    exit /b 1
)
echo [OK] 虚拟环境已创建

:activate_venv
echo [INFO] 正在激活虚拟环境...
call venv\Scripts\activate.bat >nul 2>&1
if errorlevel 1 (
    echo [错误] 无法激活虚拟环境
    pause
    exit /b 1
)
echo [OK] 虚拟环境已激活

call :print_section "Step 3: 升级 pip"
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo [WARN] pip 升级失败，将使用当前版本继续
    echo [TIP] 如果后续依赖安装失败，请手动执行: python -m pip install --upgrade pip
) else (
    echo [OK] pip 升级成功
)

call :print_section "Step 4: 安装基础依赖"
echo [INFO] 这可能需要几分钟...

echo   正在安装 coincurve (预编译)...
pip install "coincurve>=18.0.0" --only-binary :all: --quiet >nul 2>&1
if errorlevel 1 (
    echo   [警告] 预编译包不可用，正在尝试源码编译...
    pip install "coincurve>=18.0.0" --quiet >nul 2>&1
    if errorlevel 1 (
        echo   [警告] coincurve 安装失败，将使用 ecdsa 备用方案
    ) else (
        echo   [OK] coincurve 已从源码安装
    )
) else (
    echo   [OK] coincurve 已安装
)

echo   正在安装基础依赖...
pip install -r requirements-base.txt --quiet >nul 2>&1
if errorlevel 1 (
    echo [警告] 部分基础依赖安装失败，正在尝试详细安装...
    pip install -r requirements-base.txt
) else (
    echo [OK] 基础依赖已安装
)

call :print_section "Step 5: GPU 加速支持 (可选)"
echo.
echo   GPU 加速可将性能提升 100-1000 倍
echo   需要: pyopencl + 对应显卡的 OpenCL 驱动
echo.
echo   NVIDIA 显卡: 安装 CUDA Toolkit ^>= 11.0
echo   AMD 显卡   : 安装 AMD 驱动 ^>= 21.x
echo   Intel Arc  : 安装 Intel Arc 驱动 ^>= 31.0.101.4146
echo.

:ask_gpu
set "GPU_CHOICE="
set /p "GPU_CHOICE=   是否安装 GPU 依赖? [y/n]: "
if /i "!GPU_CHOICE!"=="y" (
    echo [INFO] 正在安装 GPU 依赖...
    pip install -r requirements-gpu.txt
    if errorlevel 1 (
        echo [警告] GPU 依赖安装失败
        echo         可稍后重试: pip install -r requirements-gpu.txt
    ) else (
        echo [OK] GPU 依赖已安装
    )
    goto :after_gpu
)
if /i "!GPU_CHOICE!"=="n" (
    echo [INFO] 跳过 GPU 依赖，将使用 CPU 模式
    goto :after_gpu
)
echo [错误] 请输入 y 或 n
goto :ask_gpu

:after_gpu
call :print_section "Step 6: 完成设置"

call :create_required_dirs
call :create_config

call :print_section "验证已安装的包"
echo.

rem v4.2.2 R3: 使用 if errorlevel 检测退出码，比 && / || 链更健壮
python -c "import rich"         >nul 2>&1
if errorlevel 1 (echo   [缺失] rich)              else (echo   [OK] rich)
python -c "import coincurve"    >nul 2>&1
if errorlevel 1 (echo   [警告] coincurve (ecdsa 备用)) else (echo   [OK] coincurve)
python -c "import ecdsa"        >nul 2>&1
if errorlevel 1 (echo   [缺失] ecdsa)             else (echo   [OK] ecdsa)
python -c "import psutil"       >nul 2>&1
if errorlevel 1 (echo   [缺失] psutil)            else (echo   [OK] psutil)
python -c "import gmpy2"        >nul 2>&1
if errorlevel 1 (echo   [INFO] gmpy2 (可选))      else (echo   [OK] gmpy2)
python -c "import pyopencl"     >nul 2>&1
if errorlevel 1 (echo   [INFO] pyopencl (GPU 模式不可用)) else (echo   [OK] pyopencl (GPU))
python -c "import jsonschema"   >nul 2>&1
if errorlevel 1 (echo   [缺失] jsonschema)        else (echo   [OK] jsonschema)

call :print_header "安装完成!"
echo.
echo   下一步操作:
echo     双击运行   start.bat        启动快速设置向导
echo     或运行:    start.bat --help 查看所有选项
echo.
echo   直接运行示例:
echo     start.bat -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
echo.
pause
exit /b 0
